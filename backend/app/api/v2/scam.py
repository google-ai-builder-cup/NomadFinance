from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user, require_flag
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.scam_taxonomy_repo import (
    ScamTaxonomyRepository,
    get_scam_taxonomy_repository,
)
from app.schemas.scam import ScamAnalyzeResponse, ScamAnalyzeTextRequest
from app.schemas.user import AuthenticatedUser
from app.services.scam.analyzer import analyze_text

# The flag guard also verifies the token, so a missing token is a 401 before anything else
# and a caller without the flag gets the same 404 an unknown path does (docs/api/v2-scam.md).
router = APIRouter(prefix="/scam", tags=["scam"], dependencies=[Depends(require_flag("scam"))])

_ANALYZE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    404: {"description": "The `scam` flag is off for the caller"},
    422: {"description": "Empty text, text over 4,000 characters, or a language outside the six"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/analyze",
    response_model=ScamAnalyzeResponse,
    responses=_ANALYZE_RESPONSES,
    summary="Check a pasted message for a scam",
    dependencies=[Depends(limit_ai_calls)],
)
async def analyze_scam_message(
    body: ScamAnalyzeTextRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    taxonomy_repo: Annotated[ScamTaxonomyRepository, Depends(get_scam_taxonomy_repository)],
) -> ScamAnalyzeResponse:
    """Say whether a message is a scam, of which type, how risky, and which words gave it away.

    The message is masked (phone numbers, emails, IDs, accounts, links) before anything else
    happens, and only the masked text is returned. Its content is data: instructions inside it
    are never followed. The explainer, indicators and similar scams are not filled yet
    (`explainer_status` is `unavailable`), and nothing is stored.
    """
    return await analyze_text(body, gemini, taxonomy_repo)
