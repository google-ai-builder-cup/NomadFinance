from __future__ import annotations

from datetime import date
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.remittance_compare import CorridorId


class TrendDays(IntEnum):
    """Periods the chart offers. An enum, not a Literal: a query string arrives as "90"."""

    MONTH = 30
    QUARTER = 90
    HALF_YEAR = 180
    YEAR = 365


Weekday = Literal["monday", "tuesday", "wednesday", "thursday", "friday"]
NoBestDayReason = Literal["not_enough_history", "no_clear_pattern"]


class TrendPoint(BaseModel):
    """The mid-market rate of one market day: units of the receiving currency per 1 sent."""

    date: date
    rate: float


class TrendSummary(BaseModel):
    first: TrendPoint = Field(description="Oldest day in the period")
    latest: TrendPoint = Field(description="Newest day in the period")
    change_pct: float = Field(description="Latest against first, in percent; above 0 is better")
    low: TrendPoint = Field(description="Worst day for the sender (fewest units received)")
    high: TrendPoint = Field(description="Best day for the sender")
    average: float


class WeekdayStat(BaseModel):
    """How one weekday compares with the rest of its own week, over the analysed weeks."""

    weekday: Weekday
    advantage_pct: float = Field(
        description="Average percent above (or below, when negative) its week's average rate"
    )
    weeks: int = Field(description="Weeks in which this weekday had a rate")
    beat_share: float = Field(
        description="Share of those weeks in which it was above its week's average, 0 to 1"
    )


class RemittanceTrends(BaseModel):
    """Response of `GET /api/v1/remittance/trends` (NF-P2-015)."""

    corridor_id: CorridorId
    pair: str = Field(description="rates_history document id, e.g. SGD_PHP")
    base_currency: str
    quote_currency: str
    days: TrendDays = Field(description="Length of the period the points cover")
    points: list[TrendPoint] = Field(description="One per market day, oldest first")
    summary: TrendSummary | None = Field(description="Null when the period has no points")
    last_date: date = Field(description="Newest day stored, even when outside the period")
    best_day: WeekdayStat | None = Field(
        description="The weekday that is usually best to send on, from the last 52 weeks"
    )
    best_day_reason: NoBestDayReason | None = Field(
        description="Why best_day is null: too few weeks, or no weekday is reliably better"
    )
    weeks_analysed: int = Field(description="Weeks with at least 3 market days in the analysis")
    weekdays: list[WeekdayStat] = Field(
        description="All five weekdays, Monday first; empty when there is not enough history"
    )
    providers: list[str] = Field(
        description="Rate sources used in the points; show attribution for exchangerate_api"
    )
