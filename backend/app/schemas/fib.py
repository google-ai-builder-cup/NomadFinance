from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
