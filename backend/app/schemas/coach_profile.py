"""The Financial Coach's interview slots (NF-FC-001).

`CoachProfile` holds a worker's answers as plain values: it is what a plan stores
(`coach_plans.slots`) and what the scoring reads. `SlotRecord` is one answer as the session
keeps it (`coach_sessions.slots`), with how sure we are and where it came from. The field names
here are the slot names of `docs/data-model/collections/coach.md`; the questions that fill them
are in `app/services/coach/question_bank.json`.

Two layers of limits: this module refuses values that cannot be true (a negative amount, a
13th month). The question bank holds the *expected* ranges: a value outside them is not refused,
the coach asks again before it keeps it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.schemas.contract import HostCountryCode, JobTypeId

# The six host currencies, the three corridor home currencies, and NPR and BDT: onboarding also
# offers Nepal and Bangladesh as home countries, and a fee is often paid in the home currency.
Currency = Literal["SGD", "KRW", "MYR", "JPY", "HKD", "AUD", "PHP", "INR", "IDR", "NPR", "BDT"]
# "once" is a total at one moment (savings, a fee paid, a debt). Daily and hourly pay are not
# accepted: the coach asks for a normal month instead of guessing how many days are worked.
MoneyPeriod = Literal["month", "week", "year", "once"]
InterestPeriod = Literal["month", "year"]
AccountKind = Literal["bank_account", "mobile_wallet", "both", "none"]
SlotSource = Literal["user", "contract_prefill"]
SlotName = Literal[
    "destination_country",
    "job_type",
    "departure_date",
    "monthly_salary",
    "dependents",
    "remittance_target",
    "recruitment_fee_paid",
    "debt_outstanding",
    "debt_interest",
    "savings",
    "bank_or_wallet",
]
SLOT_NAMES: tuple[str, ...] = get_args(SlotName)

# `YYYY-MM-DD` as a string, not a `date`: Firestore cannot store a date, and the check-in job
# queries `coach_plans.departure_date` as text.
DepartureDate = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]

MAX_AMOUNT = 1_000_000_000
MAX_DEPENDENTS = 20
MAX_INTEREST_PERCENT = 1000
WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12


class Money(BaseModel):
    """An amount in one currency, with the period it covers (`docs/deferred-items.md`, D-106)."""

    model_config = ConfigDict(extra="forbid")

    amount: float = Field(ge=0, le=MAX_AMOUNT, allow_inf_nan=False, strict=True)
    currency: Currency
    period: MoneyPeriod

    def per_month(self) -> float:
        """The amount for one month. A week is 52/12 of a month, a year is 12 of them.

        Raises:
            ValueError: The amount is a one-off total (`period` is `once`): it has no monthly
                figure.
        """
        if self.period == "month":
            return self.amount
        if self.period == "week":
            return self.amount * WEEKS_PER_YEAR / MONTHS_PER_YEAR
        if self.period == "year":
            return self.amount / MONTHS_PER_YEAR
        raise ValueError("A one-off total has no monthly figure.")


class Interest(BaseModel):
    """What a debt costs: a percentage for a month or for a year. 0 is allowed (family loan)."""

    model_config = ConfigDict(extra="forbid")

    rate_percent: float = Field(ge=0, le=MAX_INTEREST_PERCENT, allow_inf_nan=False, strict=True)
    period: InterestPeriod


class CoachProfile(BaseModel):
    """What the interview has learned so far. A slot not asked or not answered is `None`.

    Unknown keys are refused, so a slot the model invents never reaches a plan.
    """

    model_config = ConfigDict(extra="forbid")

    destination_country: HostCountryCode | None = Field(
        default=None, description="The country the worker is going to."
    )
    job_type: JobTypeId | None = Field(default=None, description="The kind of work.")
    departure_date: DepartureDate | None = Field(
        default=None, description="Planned day of leaving, `YYYY-MM-DD`."
    )
    monthly_salary: Money | None = Field(
        default=None, description="Pay as stated: per month, per week or per year."
    )
    dependents: int | None = Field(
        default=None,
        ge=0,
        le=MAX_DEPENDENTS,
        strict=True,
        description="People who depend on the worker's money.",
    )
    remittance_target: Money | None = Field(
        default=None, description="What the worker wants to send home, per month."
    )
    recruitment_fee_paid: Money | None = Field(
        default=None, description="Fees paid or owed to an agent or recruiter. A total (`once`)."
    )
    debt_outstanding: Money | None = Field(
        default=None, description="Money still owed because of the move. A total; 0 is no debt."
    )
    debt_interest: Interest | None = Field(default=None, description="Interest on that debt.")
    savings: Money | None = Field(default=None, description="Savings now. A total (`once`).")
    bank_or_wallet: AccountKind | None = Field(
        default=None, description="Whether the worker has a bank account or a mobile wallet."
    )

    @field_validator("monthly_salary", "remittance_target")
    @classmethod
    def _has_a_real_period(cls, value: Money | None) -> Money | None:
        if value is not None and value.period == "once":
            raise ValueError("Say what it covers: a month, a week or a year.")
        return value

    @field_validator("recruitment_fee_paid", "debt_outstanding", "savings")
    @classmethod
    def _is_a_total(cls, value: Money | None) -> Money | None:
        if value is not None and value.period != "once":
            raise ValueError("This is a total, not an amount for a period.")
        return value

    @field_validator("monthly_salary")
    @classmethod
    def _salary_is_above_zero(cls, value: Money | None) -> Money | None:
        if value is not None and value.amount <= 0:
            raise ValueError("A salary is more than zero.")
        return value

    @field_validator("departure_date")
    @classmethod
    def _is_a_real_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Not a real calendar date.") from None
        if not 2000 <= parsed.year <= 2100:
            raise ValueError("The year is not plausible.")
        return value


class SlotRecord(BaseModel):
    """One slot as `coach_sessions.slots` keeps it (D-106).

    `confirmed` is true once the worker has agreed to the value: always for a contract prefill,
    which enters the session only after the worker confirms it (NF-FC-015).
    """

    model_config = ConfigDict(extra="forbid")

    value: Any
    confidence: float = Field(ge=0, le=1)
    source: SlotSource
    confirmed: bool
    updated_at: datetime
    turn: int = Field(ge=0)

    @field_validator("value")
    @classmethod
    def _has_a_value(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("A stored slot has a value; an unanswered slot is not stored.")
        return value


def parse_slot_value(name: str, raw: object) -> object:
    """Check one answer on its own, with every rule of `CoachProfile`.

    Returns:
        The value as the profile holds it: a `Money`, an `Interest`, a number or a string.

    Raises:
        KeyError: `name` is not a slot.
        pydantic.ValidationError: The value breaks a rule of that slot.
    """
    if name not in SLOT_NAMES:
        raise KeyError(name)
    return getattr(CoachProfile.model_validate({name: raw}), name)
