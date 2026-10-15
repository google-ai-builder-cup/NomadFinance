from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.repositories.public_stats_repo import PublicStatsRepository, get_public_stats_repository
from app.schemas.public_stats import PublicStatsResponse
from app.services.public_stats import CACHE_SECONDS, get_public_stats

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/stats", response_model=PublicStatsResponse)
async def public_stats_endpoint(
    response: Response,
    stats: Annotated[PublicStatsRepository, Depends(get_public_stats_repository)],
) -> PublicStatsResponse:
    """Platform-wide totals for the landing page. Public: no sign-in, counts only, no worker data.

    Only the API-wide rate limit applies (by IP, there being no user); the answer is cached for
    five minutes here and by the browser.
    """
    response.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return await get_public_stats(stats)
