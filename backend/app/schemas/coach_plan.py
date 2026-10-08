"""Score and 90-day plan models of the Financial Coach API (NF-FC-002).

These are the contract in `docs/api/v2-coach.md`: the plan routes (NF-FC-011, -012, -014) return
them and the screens (NF-FC-020, -021) read them. `tests/unit/test_coach_mocks.py` checks that
every mock in `docs/mocks/coach/` parses as one of them. Where a plan is stored and for how long:
`docs/data-model/collections/coach.md`.

Every money figure is `{amount, currency}`, so the plan validator of NF-FC-012 can find each one
and the translation step of NF-FC-014 can leave them alone.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.schemas.coach_profile import CoachProfile, Currency, DepartureDate, SlotName
from app.schemas.contract import HostCountryCode, ReportLanguage
from app.schemas.remittance_compare import CorridorId

FactorId = Literal[
    "debt_to_income",
    "emergency_buffer",
    "remittance_ratio",
    "recruitment_fee_vs_cap",
    "banked_status",
]
WarningSeverity = Literal["info", "warning", "urgent"]

# Open vocabularies: the screens translate an id by key and show a neutral fallback for one they
# do not know, so a new id is not a breaking change (`docs/api/v2-conventions.md`, section 6).
SnakeId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,40}$")]
# 20 hex characters: the start of the slot hash (`slot_hash`).
PlanId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{20}$")]

# The plan is written in the currency of the country the worker will earn in.
HOST_CURRENCY: dict[str, str] = {
    "SG": "SGD",
    "KR": "KRW",
    "MY": "MYR",
    "JP": "JPY",
    "HK": "HKD",
    "AU": "AUD",
}
PLAN_WEEKS = 13
MAX_WARNINGS = 8
ROUNDING = 0.005


def slot_hash(profile: CoachProfile) -> str:
    """SHA-256 of the slot values, which makes a plan idempotent (`docs/api/v2-coach.md`).

    Only the values count, written as `CoachProfile` writes them (sorted keys, no spaces, UTF-8,
    unanswered slots left out), so confirming a slot again or answering in another language
    gives the same hash. The plan id is the first 20 characters.
    """
    canonical = json.dumps(
        profile.model_dump(mode="json", exclude_none=True),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ScoreFactor(BaseModel):
    id: FactorId
    value: float | None = Field(
        description="The measured figure (a ratio, or months), `null` when it cannot be measured."
    )
    score: float = Field(ge=0, le=100, description="This factor's points out of 100.")
    weight: float = Field(ge=0, le=1)


class CoachScore(BaseModel):
    """The preparedness score: pure arithmetic on the slots, no model (NF-FC-006, -011)."""

    total: int = Field(ge=0, le=100)
    band: SnakeId = Field(
        description="Provisional until NF-FC-006: `needs_work`, `getting_ready`, `well_prepared`."
    )
    factors: list[ScoreFactor] = Field(min_length=5, max_length=5)
    rubric_version: int = Field(ge=1)

    @field_validator("factors")
    @classmethod
    def _all_five_factors_once(cls, value: list[ScoreFactor]) -> list[ScoreFactor]:
        if {factor.id for factor in value} != set(get_args(FactorId)):
            raise ValueError("The score has each of the five factors exactly once.")
        return value


class PlanMoney(BaseModel):
    """A figure in the plan. Negative only where a shortfall is possible (`left_over`)."""

    amount: float = Field(allow_inf_nan=False)
    currency: Currency


class BudgetLine(BaseModel):
    id: SnakeId
    amount: PlanMoney


class MonthlyBudget(BaseModel):
    """One normal month after arrival. `left_over` is exactly what the lines above leave."""

    income: PlanMoney
    costs: list[BudgetLine] = Field(min_length=1, description="From the cost baselines.")
    goals: list[BudgetLine] = Field(
        description="Money set aside: remittance, debt, emergency fund."
    )
    left_over: PlanMoney = Field(description="Income minus costs minus goals; negative is a gap.")
    setup_costs: PlanMoney | None = Field(
        default=None, description="One-off costs of the first month; not part of the lines."
    )

    @model_validator(mode="after")
    def _the_lines_add_up(self) -> MonthlyBudget:
        currencies = {self.income.currency, self.left_over.currency}
        currencies |= {line.amount.currency for line in self.costs + self.goals}
        if len(currencies) != 1:
            raise ValueError("The budget is in one currency.")
        spent = sum(line.amount.amount for line in self.costs + self.goals)
        if abs(self.income.amount - spent - self.left_over.amount) > ROUNDING:
            raise ValueError("`left_over` is income minus costs minus goals, as shown.")
        return self


class ProviderQuote(BaseModel):
    """The cheapest provider Remittance X-Ray found for the corridor (NF-FC-012)."""

    slug: str
    name: str
    fee: PlanMoney = Field(description="In the host currency.")
    receives: PlanMoney = Field(description="What arrives at home for `monthly_amount`.")
    fx_rate: float = Field(gt=0, description="The provider's rate, home currency per host unit.")
    quoted_at: datetime


class RemittanceSend(BaseModel):
    week: int = Field(ge=1, le=PLAN_WEEKS)
    amount: PlanMoney


class RemittancePlan(BaseModel):
    corridor_id: CorridorId | None = Field(
        description="`null` when the worker's route is not one of the six: no quote then."
    )
    monthly_amount: PlanMoney
    provider: ProviderQuote | None
    schedule: list[RemittanceSend] = Field(description="When to send, in order of week.")

    @model_validator(mode="after")
    def _no_quote_without_a_corridor(self) -> RemittancePlan:
        if self.corridor_id is None and self.provider is not None:
            raise ValueError("A provider is quoted only for one of the six corridors.")
        if [send.week for send in self.schedule] != sorted({send.week for send in self.schedule}):
            raise ValueError("The schedule is in order of week, one send a week at most.")
        return self


class DebtPlan(BaseModel):
    outstanding: PlanMoney
    monthly_payment: PlanMoney
    months_to_clear: int | None = Field(
        ge=1, description="`null` when the payment does not cover the interest."
    )


class EmergencyFundPlan(BaseModel):
    target: PlanMoney
    months_of_costs: int = Field(ge=1, le=12, description="The target is this many months' costs.")
    monthly_saving: PlanMoney
    weeks_to_target: int | None = Field(
        ge=0, description="`null` when the saving is zero; 0 when the target is already met."
    )


class PlanWeek(BaseModel):
    week: int = Field(ge=1, le=PLAN_WEEKS)
    title: str = Field(min_length=1)
    actions: list[Annotated[str, StringConstraints(min_length=1)]] = Field(
        min_length=1, max_length=4
    )


class PlanWarning(BaseModel):
    id: SnakeId
    severity: WarningSeverity
    text: str = Field(min_length=1)


class ChecklistItem(BaseModel):
    id: SnakeId
    text: str = Field(min_length=1)


class CoachPlan(BaseModel):
    """The 13-week plan. Written in English once, then translated with every figure untouched."""

    summary: str = Field(min_length=1)
    monthly_budget: MonthlyBudget
    remittance: RemittancePlan
    debt: DebtPlan | None = Field(description="`null` when the worker owes nothing.")
    emergency_fund: EmergencyFundPlan
    weeks: list[PlanWeek] = Field(min_length=PLAN_WEEKS, max_length=PLAN_WEEKS)
    warnings: list[PlanWarning] = Field(max_length=MAX_WARNINGS)
    checklist: list[ChecklistItem] = Field(min_length=3, max_length=10)
    disclaimer: str = Field(min_length=1, description="The 'not professional advice' note.")

    @field_validator("weeks")
    @classmethod
    def _one_entry_per_week_in_order(cls, value: list[PlanWeek]) -> list[PlanWeek]:
        if [week.week for week in value] != list(range(1, PLAN_WEEKS + 1)):
            raise ValueError("The plan has weeks 1 to 13, in order.")
        return value

    def host_figures(self) -> list[PlanMoney]:
        """Every figure in the host currency (all of them except what arrives at home)."""
        budget = self.monthly_budget
        figures = [budget.income, budget.left_over, self.remittance.monthly_amount]
        figures += [line.amount for line in budget.costs + budget.goals]
        figures += [send.amount for send in self.remittance.schedule]
        figures += [budget.setup_costs] if budget.setup_costs else []
        figures += [self.remittance.provider.fee] if self.remittance.provider else []
        figures += [self.emergency_fund.target, self.emergency_fund.monthly_saving]
        if self.debt:
            figures += [self.debt.outstanding, self.debt.monthly_payment]
        return figures


class CoachPlanResponse(BaseModel):
    """A stored plan in one language (`POST /coach/sessions/{id}/plan`, `GET /coach/plans/{id}`)."""

    id: PlanId
    session_id: str | None = Field(description="`null` once the session has expired.")
    language: ReportLanguage = Field(description="The language of `plan`.")
    available_languages: list[ReportLanguage] = Field(
        description="Languages already stored; `en` is always there. Others are made on request."
    )
    host_country: HostCountryCode
    home_country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    corridor_id: CorridorId | None = None
    departure_date: DepartureDate | None = None
    reporting_currency: Currency = Field(description="The host country's currency.")
    slots: dict[SlotName, Any] = Field(description="The answers the plan was made from.")
    rates_as_of: datetime = Field(description="The oldest exchange rate or quote it used.")
    score: CoachScore
    plan: CoachPlan
    created_at: datetime

    @model_validator(mode="after")
    def _the_parts_agree(self) -> CoachPlanResponse:
        profile = CoachProfile.model_validate(self.slots)
        if self.language not in self.available_languages or "en" not in self.available_languages:
            raise ValueError("`available_languages` has `en` and the language of the plan.")
        if self.reporting_currency != HOST_CURRENCY[self.host_country]:
            raise ValueError("The plan is in the host country's currency.")
        if self.corridor_id is not None:
            host, home = self.corridor_id.split("-")
            if host != self.host_country or self.home_country not in (None, home):
                raise ValueError("The corridor is the host country and the home country.")
        if self.plan.remittance.corridor_id != self.corridor_id:
            raise ValueError("The remittance plan is for the plan's corridor.")
        if self.id != slot_hash(profile)[:20]:
            raise ValueError("The id is the start of the slot hash.")
        if any(f.currency != self.reporting_currency for f in self.plan.host_figures()):
            raise ValueError("Every figure is in the reporting currency.")
        return self
