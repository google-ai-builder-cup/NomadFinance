"""One-tap report of a scam check to Exploitation Radar (NF-SA-013, cross-pillar flow).

The worker has seen a sheet listing exactly what other workers will see, and this carries what
they confirmed (docs/api/v2-scam.md, `POST /scam/checks/{id}/report`). Nothing here reads the
worker's identity into the report: no uid, no reporter hash, no check id, no raw message.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError

from app.config import get_settings
from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient, ModelTier, model_for
from app.repositories.radar_repo import RadarRepository
from app.repositories.scam_report_repo import (
    CheckGoneError,
    CommitResult,
    IndicatorUpdate,
    ScamReportRepository,
)
from app.repositories.scam_taxonomy_repo import ScamTaxonomyRepository
from app.repositories.user_repo import UserRepository
from app.schemas.radar import RadarReport, RadarValidation
from app.schemas.radar_scam import RadarScamReport, ReportedIndicator
from app.schemas.scam import (
    ScamCheckDetail,
    ScamIndicator,
    ScamReportRequest,
    ScamReportResponse,
)
from app.services.radar.aggregation import update_entity_risk
from app.services.radar.clustering import embed_report, find_cluster
from app.services.scam.check_store import (
    CheckStore,
    StoredCheckUnreadableError,
    from_document,
    is_expired,
)
from app.services.scam.history import CheckNotFoundError, valid_check_id
from app.services.scam.indicator_seen import indicator_doc_id
from app.utils.corridors import CORRIDOR_HOST_HOME

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_CHARS = 1000
_HOST_COUNTRIES = frozenset({"SG", "KR", "MY", "JP", "HK", "AU"})


class NotAScamError(ValueError):
    """The check's verdict is not a scam: only a message the analyzer judged a scam is reported."""


class IndicatorsNotInCheckError(ValueError):
    """The request names an indicator the check does not have."""


@dataclass(frozen=True)
class ReportOutcome:
    response: ScamReportResponse
    created: bool


def entity_slug(scam_type: str) -> str:
    """The Radar profile of a kind of scam: `scam-` and the type id with hyphens."""
    return f"scam-{scam_type.replace('_', '-')}"


def _label(taxonomy: ScamTaxonomyRepository, scam_type: str) -> str:
    """The taxonomy's English label; the id spelled out if the taxonomy is not loaded, so a
    report is not lost because a lookup failed."""
    try:
        loaded = taxonomy.get_taxonomy()
    except GoogleAPIError:
        loaded = None
    label = (loaded.types.get(scam_type, {}) if loaded else {}).get("label")
    return str(label) if label else scam_type.replace("_", " ").capitalize()


class ScamReporter:
    """Turns a stored scam check into a Radar report, once."""

    def __init__(
        self,
        store: CheckStore,
        reports: ScamReportRepository,
        radar: RadarRepository,
        users: UserRepository,
        taxonomy: ScamTaxonomyRepository,
        gemini: GeminiClient,
    ) -> None:
        self._store = store
        self._reports = reports
        self._radar = radar
        self._users = users
        self._taxonomy = taxonomy
        self._gemini = gemini

    async def report(self, uid: str, check_id: str, request: ScamReportRequest) -> ReportOutcome:
        """Report the check, or return the report it already has.

        Raises:
            CheckNotFoundError: No such check of this worker's (unknown, expired or not theirs).
            NotAScamError: The check's verdict is not a scam.
            IndicatorsNotInCheckError: `indicator_ids` names one the check does not have.
        """
        now = datetime.now(UTC)
        document, check = await self._load(uid, check_id, now)
        if not check.verdict.is_scam or check.verdict.scam_type is None:
            raise NotAScamError(check_id)
        if document.get("reported_report_id"):
            return await self._existing(str(document["reported_report_id"]), check, now, document)
        ticked = self._ticked(check, request.indicator_ids)

        scam_type = check.verdict.scam_type
        slug = entity_slug(scam_type)
        description = redact_text(request.description or check.redacted_text)
        description = description[:MAX_DESCRIPTION_CHARS].strip()
        host_country = await self._host_country(uid, check)
        report_id = self._radar.new_report_id()
        # Before the transaction: a Gemini call must not hold one open. A vector that could not
        # be made starts a cluster of its own, as for any report (clustering.py).
        embedding = await embed_report(description, self._gemini)
        cluster_id = await find_cluster(embedding, check.corridor_id, slug, report_id, self._radar)

        report = RadarReport(
            entity_type="scam_type",
            entity_name=await run_in_threadpool(_label, self._taxonomy, scam_type),
            entity_slug=slug,
            violation_type="scam_message",
            corridor_id=check.corridor_id,
            host_country=host_country,
            description=description,
            language=_language(check),
            cluster_id=cluster_id,
            source="scam_check",
            validation=RadarValidation(
                spam_score=0.0,  # the analyzer already classified it: there is no spam check
                category_confidence=check.verdict.confidence,
                model=_classifier_model(document),
            ),
            scam=RadarScamReport(
                scam_type=scam_type,
                tactics=check.verdict.tactics,
                risk_level=check.verdict.risk_level,
                confidence=check.verdict.confidence,
                trigger_phrases=check.verdict.trigger_phrases,
                details=check.details,
                indicators=[
                    ReportedIndicator(
                        kind=i.kind, value=i.value, flags=i.flags, imitates=i.imitates
                    )
                    for i in ticked
                ],
                message_language=check.message_language,
                input_type=check.input_type,
            ),
            created_at=now,
        )
        updates = [
            IndicatorUpdate(indicator_doc_id(i), i.kind, i.value, list(i.flags), i.imitates)
            for i in ticked
        ]
        try:
            result: CommitResult = await run_in_threadpool(
                lambda: self._reports.commit_report(
                    uid=uid,
                    check_id=check_id,
                    report_id=report_id,
                    report=report,
                    updates=updates,
                    scam_type=scam_type,
                    now=now,
                )
            )
        except CheckGoneError as exc:
            raise CheckNotFoundError(check_id) from exc
        if not result.created:
            # Another tap won while this one embedded: the report is the first one, and this
            # one's vector is never saved.
            return await self._existing(result.report_id, check, now, document)

        await self._after_commit(report, report_id, embedding, now)
        logger.info(
            "scam_reported report_id=%s slug=%s indicators=%d cluster=%s",
            report_id,
            slug,
            len(ticked),
            "new" if cluster_id == report_id else "joined",
        )
        return ReportOutcome(
            ScamReportResponse(
                report_id=report_id,
                already_reported=False,
                entity_slug=slug,
                entity_name=report.entity_name,
                created_at=now,
            ),
            created=True,
        )

    async def _load(
        self, uid: str, check_id: str, now: datetime
    ) -> tuple[dict[str, Any], ScamCheckDetail]:
        if not valid_check_id(check_id):
            raise CheckNotFoundError(check_id)
        document = await run_in_threadpool(self._store.checks.get, uid, check_id)
        if document is None or is_expired(document, now):
            raise CheckNotFoundError(check_id)
        try:
            return document, from_document(check_id, document)
        except StoredCheckUnreadableError as exc:
            raise CheckNotFoundError(check_id) from exc

    @staticmethod
    def _ticked(check: ScamCheckDetail, indicator_ids: list[str]) -> list[ScamIndicator]:
        by_id = {i.id: i for i in check.indicators}
        unknown = [i for i in indicator_ids if i not in by_id]
        if unknown:
            raise IndicatorsNotInCheckError(", ".join(unknown))
        wanted = set(indicator_ids)
        return [i for i in check.indicators if i.id in wanted]  # the check's own order

    async def _host_country(self, uid: str, check: ScamCheckDetail) -> str | None:
        """The profile's host country (a country, not an identity), else the corridor's."""
        try:
            profile = await run_in_threadpool(self._users.get_profile, uid)
        except GoogleAPIError:
            profile = {}
        country = profile.get("host_country")
        if country in _HOST_COUNTRIES:
            return str(country)
        pair = CORRIDOR_HOST_HOME.get(check.corridor_id or "")
        return pair[0] if pair else None

    async def _existing(
        self, report_id: str, check: ScamCheckDetail, now: datetime, document: dict[str, Any]
    ) -> ReportOutcome:
        """The report this check already has, as the answer to a repeat tap."""
        stored = await run_in_threadpool(self._radar.get, report_id)
        scam_type = check.verdict.scam_type or "other_scam"
        created_at = (stored or {}).get("created_at") or document.get("reported_at") or now
        return ReportOutcome(
            ScamReportResponse(
                report_id=report_id,
                already_reported=True,
                entity_slug=str((stored or {}).get("entity_slug") or entity_slug(scam_type)),
                entity_name=str(
                    (stored or {}).get("entity_name")
                    or await run_in_threadpool(_label, self._taxonomy, scam_type)
                ),
                created_at=created_at,
            ),
            created=False,
        )

    async def _after_commit(
        self, report: RadarReport, report_id: str, embedding: list[float] | None, now: datetime
    ) -> None:
        """The embedding and the entity's profile: best effort, the report is already stored."""
        if embedding is not None:
            try:
                await run_in_threadpool(
                    lambda: self._radar.create_embedding(
                        report_id,
                        embedding,
                        model=get_settings().gemini_model_embedding,
                        corridor_id=report.corridor_id,
                        entity_type=report.entity_type,
                        entity_slug=report.entity_slug,
                        created_at=now,
                    )
                )
            except GoogleAPIError:
                logger.exception("scam_report_embedding_not_stored report_id=%s", report_id)
        await update_entity_risk(report, report_id, self._radar, now)


def _language(check: ScamCheckDetail) -> str:
    """The message's language, or the worker's when it is `other` or unknown."""
    language = check.message_language
    return language if language and language != "other" else check.language


def _classifier_model(document: dict[str, Any]) -> str:
    """The model that judged the message, as the check recorded it."""
    models = document.get("models")
    recorded = models.get("classifier") if isinstance(models, dict) else None
    return str(recorded) if recorded else model_for(ModelTier.CLASSIFICATION, get_settings())
