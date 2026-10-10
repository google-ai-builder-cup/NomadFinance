"""The unified activity feed of `GET /api/v1/fib/activity` (NF-HR-001).

One list of what the worker did across the money log, the Coach and the Scam Analyzer. Every
item is a kind, a day and a few fixed fields: never a note, an employer, a vendor, a message, an
answer a worker typed or an explanation.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

IncomeCategory = Literal["salary", "overtime", "bonus", "other_income"]


class _Item(BaseModel):
    id: str = Field(description="The entry, plan or check this is about.")
    on: date = Field(description="The day it happened (UTC).")


class IncomeItem(_Item):
    kind: Literal["income"] = "income"
    amount: float
    currency: str
    category: str | None = None
    verified: bool = Field(description="Backed by an analysed employment contract.")


class TransferItem(_Item):
    kind: Literal["transfer"] = "transfer"
    amount: float = Field(description="Sent, in `currency`.")
    currency: str
    corridor_id: str | None = None


class BillItem(_Item):
    kind: Literal["bill"] = "bill"
    amount: float
    currency: str
    category: str | None = None
    paid: bool


class SavingsItem(_Item):
    kind: Literal["savings"] = "savings"
    amount: float
    currency: str
    direction: Literal["deposit", "withdrawal"]


class CoachPlanItem(_Item):
    kind: Literal["coach_plan"] = "coach_plan"
    corridor_id: str | None = None
    departure_date: date | None = None


class CoachCheckinItem(_Item):
    kind: Literal["coach_checkin"] = "coach_checkin"
    milestone: Literal["d30", "d60", "d90"]
    remittance: Literal["on_track", "behind", "not_yet"]
    savings: Literal["on_track", "behind", "not_yet"]
    pay: Literal["full_on_time", "late_or_less", "not_paid"]


class ScamCheckItem(_Item):
    kind: Literal["scam_check"] = "scam_check"
    is_scam: bool
    risk_level: Literal["low", "medium", "high"] | None = None
    scam_type: str | None = Field(default=None, description="A taxonomy id, never free text.")


ActivityItem = Annotated[
    IncomeItem
    | TransferItem
    | BillItem
    | SavingsItem
    | CoachPlanItem
    | CoachCheckinItem
    | ScamCheckItem,
    Field(discriminator="kind"),
]


class ActivityFeedResponse(BaseModel):
    items: list[ActivityItem] = Field(description="Newest first.")
    days: int = Field(description="How many days back the feed reaches.")
    truncated: bool = Field(description="`true` when older items in the range were left out.")
