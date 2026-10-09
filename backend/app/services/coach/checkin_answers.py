"""A worker's answers to a Coach check-in (NF-FC-022): kept on the plan, the first time only.

The reminder (checkin_job.py) writes `checkins.<milestone>.due_on` and `notified_at`; this writes
`answers` and `answered_at` next to them. Nothing here calls a model.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi.concurrency import run_in_threadpool

from app.repositories.coach_session_repo import CoachPlanRepository
from app.schemas.coach_checkin import (
    CheckinAnswerResponse,
    CheckinAnswers,
    Milestone,
)
from app.services.coach.checkin_job import MILESTONES
from app.services.coach.plan_service import PlanNotFoundError


class CheckinNotDueError(RuntimeError):
    """The plan has no departure date, or the day of this check-in has not come."""


def _is_due(departure: object, milestone: str, today: date) -> bool:
    if not isinstance(departure, str):
        return False
    try:
        due_on = date.fromisoformat(departure) + timedelta(days=MILESTONES[milestone])
    except ValueError:
        return False
    # The job runs at 02:00 UTC and reminds on the due date itself, so a worker who opens the
    # link has always reached this date in UTC.
    return today >= due_on


async def answer_checkin(
    plans: CoachPlanRepository,
    uid: str,
    plan_id: str,
    milestone: Milestone,
    answers: CheckinAnswers,
    now: datetime,
) -> CheckinAnswerResponse:
    """Store the answers of one milestone, or return the ones stored by an earlier call.

    Raises:
        PlanNotFoundError: No such plan for this worker.
        CheckinNotDueError: The milestone's day has not come, or the plan has no departure date.
        SessionContentionError: Too many requests were writing the plan at once; retry.
    """
    state = await run_in_threadpool(plans.checkin_state, uid, plan_id)
    if state is None:
        raise PlanNotFoundError(plan_id)
    if not _is_due(state.get("departure_date"), milestone, now.date()):
        raise CheckinNotDueError(milestone)
    stored = await run_in_threadpool(
        plans.answer_checkin, uid, plan_id, milestone, answers.model_dump(), now
    )
    if stored is None:
        raise PlanNotFoundError(plan_id)
    kept, answered_at, stored_now = stored
    return CheckinAnswerResponse(
        plan_id=plan_id,
        milestone=milestone,
        answers=CheckinAnswers.model_validate(kept),
        answered_at=answered_at,
        already_answered=not stored_now,
    )
