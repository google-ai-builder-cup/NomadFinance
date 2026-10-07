from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.concurrency import run_in_threadpool

from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient
from app.repositories.scam_taxonomy_repo import ScamTaxonomyRepository
from app.schemas.scam import ScamAnalyzeResponse, ScamAnalyzeTextRequest
from app.services.scam.classifier import classify_message

logger = logging.getLogger(__name__)

# `expires_at` of a stored check: 90 days after it was last checked (scam.md).
_CHECK_TTL = timedelta(days=90)


class TaxonomyNotLoadedError(RuntimeError):
    """`scam_taxonomy` is empty: the data-scripts loader (NF-SA-001) has not run here."""


async def analyze_text(
    request: ScamAnalyzeTextRequest, gemini: GeminiClient, taxonomy_repo: ScamTaxonomyRepository
) -> ScamAnalyzeResponse:
    """Check one pasted message and answer in the shape of the v2 contract.

    Only the verdict part is real so far (NF-SA-007). The parts other tasks own come back as
    the contract's "not available yet" values: no indicators (NF-SA-011), no explainer
    (NF-SA-009), no similar scams (NF-SA-010), and nothing is stored or cached (NF-SA-012),
    so `id` identifies this answer only.

    Args:
        request: The validated body; `text` is the message as received.
        gemini: Client for the classification-tier call.
        taxonomy_repo: Where the scam types and tactics the model may name are read.

    Raises:
        TaxonomyNotLoadedError: No taxonomy in Firestore.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    # The raw text goes no further than this line: the model, the answer and the logs only
    # ever see the masked one.
    redacted_text = redact_text(request.text)
    taxonomy = await run_in_threadpool(taxonomy_repo.get_taxonomy)
    if taxonomy is None:
        raise TaxonomyNotLoadedError("scam_taxonomy has no types or tactics")

    result = await classify_message(redacted_text, taxonomy, gemini)
    logger.info(
        "scam_classified is_scam=%s scam_type=%s risk=%s confidence=%.2f taxonomy_version=%d",
        result.verdict.is_scam,
        result.verdict.scam_type,
        result.verdict.risk_level,
        result.verdict.confidence,
        taxonomy.version,
    )

    now = datetime.now(UTC)
    return ScamAnalyzeResponse(
        id=uuid.uuid4().hex,
        cached=False,
        input_type="text",
        language=request.language,
        message_language=result.message_language,
        redacted_text=redacted_text,
        corridor_id=request.corridor_id,
        verdict=result.verdict,
        details=result.details,
        indicators=[],
        explainer=None,
        explainer_status="unavailable",
        similar=[],
        corridor_report_count=None,
        reported=False,
        report_id=None,
        created_at=now,
        expires_at=now + _CHECK_TTL,
    )
