from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.dependencies import require_cloud_scheduler
from app.integrations.fx import FxRouter, get_fx_router
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.schemas.remittance import RefreshRatesResponse
from app.services.remittance.rates import refresh_rates

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
