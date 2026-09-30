from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.remittance_compare import CorridorId, SurveyInfo


class MonthlySavings(BaseModel):
    """What sending `amount` would have cost in one full calendar month, best vs worst service."""

    month: str = Field(description="Calendar month, YYYY-MM.")
    average_rate: float = Field(description="That month's average mid-market rate.")
    best_receives: float = Field(description="With the best comparable service, that month.")
    worst_receives: float = Field(description="With the worst comparable service, that month.")
    savings: float = Field(description="best_receives minus worst_receives.")


class RemittanceSavings(BaseModel):
    """Response of `GET /api/v1/remittance/savings` (NF-P2-022): step 8 of the pipeline.

    Compares the best and the worst comparable service of the corridor over the last
    `months_used` full calendar months, each at that month's average mid-market rate. The two
    services are the same every month (the survey's fees are one quarter, not a history), so
    only the rate changes month to month; `total_savings` is what sending with `best_firm`
    instead of `worst_firm` would have been worth over the period — the "you would have saved
    $X" figure.
    """

    corridor_id: CorridorId
    send_amount: float
    send_currency: str
    receive_currency: str
    months_requested: int = Field(description="Months asked for.")
    months_used: int = Field(
        description="Full calendar months that actually had rate history; less than "
        "months_requested when the history does not go back that far."
    )
    best_rpw_id: int
    best_firm: str
    worst_rpw_id: int
    worst_firm: str
    total_best_receives: float = Field(description="Sum of months[].best_receives.")
    total_worst_receives: float = Field(description="Sum of months[].worst_receives.")
    total_savings: float = Field(
        description="What sending with best_firm instead of worst_firm would have been worth "
        "over the period."
    )
    months: list[MonthlySavings] = Field(description="Oldest first.")
    survey: SurveyInfo
