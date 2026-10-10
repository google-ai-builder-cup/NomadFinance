from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

# docs/data-model/collections/fib.md: "Transfers and savings: none needed" — only income and
# bills carry a category at all.
IncomeCategory = Literal["salary", "overtime", "bonus", "other_income"]
BillCategory = Literal[
    "rent", "utilities", "phone_internet", "transport", "food", "medical", "other_expense"
]
SavingsDirection = Literal["deposit", "withdrawal"]
AccountType = Literal["cash", "bank", "mobile_wallet", "other"]
CategorySource = Literal["user", "model"]

CURRENCY_PATTERN = r"^[A-Z]{3}$"
MAX_NOTES_CHARS = 500
MAX_VENDOR_CHARS = 200
MAX_EMPLOYER_CHARS = 200

# The most one entry can be (NF-HR-004). An extra zero or a slipped finger would otherwise sit in
# the worker's profile for a year: one entry of SGD 99,999 took the income stability score of a
# worker with three steady months from 67 to 0. Yen and won have no minor unit, so their
# amounts run a hundred times larger. The app's form holds the same limits (`utils/fibForm.ts`).
MAX_AMOUNT = 1_000_000
MAX_AMOUNT_WHOLE_UNIT = 100_000_000
WHOLE_UNIT_CURRENCIES = frozenset({"JPY", "KRW"})


def _within_limit(amount: float, currency: str) -> None:
    limit = MAX_AMOUNT_WHOLE_UNIT if currency in WHOLE_UNIT_CURRENCIES else MAX_AMOUNT
    if amount > limit:
        raise ValueError(f"amount must be at most {limit:,} {currency}")


class IncomeLogRequest(BaseModel):
    """Body of `POST /api/v1/fib/income`."""

    entry_date: date | None = Field(
        default=None, description="Defaults to today (UTC) when omitted."
    )
    amount: float = Field(gt=0)
    currency: str = Field(pattern=CURRENCY_PATTERN, description="ISO 4217, e.g. SGD")
    category: IncomeCategory
    employer_name: str | None = Field(default=None, max_length=MAX_EMPLOYER_CHARS)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)

    @field_validator("employer_name", "notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def _not_beyond_the_limit(self) -> Self:
        _within_limit(self.amount, self.currency)
        return self


class IncomeLogResponse(BaseModel):
    """Response of `POST /api/v1/fib/income`: the stored entry."""

    entry_id: str = Field(description="Id of `users/{uid}/income/{entry_id}`.")
    entry_date: date
    amount: float
    currency: str
    category: IncomeCategory
    category_source: CategorySource
    employer_name: str | None
    # Always false here: true is set only by the contract cross-pillar flow (NF-P3-024),
    # never by a worker's own manual entry.
    verified: bool
    notes: str | None
    created_at: datetime


class BillLogRequest(BaseModel):
    """Body of `POST /api/v1/fib/bill`. Manual entry; a photo read by Gemini Vision is
    NF-P3-011's own endpoint, not this one."""

    entry_date: date | None = Field(
        default=None, description="Defaults to today (UTC) when omitted."
    )
    amount: float = Field(gt=0)
    currency: str = Field(pattern=CURRENCY_PATTERN, description="ISO 4217, e.g. SGD")
    vendor: str | None = Field(default=None, max_length=MAX_VENDOR_CHARS)
    bill_date: date | None = Field(default=None, description="Date printed on the bill, if known.")
    paid: bool
    category: BillCategory | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)

    @field_validator("vendor", "notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def _not_beyond_the_limit(self) -> Self:
        _within_limit(self.amount, self.currency)
        return self


class BillLogResponse(BaseModel):
    """Response of `POST /api/v1/fib/bill`: the stored entry."""

    entry_id: str = Field(description="Id of `users/{uid}/bills/{entry_id}`.")
    entry_date: date
    amount: float
    currency: str
    vendor: str | None
    bill_date: date | None
    paid: bool
    category: BillCategory | None
    category_source: CategorySource | None
    notes: str | None
    created_at: datetime


class SavingsLogRequest(BaseModel):
    """Body of `POST /api/v1/fib/savings`."""

    entry_date: date | None = Field(
        default=None, description="Defaults to today (UTC) when omitted."
    )
    amount: float = Field(gt=0, description="Always positive; `direction` carries the sign.")
    currency: str = Field(pattern=CURRENCY_PATTERN, description="ISO 4217, e.g. SGD")
    direction: SavingsDirection
    account_type: AccountType | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_CHARS)

    @field_validator("notes")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def _not_beyond_the_limit(self) -> Self:
        _within_limit(self.amount, self.currency)
        return self


class SavingsLogResponse(BaseModel):
    """Response of `POST /api/v1/fib/savings`: the stored entry."""

    entry_id: str = Field(description="Id of `users/{uid}/savings/{entry_id}`.")
    entry_date: date
    amount: float
    currency: str
    direction: SavingsDirection
    account_type: AccountType | None
    notes: str | None
    created_at: datetime


class ExtractedBill(BaseModel):
    """What Gemini Vision reads from a bill photo (NF-P3-011); also its `response_schema`.

    Dates are strings, not `date`: a misread date must not fail the whole schema and discard
    a good amount. The service parses `bill_date` and drops it when it is not valid.
    Field descriptions are sent to Gemini as part of the schema.
    """

    is_bill: bool = Field(description="False for anything that is not a bill, invoice or receipt.")
    amount: float | None = Field(default=None, description="Final total, no symbols or separators.")
    currency: str | None = Field(default=None, description="ISO 4217 code, e.g. SGD.")
    vendor: str | None = Field(default=None, description="Issuer of the bill, as written.")
    bill_date: str | None = Field(default=None, description="Bill or payment date, YYYY-MM-DD.")
    paid: bool | None = Field(default=None, description="True if shown as paid, null if unclear.")
    category: BillCategory | None = None
    confidence: float = Field(ge=0, le=1, description="Confidence in amount and currency together.")


class BillScanResponse(BillLogResponse):
    """Response of `POST /api/v1/fib/bill/scan`: the entry stored from the photo."""

    image_path: str | None = Field(
        description="Cloud Storage path of the photo; null if it could not be stored."
    )
    confidence: float = Field(description="How sure Gemini is of `amount` and `currency`, 0 to 1.")
    paid_assumed: bool = Field(
        description="True when the bill did not say if it was paid; `paid` is then false."
    )


# One flat list of every category, not `IncomeCategory | BillCategory`: Gemini's response
# schema handles a single enum better than a union of two. The service checks that the
# category fits the entry's type.
AnyCategory = Literal[
    "salary",
    "overtime",
    "bonus",
    "other_income",
    "rent",
    "utilities",
    "phone_internet",
    "transport",
    "food",
    "medical",
    "other_expense",
]


class CategorizeResult(BaseModel):
    """One entry's category as Gemini returns it (NF-P3-012)."""

    id: str = Field(description="The entry id, copied exactly.")
    category: AnyCategory
    confidence: float = Field(ge=0, le=1)


class CategorizeAnswer(BaseModel):
    """Gemini's answer for one batch of entries; also its `response_schema`."""

    results: list[CategorizeResult]


class CategorizedEntry(BaseModel):
    """An entry that got a category in this call."""

    entry_id: str
    entry_type: Literal["income", "bill"]
    category: AnyCategory
    confidence: float


class FibCategorizeResponse(BaseModel):
    """Response of `POST /api/v1/fib/categorize`."""

    categorized: list[CategorizedEntry]
    skipped: int = Field(
        description="Entries Gemini gave no usable category for; still pending, retried next call."
    )
    remaining: int = Field(
        description="Pending entries left for a later call because of the per-call limit."
    )
