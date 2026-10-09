"""The dashboard card's view of a worker's Coach (NF-FC-008): reads only, changes nothing."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.repositories.coach_session_repo import CoachPlanRepository, CoachSessionRepository
from app.schemas.coach_questions import QuestionBank
from app.schemas.coach_session import CoachOverview, OverviewPlan, OverviewSession
from app.services.coach.session_document import expired, idle, to_session


async def build_overview(
    sessions: CoachSessionRepository,
    plans: CoachPlanRepository,
    bank: QuestionBank,
    uid: str,
    now: datetime,
) -> CoachOverview:
    """The active session (one that has gone idle or expired is left out) and the newest plan."""
    session = None
    for session_id, document in await run_in_threadpool(sessions.active, uid):
        if idle(document, now) or expired(document, now):
            continue
        view = to_session(session_id, document, bank)
        session = OverviewSession(
            id=session_id,
            stage=view.stage,
            language=view.language,
            turn_count=view.turn_count,
            last_active=view.last_active,
        )
        break
    newest = await run_in_threadpool(plans.newest, uid)
    return CoachOverview(session=session, plan=_plan_of(newest))


def _plan_of(newest: tuple[str, dict[str, Any]] | None) -> OverviewPlan | None:
    if newest is None:
        return None
    plan_id, plan = newest
    return OverviewPlan(
        id=plan_id,
        created_at=plan["created_at"],
        score_total=plan["score"]["total"],
        band=plan["score"]["band"],
        departure_date=plan.get("departure_date"),
    )
