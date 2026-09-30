from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.corridor_repo import CorridorRepository, get_corridor_repository
from app.repositories.fib_repo import FibRepository, get_fib_repository
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.schemas.remittance_compare import (
    CorridorId,
    RemittanceCompareRequest,
    RemittanceComparison,
)
from app.schemas.remittance_log import TransferLogRequest, TransferLogResponse
from app.schemas.remittance_recommend import RemittanceRecommendation, RemittanceRecommendRequest
from app.schemas.remittance_trends import RemittanceTrends, TrendDays
from app.schemas.user import AuthenticatedUser
from app.services.remittance.engine import (
    AmountOutOfRangeError,
    CorridorNotFoundError,
    compare_remittance,
)
from app.services.remittance.logger import ProviderNotInComparisonError, log_transfer
from app.services.remittance.recommender import (
    RecommendationIncompleteError,
    generate_recommendation,
)
from app.services.remittance.trends import HistoryNotFoundError, get_trends

router = APIRouter(prefix="/remittance", tags=["remittance"])

_COMPARE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No prices are loaded for this corridor yet"},
    422: {"description": "Unknown corridor, or an amount outside the range that can be compared"},
    429: {"description": "Too many requests (default 60 a minute); see Retry-After"},
}


@router.post(
    "/compare",
    response_model=RemittanceComparison,
    responses=_COMPARE_ERROR_RESPONSES,
    summary="Compare what every service costs for a corridor and an amount",
)
async def compare_remittance_options(
    body: RemittanceCompareRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    corridors: Annotated[CorridorRepository, Depends(get_corridor_repository)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
) -> RemittanceComparison:
    """Rank the surveyed ways to send money home by what the recipient receives. Steps 1 to 6.

    Send the `corridor_id` (for example `SG-PH`) and the `amount` in the sending currency. Each
    service's fee and rate markup come from the World Bank's Remittance Prices Worldwide survey
    (a published survey, not a live price list); the mid-market rate is the cron's latest. The
    result carries the survey period and the attribution the World Bank requires wherever the
    prices are shown. No Gemini call, so only the API-wide rate limit applies.
    """
    try:
        return await compare_remittance(
            body.corridor_id, body.amount, corridors, rates, datetime.now(UTC)
        )
    except CorridorNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No prices are available yet for {body.corridor_id}.",
        ) from exc
    except AmountOutOfRangeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Enter an amount between {exc.minimum:,.2f} and {exc.maximum:,.2f} {exc.currency}.",
        ) from exc


_TRENDS_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No rate history is stored for this corridor yet"},
    422: {"description": "Unknown corridor, or days not one of 30, 90, 180, 365"},
    429: {"description": "Too many requests (default 60 a minute); see Retry-After"},
}


@router.get(
    "/trends",
    response_model=RemittanceTrends,
    responses=_TRENDS_ERROR_RESPONSES,
    summary="Mid-market rate history of a corridor, and the best weekday to send",
)
async def remittance_trends(
    corridor_id: Annotated[CorridorId, Query(description="For example SG-PH")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
    days: Annotated[
        TrendDays, Query(description="Period of the points: 30, 90, 180 or 365")
    ] = TrendDays.QUARTER,
) -> RemittanceTrends:
    """One mid-market rate per market day for the chart, a summary, and the best day to send.
    Steps 4 and 7.

    The rates are the European Central Bank's reference rates (via Frankfurter), backfilled for
    past days and kept up by the rate cron; `providers` names any other source used. The best
    day compares each weekday with its own week over the last 52 weeks, and stays null with a
    reason when the history is too short or no weekday is reliably better. One Firestore read,
    no Gemini call, so only the API-wide rate limit applies.
    """
    try:
        return await get_trends(corridor_id, days, rates, datetime.now(UTC).date())
    except HistoryNotFoundError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No rate history is available yet for {corridor_id}.",
        ) from exc


_RECOMMEND_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "The comparison has no ranked provider, or an invalid body"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/recommend",
    response_model=RemittanceRecommendation,
    responses=_RECOMMEND_ERROR_RESPONSES,
    summary="Write a short, personal recommendation from a finished comparison",
    dependencies=[Depends(limit_ai_calls)],
)
async def recommend_remittance_option(
    body: RemittanceRecommendRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> RemittanceRecommendation:
    """Explain the comparison in one headline and a few sentences. Step 9.

    Send the unmodified body of `/remittance/compare` as `comparison`, the body of
    `/remittance/trends` as `trend` if you have it (for the timing tip; omit it otherwise),
    and `target_language`. `recommended_rpw_id` and `recommended_firm` are always the
    comparison's own top-ranked provider, never a name Gemini chose; the recommendation is
    rejected as unusable if it names a different one. Nothing is stored.
    """
    try:
        return await generate_recommendation(
            body.comparison, body.trend, body.target_language, gemini
        )
    except RecommendationIncompleteError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI service returned an unusable answer. Please try again.",
        ) from exc


_LOG_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "Invalid body, or rpw_id is not a comparable, ranked provider"},
    429: {"description": "Too many requests (default 60 a minute); see Retry-After"},
}


@router.post(
    "/log",
    status_code=status.HTTP_201_CREATED,
    response_model=TransferLogResponse,
    responses=_LOG_ERROR_RESPONSES,
    summary="Log a transfer the worker actually sent",
)
async def log_remittance_transfer(
    body: TransferLogRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    transfers: Annotated[FibRepository, Depends(get_fib_repository)],
) -> TransferLogResponse:
    """Store a completed transfer under `users/{uid}/transfers`, feeding Financial Identity.

    Send the unmodified body of `/remittance/compare` as `comparison`, plus the `rpw_id` of the
    service the worker actually used (and optionally `entry_date`, `notes`). Every amount
    stored is read from that provider's own row in the comparison, never typed freely by the
    client — the same reasoning `/remittance/recommend` uses to never trust a provider name
    Gemini wrote over the comparison's own top-ranked one. No Gemini call, so only the
    API-wide rate limit applies.
    """
    try:
        return await log_transfer(user.uid, body, transfers, datetime.now(UTC))
    except ProviderNotInComparisonError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "rpw_id is not a comparable, ranked provider of the comparison sent.",
        ) from exc
