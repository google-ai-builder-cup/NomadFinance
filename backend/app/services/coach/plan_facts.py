"""What the plan's sentences are about: the facts, the warnings and the checklist (NF-FC-012).

Code decides which warnings and checklist items a worker gets, and their severity, from the
figures; the model only words them. The facts here are the only numbers it is given, and
`plan_validator.py` allows no others.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.coach_plan import CoachScore, WarningSeverity
from app.schemas.coach_profile import AccountKind
from app.services.coach.plan_figures import (
    PlanFigures,
    PlanInputs,
    monthly_rate_percent,
    round2,
)
from app.services.coach.scoring import HIGH_INTEREST_YEARLY, VERY_HIGH_INTEREST_YEARLY

# What the worker is told in the checklist and why; the model words each in plain English.
CHECKLIST_ABOUT = {
    "keep_documents": "Keep copies of the contract, passport and any agent receipts together.",
    "open_pay_account": "Open a bank account that the employer can pay into.",
    "compare_transfer_providers": "Compare ways to send money home before each transfer.",
    "save_helpline_numbers": "Save the numbers of a worker support group and the embassy.",
    "track_spending": "Write down what is spent during the first month.",
    "keep_agent_receipts": "Keep every receipt for fees paid to the recruitment agent.",
    "pay_costly_debt_first": "Pay the costly debt before saving more.",
}
WARNING_ABOUT = {
    "fee_above_legal_limit": "The agent fee paid is above what the host country usually allows.",
    "high_interest_debt": "The debt costs a lot in interest.",
    "debt_not_covered": "The monthly payment does not cover the interest, so the debt never ends.",
    "budget_shortfall": "Costs and the planned remittance are more than the pay.",
    "thin_emergency_fund": "Savings are below the emergency-fund target.",
    "no_pay_account": "The worker has no bank account or wallet to be paid into.",
    "no_provider_quote": "The costs of sending money home cannot be compared yet.",
}


@dataclass(frozen=True)
class PlanContext:
    inputs: PlanInputs
    figures: PlanFigures
    score: CoachScore
    account: AccountKind
    job_type: str
    dependents: int | None
    departure_date: str | None


@dataclass(frozen=True)
class WarningSpec:
    id: str
    severity: WarningSeverity
    about: dict[str, Any]


def warnings_for(ctx: PlanContext) -> list[WarningSpec]:
    """The warnings this worker gets, most serious first."""
    inputs, figures = ctx.inputs, ctx.figures
    found: list[WarningSpec] = []
    limit = round2(inputs.fee_cap_months * inputs.salary)
    if inputs.recruitment_fee > limit + 0.005:
        found.append(
            WarningSpec(
                "fee_above_legal_limit",
                "urgent",
                {"fee_paid": round2(inputs.recruitment_fee), "usual_limit": limit},
            )
        )
    yearly = inputs.debt_rate_yearly_percent
    if inputs.debt > 0 and yearly is not None and yearly >= HIGH_INTEREST_YEARLY:
        severity: WarningSeverity = "urgent" if yearly >= VERY_HIGH_INTEREST_YEARLY else "warning"
        about = {
            "interest_percent_per_month": round2(monthly_rate_percent(yearly)),
            "interest_percent_per_year": round2(yearly),
        }
        found.append(WarningSpec("high_interest_debt", severity, about))
    if figures.debt is not None and figures.debt.months_to_clear is None:
        payment = figures.debt.monthly_payment.amount
        found.append(WarningSpec("debt_not_covered", "urgent", {"monthly_payment": payment}))
    if figures.available < 0:
        found.append(WarningSpec("budget_shortfall", "urgent", {"gap": -figures.available}))
    fund = figures.emergency_fund
    if inputs.savings < fund.target.amount:
        costs = sum(line.amount.amount for line in figures.budget.costs)
        thin: WarningSeverity = "warning" if inputs.savings < costs else "info"
        found.append(
            WarningSpec(
                "thin_emergency_fund",
                thin,
                {"savings": round2(inputs.savings), "target": fund.target.amount},
            )
        )
    if ctx.account == "none":
        found.append(WarningSpec("no_pay_account", "warning", {}))
    if figures.remittance.provider is None and figures.remittance.monthly_amount.amount > 0:
        found.append(WarningSpec("no_provider_quote", "info", {}))
    order = {"urgent": 0, "warning": 1, "info": 2}
    return sorted(found, key=lambda spec: order[spec.severity])


def checklist_ids(ctx: PlanContext) -> list[str]:
    ids = ["keep_documents"]
    if ctx.account in ("none", "mobile_wallet"):
        ids.append("open_pay_account")
    if ctx.inputs.recruitment_fee > 0:
        ids.append("keep_agent_receipts")
    yearly = ctx.inputs.debt_rate_yearly_percent
    if ctx.inputs.debt > 0 and yearly is not None and yearly >= HIGH_INTEREST_YEARLY:
        ids.append("pay_costly_debt_first")
    ids += ["compare_transfer_providers", "save_helpline_numbers", "track_spending"]
    return ids


def build_facts(ctx: PlanContext) -> dict[str, Any]:
    """Every number the sentences may use, with what each is."""
    figures, inputs = ctx.figures, ctx.inputs
    budget = figures.budget
    remittance = figures.remittance
    provider = remittance.provider
    facts: dict[str, Any] = {
        "currency": inputs.currency,
        "worker": {
            "job_type": ctx.job_type,
            "dependents": ctx.dependents,
            "departure_date": ctx.departure_date,
            "account": ctx.account,
            "savings_now": round2(inputs.savings),
        },
        "monthly_budget": {
            "income": budget.income.amount,
            "costs": {line.id: line.amount.amount for line in budget.costs},
            "goals": {line.id: line.amount.amount for line in budget.goals},
            "left_over": budget.left_over.amount,
            "first_month_setup_costs": budget.setup_costs.amount if budget.setup_costs else 0,
        },
        "remittance": {
            "corridor": remittance.corridor_id,
            "monthly_amount": remittance.monthly_amount.amount,
            "send_in_weeks": [send.week for send in remittance.schedule],
            "cheapest_provider": (
                None
                if provider is None
                else {
                    "name": provider.name,
                    "fee": provider.fee.amount,
                    "family_receives": provider.receives.amount,
                    "family_receives_currency": provider.receives.currency,
                }
            ),
        },
        "debt": (
            None
            if figures.debt is None
            else {
                "outstanding": figures.debt.outstanding.amount,
                "monthly_payment": figures.debt.monthly_payment.amount,
                "months_to_clear": figures.debt.months_to_clear,
            }
        ),
        "emergency_fund": {
            "target": figures.emergency_fund.target.amount,
            "months_of_costs": figures.emergency_fund.months_of_costs,
            "monthly_saving": figures.emergency_fund.monthly_saving.amount,
            "weeks_to_target": figures.emergency_fund.weeks_to_target,
        },
        "readiness_score": {"total": ctx.score.total, "band": ctx.score.band},
        "timeline": {"arrival_week": 1, "first_pay_week": 4},
    }
    for spec in warnings_for(ctx):
        facts.setdefault("warning_facts", {})[spec.id] = spec.about
    return facts
