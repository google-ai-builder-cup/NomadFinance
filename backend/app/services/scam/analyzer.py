from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.core.cache import log_cache_lookup
from app.core.rate_limit import consume_limit
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
from app.services.scam.check_store import CHECK_TTL, CheckStore, cache_key, check_id_for
from app.services.scam.classifier import classify_message
from app.services.scam.explainer import explain_message
from app.services.scam.indicators import MAX_INDICATORS, Signals, extract_signals
from app.services.scam.retrieval import SimilarScamFinder
from app.services.scam.screenshot import read_screenshot_message

logger = logging.getLogger(__name__)

HOURLY_BUDGET_MESSAGE = "You have used all your checks for this hour. Please try again later."


class TaxonomyNotLoadedError(RuntimeError):
    """`scam_taxonomy` is empty: the data-scripts loader (NF-SA-001) has not run here."""


async def _load_taxonomy(repo: ScamTaxonomyRepository) -> ScamTaxonomy:
    taxonomy = await run_in_threadpool(repo.get_taxonomy)
    if taxonomy is None:
        raise TaxonomyNotLoadedError("scam_taxonomy has no types or tactics")
    return taxonomy


def _charge_hourly_budget(uid: str) -> None:
    """One of the worker's 20 checks an hour that call Gemini (`RATE_LIMIT_SCAM_ANALYZE`), or a
    429 with Retry-After. Spent only when Gemini is about to be called."""
    consume_limit(
        get_settings().rate_limit_scam_analyze, "scam_analyze", uid, HOURLY_BUDGET_MESSAGE
    )


async def _check_message(
    redacted_text: str,
    *,
    uid: str,
    store: CheckStore,
    charge_budget: bool,
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

    The message is looked up first (`check_store`): a check made before with the same text and
    language, under the same taxonomy and prompts and with an explainer, is the answer, and no
    Gemini call is made and no hourly budget spent. Otherwise the budget is spent (unless the
    caller already did), the message is checked and the check is stored under its hash.

    The indicators were found by fixed rules before the message was masked (`signals`); their
    `seen` is read when the answer is made (NF-SA-013 writes it).

    The similar-scam search starts with the classification and runs beside it; its answer is
    only returned, never given to the classifier. It cannot fail the check.

    The explainer is written after the verdict, in the worker's language. If it cannot be made
    the worker still gets the verdict, with `explainer_status: "unavailable"`.
    """
    key = cache_key(redacted_text, language)
    lookup = await store.lookup(uid, key, taxonomy.version, datetime.now(UTC))
    if lookup.hit is not None:
        logger.info("scam_cache result=hit input=%s", input_type)
        log_cache_lookup("scam", "check", hit=True)
        return await store.serve_hit(uid, lookup.hit, datetime.now(UTC))
    if charge_budget:
        _charge_hourly_budget(uid)
    logger.info("scam_cache result=miss input=%s", input_type)
    log_cache_lookup("scam", "check", hit=False)
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
    # An older check of this message that could not be served (an old prompt, no explainer) is
    # replaced, but whether the worker already warned others stays true.
    report_id = (lookup.previous or {}).get("reported_report_id")
    indicators = await store.with_seen(_indicators(sender, signals))
    response = ScamAnalyzeResponse(
        id=check_id_for(key),
        cached=False,
        input_type=input_type,
        language=language,
        message_language=result.message_language,
        redacted_text=redacted_text,
        corridor_id=corridor_id,
        verdict=result.verdict,
        details=result.details,
        indicators=indicators,
        explainer=explainer,
        explainer_status="ready" if explainer else "unavailable",
        similar=[
            SimilarScam(source=m.source, scam_type=m.scam_type, score=m.score)
            for m in retrieval.similar
        ],
        corridor_report_count=retrieval.corridor_report_count,
        reported=report_id is not None,
        report_id=report_id,
        created_at=now,
        expires_at=now + CHECK_TTL,
    )
    await store.save(
        uid, key, response, taxonomy_version=taxonomy.version, previous=lookup.previous, now=now
    )
    return response


def _indicators(sender: ScamIndicator | None, signals: Signals) -> list[ScamIndicator]:
    """The sender a screenshot shows first, then what was found in the text; no repeats, at most
    ten (the contract's limit)."""
    merged: dict[str, ScamIndicator] = {}
    for indicator in ([sender] if sender else []) + signals.indicators:
        merged.setdefault(indicator.id, indicator)
    return list(merged.values())[:MAX_INDICATORS]


async def analyze_text(
    request: ScamAnalyzeTextRequest,
    uid: str,
    gemini: GeminiClient,
    taxonomy_repo: ScamTaxonomyRepository,
    finder: SimilarScamFinder,
    store: CheckStore,
) -> ScamAnalyzeResponse:
    """Check one pasted message and answer in the shape of the v2 contract.

    Args:
        request: The validated body; `text` is the message as received.
        uid: The signed-in worker: whose checks are looked up and stored, and whose budget is spent.
        gemini: Client for the classification-tier call.
        taxonomy_repo: Where the scam types and tactics the model may name are read.
        finder: The neighbour search over known scams and Radar reports.
        store: The worker's stored checks, which answer a repeated message.

    Raises:
        TaxonomyNotLoadedError: No taxonomy in Firestore.
        GeminiError: Any Gemini failure, left for the API error handlers.
        HTTPException: 429 when the worker has used the hourly budget and the message is new.
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
        uid=uid,
        store=store,
        charge_budget=True,
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
    uid: str,
    gemini: GeminiClient,
    taxonomy_repo: ScamTaxonomyRepository,
    finder: SimilarScamFinder,
    store: CheckStore,
) -> ScamAnalyzeResponse:
    """Read a screenshot of a message, then check it exactly as pasted text is checked.

    The image is only held in memory for this call. The text read from it is masked before
    anything else sees it, and a sender it shows becomes an indicator of kind `sender`.

    Args:
        image: The uploaded file, already known to be a JPEG, PNG or WebP of at most 5 MB.
        fields: The form's `language` and `corridor_id`.
        uid: The signed-in worker, as for `analyze_text`.
        gemini: Client for the Vision call and the classification call.
        taxonomy_repo: Where the scam types and tactics the model may name are read.
        finder: The neighbour search over known scams and Radar reports.
        store: The worker's stored checks, which answer a repeated message.

    Raises:
        ImageUnreadableError: The file cannot be decoded, or shows no message text.
        TaxonomyNotLoadedError: No taxonomy in Firestore.
        GeminiError: Any Gemini failure, left for the API error handlers.
        HTTPException: 429 when the worker has used the hourly budget.
    """
    # Before the Vision call, so a server that cannot finish the check does not spend quota.
    taxonomy = await _load_taxonomy(taxonomy_repo)
    # A screenshot always calls Gemini (Vision reads it before there is any text to look up), so
    # it spends the hourly budget even if the text then matches a stored check.
    _charge_hourly_budget(uid)
    message = await read_screenshot_message(image, gemini)
    # A screenshot cannot be asked to be shorter, so a long conversation is cut here (after
    # masking, which can lengthen a short number) rather than refused.
    redacted_text = redact_text(message.text)[:MAX_TEXT_CHARS].strip()
    signals = extract_signals(message.text, redacted_text, corridor_id=fields.corridor_id)
    return await _check_message(
        redacted_text,
        uid=uid,
        store=store,
        charge_budget=False,
        input_type="screenshot",
        language=fields.language,
        corridor_id=fields.corridor_id,
        signals=signals,
        sender=message.sender,
        taxonomy=taxonomy,
        gemini=gemini,
        finder=finder,
    )
