"""Stored checks and the cache over them (NF-SA-012).

A check is stored under an id derived from its cache key, so the same message in the same
language is found by one read, and a retried request writes the same document instead of a
second one. Everything stored is what the contract may show plus the bookkeeping of
`docs/data-model/collections/scam.md`; the raw message is never here, only the redacted one.
The indicators carry their values on purpose (that document, decision 2), nothing else of the
message's identifiers does.
"""

from __future__ import annotations

import hashlib
import logging
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError
from pydantic import ValidationError

from app.config import get_settings
from app.integrations.gemini import ModelTier, model_for
from app.repositories.scam_check_repo import ScamCheckRepository
from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.schemas.scam import ScamAnalyzeResponse, ScamCheckDetail, ScamIndicator
from app.services.scam.classifier import CLASSIFY_PROMPT
from app.services.scam.explainer import EXPLAIN_PROMPT, REASSURE_PROMPT
from app.services.scam.indicator_seen import attach_seen

logger = logging.getLogger(__name__)

# `expires_at` of a stored check: 90 days after it was last checked (scam.md).
CHECK_TTL = timedelta(days=90)
SCHEMA_VERSION = 1


def cache_key(redacted_text: str, language: str) -> str:
    """SHA-256 of the normalised redacted text, a newline and the output language (scam.md).

    Normalised so a message that differs only in case, spacing or a look-alike character form
    is the same message; the language is part of it because the explainer is written in it.
    """
    normalised = " ".join(unicodedata.normalize("NFKC", redacted_text).casefold().split())
    return hashlib.sha256(f"{normalised}\n{language}".encode()).hexdigest()


def check_id_for(key: str) -> str:
    return key[:32]


def prompt_versions(is_scam: bool) -> dict[str, int]:
    """The prompts a check of this kind used: a scam is explained, anything else reassured."""
    steps = [CLASSIFY_PROMPT, EXPLAIN_PROMPT if is_scam else REASSURE_PROMPT]
    return {prompt.key: prompt.version for prompt in steps}


def models_used(is_scam: bool, input_type: str) -> dict[str, str]:
    """The models the tiers point to now. The explainer's is the tier it starts on: a scam is
    explained on the reasoning tier and, if that is busy, on the classification tier, which this
    does not record."""
    settings = get_settings()
    models = {
        "classifier": model_for(ModelTier.CLASSIFICATION, settings),
        "explainer": model_for(
            ModelTier.REASONING if is_scam else ModelTier.CLASSIFICATION, settings
        ),
    }
    if input_type == "screenshot":
        models["vision"] = model_for(ModelTier.EXTRACTION, settings)
    return models


class StoredCheckUnreadableError(ValueError):
    """A stored document no longer fits the contract: treated as absent, never shown."""


def to_document(
    check: ScamCheckDetail,
    *,
    key: str,
    taxonomy_version: int,
    check_count: int,
    last_checked_at: datetime,
    reported_at: datetime | None,
) -> dict[str, Any]:
    """What is written for a check. Fields that are unknown are left out, as the schema says."""
    is_scam = check.verdict.is_scam
    document: dict[str, Any] = {
        "input_type": check.input_type,
        "language": check.language,
        "message_language": check.message_language,
        "redacted_text": check.redacted_text,
        "cache_key": key,
        "corridor_id": check.corridor_id,
        "verdict": check.verdict.model_dump(mode="json"),
        "details": check.details.model_dump(mode="json"),
        # `seen` is read live when the check is shown; it is never stored on the check.
        "indicators": [
            i.model_dump(mode="json", exclude={"seen"}, exclude_none=True) for i in check.indicators
        ],
        "explainer": check.explainer.model_dump(mode="json") if check.explainer else None,
        "similar": [s.model_dump(mode="json") for s in check.similar],
        "corridor_report_count": check.corridor_report_count,
        "reported_report_id": check.report_id,
        "reported_at": reported_at,
        "check_count": check_count,
        "last_checked_at": last_checked_at,
        "taxonomy_version": taxonomy_version,
        "models": models_used(is_scam, check.input_type),
        "prompt_versions": prompt_versions(is_scam),
        "created_at": check.created_at,
        "expires_at": check.expires_at,
        "schema_version": SCHEMA_VERSION,
    }
    return {name: value for name, value in document.items() if value is not None}


def from_document(check_id: str, document: dict[str, Any]) -> ScamCheckDetail:
    """The contract's view of a stored check (no bookkeeping, no `seen` yet)."""
    report_id = document.get("reported_report_id")
    explainer = document.get("explainer")
    try:
        return ScamCheckDetail.model_validate(
            {
                "id": check_id,
                "input_type": document["input_type"],
                "language": document["language"],
                "message_language": document.get("message_language"),
                "redacted_text": document["redacted_text"],
                "corridor_id": document.get("corridor_id"),
                "verdict": document["verdict"],
                "details": document.get("details", {}),
                "indicators": document.get("indicators", []),
                "explainer": explainer,
                "explainer_status": "ready" if explainer else "unavailable",
                "similar": document.get("similar", []),
                "corridor_report_count": document.get("corridor_report_count"),
                "reported": report_id is not None,
                "report_id": report_id,
                "created_at": document["created_at"],
                "expires_at": document["expires_at"],
            }
        )
    except (KeyError, ValidationError) as exc:
        raise StoredCheckUnreadableError(check_id) from exc


def is_expired(document: dict[str, Any], now: datetime) -> bool:
    """Past `expires_at` counts as gone: the TTL policy deletes within a day or so, not at once."""
    expires = document.get("expires_at")
    return not isinstance(expires, datetime) or expires <= now


def is_usable_as_answer(document: dict[str, Any], taxonomy_version: int) -> bool:
    """Whether a stored check may be served again instead of asking Gemini.

    Not when it has no explainer (the next try makes one), when the taxonomy has changed, or
    when a prompt it was made with has a newer version: the answer would differ.
    """
    if not document.get("explainer") or document.get("taxonomy_version") != taxonomy_version:
        return False
    stored = document.get("prompt_versions")
    if not isinstance(stored, dict) or not stored:
        return False
    current = prompt_versions(bool(document.get("verdict", {}).get("is_scam")))
    return all(current.get(key) == version for key, version in stored.items())


@dataclass(frozen=True)
class Lookup:
    """What the store knew about a message: an answer to serve, and an older check to carry on."""

    hit: ScamCheckDetail | None
    previous: dict[str, Any] | None


NOTHING_STORED = Lookup(None, None)


class CheckStore:
    """Reads and writes a worker's stored checks. A Firestore failure never fails a check: the
    worker still gets the answer, only the history and the cache miss out."""

    def __init__(self, checks: ScamCheckRepository, indicators: ScamIndicatorRepository) -> None:
        self.checks = checks
        self._indicators = indicators

    async def lookup(self, uid: str, key: str, taxonomy_version: int, now: datetime) -> Lookup:
        check_id = check_id_for(key)
        try:
            document = await run_in_threadpool(self.checks.get, uid, check_id)
        except GoogleAPIError as exc:
            logger.warning("scam_cache_unavailable error=%s", type(exc).__name__)
            return NOTHING_STORED
        if document is None or is_expired(document, now):
            return NOTHING_STORED
        if not is_usable_as_answer(document, taxonomy_version):
            return Lookup(None, document)
        try:
            return Lookup(from_document(check_id, document), document)
        except StoredCheckUnreadableError:
            logger.warning("scam_check_unreadable")
            return NOTHING_STORED

    async def serve_hit(self, uid: str, hit: ScamCheckDetail, now: datetime) -> ScamAnalyzeResponse:
        """A stored check as the answer: counted as one more check, with its expiry moved."""
        expires_at = now + CHECK_TTL
        try:
            await run_in_threadpool(
                self.checks.touch, uid, hit.id, last_checked_at=now, expires_at=expires_at
            )
        except GoogleAPIError as exc:
            logger.warning("scam_cache_touch_failed error=%s", type(exc).__name__)
        answer = ScamAnalyzeResponse.model_validate(
            {**hit.model_dump(), "cached": True, "expires_at": expires_at}
        )
        return answer.model_copy(update={"indicators": await self.with_seen(answer.indicators)})

    async def save(
        self,
        uid: str,
        key: str,
        check: ScamCheckDetail,
        *,
        taxonomy_version: int,
        previous: dict[str, Any] | None,
        now: datetime,
    ) -> None:
        """Store a freshly made check, keeping what an older check of the same message had:
        whether it was reported, and how many times it has been checked."""
        document = to_document(
            check,
            key=key,
            taxonomy_version=taxonomy_version,
            check_count=int((previous or {}).get("check_count", 0)) + 1,
            last_checked_at=now,
            reported_at=(previous or {}).get("reported_at"),
        )
        try:
            await run_in_threadpool(self.checks.save, uid, check.id, document)
        except GoogleAPIError as exc:
            logger.warning("scam_check_not_stored error=%s", type(exc).__name__)

    async def with_seen(self, indicators: list[ScamIndicator]) -> list[ScamIndicator]:
        return await attach_seen(indicators, self._indicators)
