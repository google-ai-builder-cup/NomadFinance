from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from app.repositories.corridor_repo import CorridorRepository, get_corridor_repository
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.schemas.remittance_compare import (
    CorridorId,
    RemittanceCompareRequest,
    RemittanceComparison,
)
from app.schemas.remittance_trends import RemittanceTrends, TrendDays
from app.schemas.user import AuthenticatedUser
from app.services.remittance.engine import (
    AmountOutOfRangeError,
    CorridorNotFoundError,
    compare_remittance,
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
