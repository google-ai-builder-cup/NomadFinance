from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, get_args

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.scam_taxonomy_repo import ScamTaxonomy
from app.schemas.scam import (
    ContactChannel,
    MessageLanguage,
    ScamAmount,
    ScamDetails,
    ScamVerdict,
)
from app.schemas.scam_classify import ClassifiedDetails, ScamClassification

# Loaded at import so a missing or malformed prompt file stops the app at startup. The check
# records CLASSIFY_PROMPT.key / .version in `prompt_versions`.
CLASSIFY_PROMPT = load_prompt("scam", "classify", 1)

# A scam that fits no listed type is still a scam, never a wrong type (scam.md).
FALLBACK_TYPE = "other_scam"

_MAX_TACTICS = 6
_MAX_TRIGGER_PHRASES = 5
_MAX_PHRASE_CHARS = 80
_MAX_DETAIL_CHARS = 120
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
_CONTACT_CHANNELS: tuple[ContactChannel, ...] = get_args(ContactChannel)
_MESSAGE_LANGUAGES: tuple[MessageLanguage, ...] = get_args(MessageLanguage)


@dataclass(frozen=True)
class Classification:
    """The verdict and details of one message, trimmed to the contract's strict types."""

    verdict: ScamVerdict
    details: ScamDetails
    message_language: MessageLanguage | None


def _taxonomy_json(taxonomy: ScamTaxonomy) -> str:
    """The grounding the model sees: ids and what tells them apart, not sources or curators."""

    def entry(doc_id: str, doc: dict[str, Any], *extra: str) -> dict[str, Any]:
        keys = ("label", "definition", "signs", *extra)
        return {"id": doc_id, **{key: doc[key] for key in keys if key in doc}}

    return json.dumps(
        {
            "types": [entry(i, d, "default_risk") for i, d in taxonomy.types.items()],
            "tactics": [entry(i, d) for i, d in taxonomy.tactics.items()],
        },
        ensure_ascii=False,
    )


def _fenced(text: str) -> str:
    # The prompt tells the model that everything inside <message> is data. A message that
    # contains the closing tag could otherwise end that section early.
    return text.replace("</message", "< /message")


def _short(raw: str | None, limit: int = _MAX_DETAIL_CHARS) -> str | None:
    text = (raw or "").strip()[:limit].strip()
    return text or None


def _phrases(raw: list[str], redacted_text: str) -> list[str]:
    """Keep what really is a piece of the text, so the screen can highlight it."""
    kept: list[str] = []
    for phrase in raw:
        wanted = phrase.strip()[:_MAX_PHRASE_CHARS].strip()
        if not wanted:
            continue
        # A model often changes the case; the text's own spelling is what gets highlighted.
        found = re.search(re.escape(wanted), redacted_text, re.IGNORECASE)
        if found and found.group(0) not in kept:
            kept.append(found.group(0))
    return kept[:_MAX_TRIGGER_PHRASES]


def _amount(amount: float | None, currency: str | None) -> ScamAmount | None:
    code = (currency or "").strip().upper()
    if amount is None or not math.isfinite(amount) or amount <= 0 or not _CURRENCY_CODE.match(code):
        return None
    return ScamAmount(amount=amount, currency=code)


def _details(raw: ClassifiedDetails) -> ScamDetails:
    channel = (raw.contact_channel or "").strip().lower()
    return ScamDetails(
        claimed_identity=_short(raw.claimed_identity),
        contact_channel=next((c for c in _CONTACT_CHANNELS if c == channel), None),
        payment_requested=_short(raw.payment_requested),
        amount_requested=_amount(raw.amount, raw.currency),
        deadline_stated=raw.deadline_stated,
    )


def _message_language(raw: str | None) -> MessageLanguage | None:
    if not raw:
        return None
    code = re.split(r"[-_]", raw.strip().lower())[0]
    # A language outside the six is "other", not unknown: the screens use it to say so.
    return next((lang for lang in _MESSAGE_LANGUAGES if lang == code), "other")


def _clean(raw: ScamClassification, redacted_text: str, taxonomy: ScamTaxonomy) -> Classification:
    """Turn what the model returned into the contract's types.

    Anything the model invented (a type or tactic id outside the taxonomy, a phrase that is
    not in the text, a confidence of 1.4) is corrected or dropped rather than failing the
    check: the worker still gets a verdict.
    """
    details = _details(raw.details)
    language = _message_language(raw.message_language)
    if not raw.is_scam:
        verdict = ScamVerdict(
            is_scam=False,
            scam_type=None,
            tactics=[],
            risk_level="low",
            confidence=_confidence(raw.confidence),
            trigger_phrases=[],
        )
        return Classification(verdict, details, language)

    tactics: list[str] = []
    for tactic in raw.tactics:
        tactic_id = tactic.strip()
        if tactic_id in taxonomy.tactics and tactic_id not in tactics:
            tactics.append(tactic_id)
    scam_type = (raw.scam_type or "").strip()
    verdict = ScamVerdict(
        is_scam=True,
        scam_type=scam_type if scam_type in taxonomy.types else FALLBACK_TYPE,
        tactics=tactics[:_MAX_TACTICS],
        risk_level=raw.risk_level,
        confidence=_confidence(raw.confidence),
        trigger_phrases=_phrases(raw.trigger_phrases, redacted_text),
    )
    return Classification(verdict, details, language)


def _confidence(raw: float) -> float:
    return min(1.0, max(0.0, raw)) if math.isfinite(raw) else 0.0


async def classify_message(
    redacted_text: str, taxonomy: ScamTaxonomy, gemini: GeminiClient
) -> Classification:
    """Decide whether a message is a scam, of which type, and how risky.

    Args:
        redacted_text: The message after `redact_text`. Never the raw text: it is sent to the
            model and highlighted back to the worker, and neither may carry identifiers.
        taxonomy: The scam types and tactics the model may name.
        gemini: Client for the classification-tier call.

    Returns:
        The verdict, what the message asks for, and its language. A scam always has a type
        (`other_scam` when the model named none that exists) and only taxonomy tactics.

    Raises:
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    raw = await gemini.generate_structured(
        operation=CLASSIFY_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=CLASSIFY_PROMPT.render_user(
            taxonomy_json=_taxonomy_json(taxonomy), message=_fenced(redacted_text)
        ),
        response_model=ScamClassification,
        system_instruction=CLASSIFY_PROMPT.system,
        # A classification: the same message should always get the same verdict.
        temperature=0.0,
    )
    return _clean(raw, redacted_text, taxonomy)
