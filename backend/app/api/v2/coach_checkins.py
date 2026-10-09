"""The answers to a Coach check-in (NF-FC-022): one `PUT` per plan and milestone.

The reminder that opens the check-in is the daily job of NF-FC-016. The three questions and their
choices are the screen's; this route stores the choice (`CheckinAnswers`) on the plan.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.errors import ApiError
from app.dependencies import get_current_user, require_flag
from app.repositories.coach_session_repo import (
    CoachPlanRepository,
    SessionContentionError,
    get_coach_plan_repository,
)
from app.schemas.coach_checkin import CheckinAnswerRequest, CheckinAnswerResponse, Milestone
from app.schemas.user import AuthenticatedUser
from app.services.coach.checkin_answers import CheckinNotDueError, answer_checkin
from app.services.coach.plan_service import PlanNotFoundError

router = APIRouter(prefix="/coach", tags=["coach"], dependencies=[Depends(require_flag("coach"))])

_PLAN_ID = re.compile(r"^[0-9a-f]{20}$")


@router.put(
    "/plans/{plan_id}/checkins/{milestone}",
    response_model=CheckinAnswerResponse,
    responses={
        401: {"description": "Missing, invalid, expired or revoked token"},
        404: {"description": "The `coach` flag is off, or no such plan of the caller's"},
        409: {
            "description": "`checkin_not_due` (the day has not come, or the plan has no departure "
            "date) or `request_in_progress` (sends `Retry-After: 2`)"
        },
        422: {
            "description": "A milestone other than d30, d60 or d90, or an answer outside the list"
        },
        429: {"description": "Too many requests; see Retry-After"},
    },
    summary="Answer the three questions of a day 30, 60 or 90 check-in",
)
async def put_coach_checkin(
    plan_id: str,
    milestone: Milestone,
    body: CheckinAnswerRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
) -> CheckinAnswerResponse:
    """Stores the answers once per milestone: a second call, from a second tap or another phone,
    changes nothing and gets the stored answers back with `already_answered: true`."""
    if not _PLAN_ID.match(plan_id):
        raise ApiError(404, "not_found", "Not Found")
    try:
        return await answer_checkin(
            plans, user.uid, plan_id, milestone, body.answers, datetime.now(UTC)
        )
    except PlanNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc
    except CheckinNotDueError as exc:
        raise ApiError(409, "checkin_not_due", "This check-in is not open yet.") from exc
    except SessionContentionError as exc:
        raise ApiError(
            409,
            "request_in_progress",
            "Your answers are being saved. Try again in a moment.",
            headers={"Retry-After": "2"},
        ) from exc
