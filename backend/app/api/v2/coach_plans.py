"""The Financial Coach's plan routes (NF-FC-012): make the 90-day plan, and read it.

`POST /coach/sessions/{id}/plan` finds the plan by the hash of the answers or makes it (the
figures in code, the sentences by Gemini, checked). The PDF and other languages are NF-FC-014's:
until then a plan is returned in English.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response

from app.core.errors import ApiError
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_coach_plans, get_current_user, require_flag
from app.schemas.coach_plan import CoachPlanResponse
from app.schemas.coach_session import CoachPlanRequest
from app.schemas.contract import ReportLanguage
from app.schemas.user import AuthenticatedUser
from app.services.coach.plan_service import (
    CoachPlans,
    PlanInProgressError,
    PlanNotFoundError,
    PlanNotReadyError,
)
from app.services.coach.scoring_inputs import ScoreUnavailableError
from app.services.coach.session_types import SessionNotActiveError, SessionNotFoundError

router = APIRouter(prefix="/coach", tags=["coach"], dependencies=[Depends(require_flag("coach"))])

_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_PLAN_ID = re.compile(r"^[0-9a-f]{20}$")
_COMMON: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    404: {"description": "The `coach` flag is off, or no such session or plan of the caller's"},
    429: {"description": "Too many requests; see Retry-After"},
}


@router.post(
    "/sessions/{session_id}/plan",
    response_model=CoachPlanResponse,
    status_code=201,
    dependencies=[Depends(limit_ai_calls)],
    responses={
        **_COMMON,
        200: {"model": CoachPlanResponse, "description": "The plan already existed"},
        409: {
            "description": "`plan_not_ready`, `session_not_active` or `request_in_progress` "
            "(the last sends `Retry-After: 5`)"
        },
        422: {"description": "A language outside the six"},
        502: {"description": "The plan's sentences were unusable twice (`ai_bad_response`)"},
        503: {
            "description": "`score_unavailable` (a rate or cost baseline is missing), `ai_busy` "
            "or `ai_unavailable`; sends `Retry-After`"
        },
        504: {"description": "Gemini timed out (`ai_timeout`)"},
    },
    summary="Make the 90-day plan from the confirmed answers",
)
async def create_coach_plan(
    session_id: str,
    body: CoachPlanRequest,
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    plans: Annotated[CoachPlans, Depends(get_coach_plans)],
) -> CoachPlanResponse:
    """The plan is found by the hash of the answers, so asking again returns the same plan
    (200). A new plan takes 20 to 40 seconds (201). Only English exists for now: `language` is
    accepted and the plan comes back in English (`language: "en"`) until translation is built."""
    if not _SESSION_ID.match(session_id):
        raise ApiError(404, "not_found", "Not Found")
    try:
        result = await plans.create(user.uid, session_id, datetime.now(UTC))
    except SessionNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc
    except SessionNotActiveError as exc:
        raise ApiError(409, "session_not_active", "This interview has ended.") from exc
    except PlanNotReadyError as exc:
        raise ApiError(
            409, "plan_not_ready", "Confirm your answers before the plan is made."
        ) from exc
    except PlanInProgressError as exc:
        raise ApiError(
            409,
            "request_in_progress",
            "Your plan is being made. Try again in a moment.",
            headers={"Retry-After": "5"},
        ) from exc
    except ScoreUnavailableError as exc:
        raise ApiError(
            503,
            "score_unavailable",
            "The plan cannot be made right now. Please try again later.",
            headers={"Retry-After": "30"},
        ) from exc
    response.status_code = 201 if result.created else 200
    return result.response


@router.get(
    "/plans/{plan_id}",
    response_model=CoachPlanResponse,
    responses={**_COMMON, 422: {"description": "A language outside the six"}},
    summary="One stored plan",
)
async def get_coach_plan(
    plan_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    plans: Annotated[CoachPlans, Depends(get_coach_plans)],
    language: Annotated[ReportLanguage, Query()] = "en",
) -> CoachPlanResponse:
    """A stored plan. Another worker's plan and a missing one are the same `404`. Until
    translation is built (NF-FC-014) every language returns the English plan."""
    if not _PLAN_ID.match(plan_id):
        raise ApiError(404, "not_found", "Not Found")
    try:
        return await plans.get(user.uid, plan_id, datetime.now(UTC))
    except PlanNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc
