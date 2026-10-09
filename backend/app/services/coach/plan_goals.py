"""The plan's targets as goals the Financial Identity Builder tracks (NF-FC-015).

When a plan is made its targets go into `users/{uid}/financial_profile/current.goals`
(`docs/data-model/collections/fib.md`). Nothing here is a new figure: each is taken from the plan
(the savings rate is the plan's emergency saving over the plan's income), so the goals can never
disagree with the plan the worker was shown.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.repositories.coach_session_repo import CoachPlanRepository
from app.schemas.coach_plan import CoachPlan

GoalsSource = Callable[[str], dict[str, Any] | None]


def goals_for(plan_id: str, plan: CoachPlan, now: datetime) -> dict[str, Any]:
    """`{plan_id, savings_rate_target_pct, remittance, emergency_fund_target, set_at}`."""
    income = plan.monthly_budget.income.amount
    saving = plan.emergency_fund.monthly_saving.amount
    rate = round(saving / income * 100, 1) if income > 0 else 0.0
    remittance = plan.remittance.monthly_amount
    target = plan.emergency_fund.target
    return {
        "plan_id": plan_id,
        "savings_rate_target_pct": rate,
        "remittance": {
            "amount": remittance.amount,
            "currency": remittance.currency,
            "cadence": "monthly",
        },
        "emergency_fund_target": {"amount": target.amount, "currency": target.currency},
        "set_at": now,
    }


def newest_plan_goals(plans: CoachPlanRepository) -> GoalsSource:
    """The goals of the worker's newest plan, for a profile built after the plan was made.
    Blocking: call it in a thread."""

    def source(uid: str) -> dict[str, Any] | None:
        newest = plans.newest(uid)
        if newest is None:
            return None
        plan_id, document = newest
        created = document.get("created_at")
        if "plan" not in document or not isinstance(created, datetime):
            return None
        return goals_for(plan_id, CoachPlan.model_validate(document["plan"]), created)

    return source
