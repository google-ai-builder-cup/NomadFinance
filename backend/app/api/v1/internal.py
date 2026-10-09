from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.dependencies import get_feature_flag_service, require_cloud_scheduler
from app.integrations.fx import FxRouter, get_fx_router
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.coach_session_repo import CoachPlanRepository, get_coach_plan_repository
from app.repositories.fib_repo import FibRepository, get_fib_repository
from app.repositories.radar_repo import RadarRepository, get_radar_repository
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.repositories.scam_stats_repo import ScamStatsRepository, get_scam_stats_repository
from app.repositories.user_repo import UserRepository, get_user_repository
from app.schemas.coach_checkin import SendCheckinsResponse
from app.schemas.fib_profile import RecomputeResponse
from app.schemas.radar_alert import AggregateRadarResponse
from app.schemas.remittance import RefreshRatesResponse
from app.schemas.scam_stats import AggregateScamStatsResponse
from app.services.coach.checkin_job import send_checkins
from app.services.feature_flag_service import FeatureFlagService
from app.services.fib.profile_builder import recompute_all
from app.services.radar.alerts import run_aggregation
from app.services.remittance.rates import refresh_rates
from app.services.scam.stats import run_scam_stats

# Called by Cloud Scheduler only (infra/cloud-scheduler/). Hidden from the public API docs,
# and never rate limited (RateLimitMiddleware skips /api/v1/internal/).
router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Google OIDC token"},
    403: {"description": "Token is not from the Cloud Scheduler service account"},
    503: {"description": "Some pairs failed on every provider, or internal auth not configured"},
}


@router.post("/refresh-rates", response_model=RefreshRatesResponse, responses=_RESPONSES)
async def refresh_rates_endpoint(
    _caller: Annotated[str, Depends(require_cloud_scheduler)],
    fx: Annotated[FxRouter, Depends(get_fx_router)],
    repo: Annotated[RateRepository, Depends(get_rate_repository)],
) -> JSONResponse:
    """Refresh the six corridor FX rates in rates_cache and rates_history."""
    result = await refresh_rates(fx=fx, repo=repo, now=datetime.now(UTC))
    # A non-2xx makes Cloud Scheduler log a failed run and retry, which is what a partial
    # refresh should trigger. The pairs that did succeed are already saved.
    code = status.HTTP_200_OK if not result.failed else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(result.model_dump(mode="json"), status_code=code)


@router.post("/aggregate-radar", response_model=AggregateRadarResponse, responses=_RESPONSES)
async def aggregate_radar_endpoint(
    _caller: Annotated[str, Depends(require_cloud_scheduler)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> AggregateRadarResponse:
    """AGG subgraph of the radar pipeline (NF-P3-004): detect surges, alert, expire, notify.

    Always 200: a failure on one corridor or one recipient is caught and logged inside
    `run_aggregation` itself, never left to make Cloud Scheduler retry the whole run.
    """
    return await run_aggregation(radar, users, gemini, datetime.now(UTC))


@router.post("/recompute-fib-profiles", response_model=RecomputeResponse, responses=_RESPONSES)
async def recompute_fib_profiles_endpoint(
    _caller: Annotated[str, Depends(require_cloud_scheduler)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> RecomputeResponse:
    """Weekly Financial Identity recompute (NF-P3-013): metrics and narrative per user.

    Always 200: a failure for one user is caught and logged inside `recompute_all`, and that
    user keeps the previous profile. A retry would run (and pay for) every other user again.
    """
    return await recompute_all(gemini, fib, users, rates, datetime.now(UTC))


@router.post(
    "/aggregate-scam-stats", response_model=AggregateScamStatsResponse, responses=_RESPONSES
)
async def aggregate_scam_stats_endpoint(
    _caller: Annotated[str, Depends(require_cloud_scheduler)],
    stats: Annotated[ScamStatsRepository, Depends(get_scam_stats_repository)],
) -> JSONResponse:
    """Weekly Scam Analyzer counts per corridor and type for the current and previous ISO week
    (NF-SA-022), written to `scam_stats/{corridor}/weeks/{iso_week}`: counts only.

    A week that could not be read or written makes the answer a 503, so Cloud Scheduler logs a
    failed run and retries. Repeating is harmless: every run replaces what it writes.
    """
    result, complete = await run_scam_stats(stats, datetime.now(UTC))
    code = status.HTTP_200_OK if complete else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(result.model_dump(mode="json"), status_code=code)


@router.post("/send-coach-checkins", response_model=SendCheckinsResponse, responses=_RESPONSES)
async def send_coach_checkins_endpoint(
    _caller: Annotated[str, Depends(require_cloud_scheduler)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    flags: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> JSONResponse:
    """Daily Coach check-in reminders for plans 30, 60 and 90 days past departure (NF-FC-016).

    A plan or a query that could not be read or written makes the answer a 503, so Cloud
    Scheduler logs a failed run and retries. Repeating is harmless: a reminder already written
    for a plan and milestone is never written or pushed again.
    """
    result, complete = await send_checkins(plans, users, flags, datetime.now(UTC))
    code = status.HTTP_200_OK if complete else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(result.model_dump(mode="json"), status_code=code)
