"""Every figure of the 90-day plan, worked out from the answers (NF-FC-012).

Pure and without a model: the plan's budget, goals, remittance schedule, debt paydown and
emergency fund are arithmetic on the worker's answers, the cost baselines and the stored rates, so
no figure in a plan can be one the model made up. The model only writes the sentences around them
(`plan_generator.py`), and `plan_validator.py` checks those sentences against these figures.

The rules (shares, the 3-month target, the send weeks) live in this module; changing one means
changing `PLAN_RULES_VERSION`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from app.schemas.coach_plan import (
    BudgetLine,
    DebtPlan,
    EmergencyFundPlan,
    MonthlyBudget,
    PlanMoney,
    ProviderQuote,
    RemittancePlan,
    RemittanceSend,
)
from app.schemas.coach_profile import Currency
from app.schemas.remittance_compare import CorridorId
from app.services.coach.scoring import HIGH_INTEREST_YEARLY, half_up

PLAN_RULES_VERSION = 1
EMERGENCY_MONTHS = 3
# Pay arrives at the end of the first month, so the first transfer is in week 5, then every four
# weeks (week 13 is the last of the plan).
SEND_WEEKS = (5, 9, 13)
# Shares of what is left after costs and the remittance. With a costly debt the debt comes first;
# the part not named stays as `left_over`.
DEBT_SHARE = 0.5
DEBT_SHARE_COSTLY = 0.7
FUND_SHARE_WITH_DEBT = 0.4
FUND_SHARE_COSTLY_DEBT = 0.25
FUND_SHARE_NO_DEBT = 0.8
WEEKS_PER_MONTH = 52 / 12
MAX_PAYOFF_MONTHS = 240


@dataclass(frozen=True)
class PlanInputs:
    """The answers and stored data in the host currency, as the plan reads them."""

    currency: Currency
    salary: float
    remittance: float
    recruitment_fee: float
    debt: float
    savings: float
    debt_rate_yearly_percent: float | None
    costs: tuple[tuple[str, float], ...]
    setup_costs: float
    fee_cap_months: float


@dataclass(frozen=True)
class Quote:
    """The cheapest provider Remittance X-Ray found for the monthly amount."""

    slug: str
    name: str
    fee: float
    receives: float
    receive_currency: Currency
    quoted_at: datetime


@dataclass(frozen=True)
class PlanFigures:
    budget: MonthlyBudget
    remittance: RemittancePlan
    debt: DebtPlan | None
    emergency_fund: EmergencyFundPlan

    @property
    def available(self) -> float:
        """What is left of the pay after costs and the remittance; negative is a gap."""
        budget = self.budget
        costs = sum(line.amount.amount for line in budget.costs)
        return round2(budget.income.amount - costs - self.remittance.monthly_amount.amount)


def round2(number: float) -> float:
    return half_up(number * 100) / 100


def monthly_rate_percent(yearly_percent: float | None) -> float:
    return 0.0 if yearly_percent is None else yearly_percent / 12


def months_to_clear(debt: float, payment: float, monthly_percent: float) -> int | None:
    """Months of `payment` to pay `debt` off, or None if the payment never beats the interest."""
    if debt <= 0:
        return None
    rate = monthly_percent / 100
    if payment <= 0 or (rate > 0 and payment <= debt * rate):
        return None
    balance = debt
    for month in range(1, MAX_PAYOFF_MONTHS + 1):
        balance = balance * (1 + rate) - payment
        if balance <= 0.005:
            return month
    return None


def weeks_to_target(target: float, savings: float, monthly_saving: float) -> int | None:
    """Weeks to reach `target` from `savings` at `monthly_saving`: 0 if met, None if never."""
    if savings >= target:
        return 0
    if monthly_saving <= 0:
        return None
    return math.ceil((target - savings) / monthly_saving * WEEKS_PER_MONTH)


def _goals(inputs: PlanInputs, available: float) -> tuple[float, float]:
    """The monthly debt payment and emergency saving, in whole units of the currency."""
    if available <= 0:
        return 0.0, 0.0
    if inputs.debt <= 0:
        return 0.0, float(math.floor(available * FUND_SHARE_NO_DEBT))
    yearly = inputs.debt_rate_yearly_percent or 0.0
    costly = yearly >= HIGH_INTEREST_YEARLY
    share = DEBT_SHARE_COSTLY if costly else DEBT_SHARE
    fund_share = FUND_SHARE_COSTLY_DEBT if costly else FUND_SHARE_WITH_DEBT
    # Never plan to pay more in a month than the whole debt with its interest.
    cap = math.ceil(inputs.debt * (1 + monthly_rate_percent(inputs.debt_rate_yearly_percent) / 100))
    return float(min(math.floor(available * share), cap)), float(math.floor(available * fund_share))


def compute_figures(
    inputs: PlanInputs, corridor_id: CorridorId | None, quote: Quote | None
) -> PlanFigures:
    """The plan's figures. `quote` is None without a corridor or when no price was available."""
    cur = inputs.currency

    def money(amount: float) -> PlanMoney:
        return PlanMoney(amount=round2(amount), currency=cur)

    cost_lines = [BudgetLine(id=name, amount=money(amount)) for name, amount in inputs.costs]
    costs_total = sum(line.amount.amount for line in cost_lines)
    remittance = round2(inputs.remittance)
    available = round2(inputs.salary - costs_total - remittance)
    debt_payment, saving = _goals(inputs, available)

    goals = [BudgetLine(id="remittance", amount=money(remittance))]
    if inputs.debt > 0:
        goals.append(BudgetLine(id="debt_payment", amount=money(debt_payment)))
    goals.append(BudgetLine(id="emergency_fund", amount=money(saving)))
    budget = MonthlyBudget(
        income=money(inputs.salary),
        costs=cost_lines,
        goals=goals,
        left_over=money(available - debt_payment - saving),
        setup_costs=money(inputs.setup_costs) if inputs.setup_costs > 0 else None,
    )

    debt: DebtPlan | None = None
    if inputs.debt > 0:
        months = months_to_clear(
            inputs.debt, debt_payment, monthly_rate_percent(inputs.debt_rate_yearly_percent)
        )
        debt = DebtPlan(
            outstanding=money(inputs.debt),
            monthly_payment=money(debt_payment),
            months_to_clear=months,
        )

    target = round2(EMERGENCY_MONTHS * costs_total)
    fund = EmergencyFundPlan(
        target=money(target),
        months_of_costs=EMERGENCY_MONTHS,
        monthly_saving=money(saving),
        weeks_to_target=weeks_to_target(target, inputs.savings, saving),
    )

    send = money(remittance)
    schedule = [RemittanceSend(week=week, amount=send) for week in SEND_WEEKS] if remittance else []
    provider = None
    if corridor_id is not None and quote is not None:
        net = remittance - quote.fee
        provider = ProviderQuote(
            slug=quote.slug,
            name=quote.name,
            fee=money(quote.fee),
            receives=PlanMoney(amount=round2(quote.receives), currency=quote.receive_currency),
            # The rate the worker effectively gets after the provider's margin: what arrives
            # divided by what is sent after the fee.
            fx_rate=round(quote.receives / net, 6) if net > 0 else 1.0,
            quoted_at=quote.quoted_at,
        )
    plan_remittance = RemittancePlan(
        corridor_id=corridor_id, monthly_amount=send, provider=provider, schedule=schedule
    )
    return PlanFigures(budget, plan_remittance, debt, fund)
