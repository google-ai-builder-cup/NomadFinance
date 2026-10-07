from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool

from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient
from app.repositories.scam_taxonomy_repo import ScamTaxonomy, ScamTaxonomyRepository
from app.schemas.scam import (
    MAX_TEXT_CHARS,
    CorridorId,
    InputType,
    Language,
    ScamAnalyzeResponse,
    ScamAnalyzeTextRequest,
    ScamIndicator,
    SimilarScam,
)
from app.schemas.scam_screenshot import ScamAnalyzeFormFields
from app.services.scam.classifier import classify_message
from app.services.scam.explainer import explain_message
from app.services.scam.indicators import MAX_INDICATORS, Signals, extract_signals
from app.services.scam.retrieval import SimilarScamFinder
from app.services.scam.screenshot import read_screenshot_message

logger = logging.getLogger(__name__)

# `expires_at` of a stored check: 90 days after it was last checked (scam.md).
_CHECK_TTL = timedelta(days=90)


class TaxonomyNotLoadedError(RuntimeError):
    """`scam_taxonomy` is empty: the data-scripts loader (NF-SA-001) has not run here."""


async def _load_taxonomy(repo: ScamTaxonomyRepository) -> ScamTaxonomy:
    taxonomy = await run_in_threadpool(repo.get_taxonomy)
    if taxonomy is None:
        raise TaxonomyNotLoadedError("scam_taxonomy has no types or tactics")
    return taxonomy


async def _check_message(
    redacted_text: str,
    *,
    input_type: InputType,
    language: Language,
    corridor_id: CorridorId | None,
    signals: Signals,
    sender: ScamIndicator | None,
    taxonomy: ScamTaxonomy,
    gemini: GeminiClient,
    finder: SimilarScamFinder,
) -> ScamAnalyzeResponse:
    """The steps both paths share, from the redacted message to the contract's answer.

    The parts other tasks own come back as the contract's "not available yet" values: nothing
    is stored or cached (NF-SA-012), so `id` identifies this answer only. The indicators
    were found by fixed rules before the message was masked (`signals`); `seen` stays null until
    reports exist (NF-SA-013).

    The similar-scam search starts with the classification and runs beside it; its answer is
    only returned, never given to the classifier. It cannot fail the check.

    The explainer is written after the verdict, in the worker's language. If it cannot be made
    the worker still gets the verdict, with `explainer_status: "unavailable"`.
    """
    # Started first so it overlaps the classification and the explainer. It handles its own
    # failures, so awaiting it later cannot raise; if the classification fails it is cancelled.
    similar_search = asyncio.create_task(
        finder.find(redacted_text, corridor_id, taxonomy.types.keys())
    )
    try:
        result = await classify_message(redacted_text, taxonomy, gemini, signals)
    except BaseException:
        similar_search.cancel()
        raise
    logger.info(
        "scam_classified input=%s is_scam=%s scam_type=%s risk=%s confidence=%.2f "
        "taxonomy_version=%d",
        input_type,
        result.verdict.is_scam,
        result.verdict.scam_type,
        result.verdict.risk_level,
        result.verdict.confidence,
        taxonomy.version,
    )

    explainer = await explain_message(
        redacted_text,
        result.verdict,
        result.details,
        language=language,
        corridor_id=corridor_id,
        taxonomy=taxonomy,
        gemini=gemini,
    )
    logger.info(
        "scam_explained input=%s kind=%s status=%s",
        input_type,
        "scam" if result.verdict.is_scam else "benign",
        "ready" if explainer else "unavailable",
    )

    retrieval = await similar_search
    now = datetime.now(UTC)
    return ScamAnalyzeResponse(
        id=uuid.uuid4().hex,
        cached=False,
        input_type=input_type,
        language=language,
        message_language=result.message_language,
        redacted_text=redacted_text,
        corridor_id=corridor_id,
        verdict=result.verdict,
        details=result.details,
        indicators=_indicators(sender, signals),
        explainer=explainer,
        explainer_status="ready" if explainer else "unavailable",
        similar=[
            SimilarScam(source=m.source, scam_type=m.scam_type, score=m.score)
            for m in retrieval.similar
        ],
        corridor_report_count=retrieval.corridor_report_count,
        reported=False,
        report_id=None,
        created_at=now,
        expires_at=now + _CHECK_TTL,
    )


def _indicators(sender: ScamIndicator | None, signals: Signals) -> list[ScamIndicator]:
    """The sender a screenshot shows first, then what was found in the text; no repeats, at most
    ten (the contract's limit)."""
    merged: dict[str, ScamIndicator] = {}
    for indicator in ([sender] if sender else []) + signals.indicators:
        merged.setdefault(indicator.id, indicator)
    return list(merged.values())[:MAX_INDICATORS]


async def analyze_text(
    request: ScamAnalyzeTextRequest,
    gemini: GeminiClient,
    taxonomy_repo: ScamTaxonomyRepository,
    finder: SimilarScamFinder,
) -> ScamAnalyzeResponse:
    """Check one pasted message and answer in the shape of the v2 contract.

    Args:
        request: The validated body; `text` is the message as received.
        gemini: Client for the classification-tier call.
        taxonomy_repo: Where the scam types and tactics the model may name are read.
        finder: The neighbour search over known scams and Radar reports.

    Raises:
        TaxonomyNotLoadedError: No taxonomy in Firestore.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    taxonomy = await _load_taxonomy(taxonomy_repo)
    # The raw text goes no further than these lines: the model, the answer's text and the logs
    # only ever see the masked one. The indicators are the exception the data model allows (the
    # scam's own contact points, shown to the worker who pasted them), found here, before the
    # masking, and never fetched.
    redacted_text = redact_text(request.text)
    signals = extract_signals(request.text, redacted_text, corridor_id=request.corridor_id)
    return await _check_message(
        redacted_text,
        input_type="text",
        language=request.language,
        corridor_id=request.corridor_id,
        signals=signals,
        sender=None,
        taxonomy=taxonomy,
        gemini=gemini,
        finder=finder,
    )


async def analyze_screenshot(
    image: bytes,
    fields: ScamAnalyzeFormFields,
    gemini: GeminiClient,
    taxonomy_repo: ScamTaxonomyRepository,
    finder: SimilarScamFinder,
) -> ScamAnalyzeResponse:
    """Read a screenshot of a message, then check it exactly as pasted text is checked.

    The image is only held in memory for this call. The text read from it is masked before
    anything else sees it, and a sender it shows becomes an indicator of kind `sender`.

    Args:
        image: The uploaded file, already known to be a JPEG, PNG or WebP of at most 5 MB.
        fields: The form's `language` and `corridor_id`.
        gemini: Client for the Vision call and the classification call.
        taxonomy_repo: Where the scam types and tactics the model may name are read.
        finder: The neighbour search over known scams and Radar reports.

    Raises:
        ImageUnreadableError: The file cannot be decoded, or shows no message text.
        TaxonomyNotLoadedError: No taxonomy in Firestore.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    # Before the Vision call, so a server that cannot finish the check does not spend quota.
    taxonomy = await _load_taxonomy(taxonomy_repo)
    message = await read_screenshot_message(image, gemini)
    # A screenshot cannot be asked to be shorter, so a long conversation is cut here (after
    # masking, which can lengthen a short number) rather than refused.
    redacted_text = redact_text(message.text)[:MAX_TEXT_CHARS].strip()
    signals = extract_signals(message.text, redacted_text, corridor_id=fields.corridor_id)
    return await _check_message(
        redacted_text,
        input_type="screenshot",
        language=fields.language,
        corridor_id=fields.corridor_id,
        signals=signals,
        sender=message.sender,
        taxonomy=taxonomy,
        gemini=gemini,
        finder=finder,
    )
