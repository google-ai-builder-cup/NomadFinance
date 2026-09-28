from __future__ import annotations

import math
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

CorridorId = Literal["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"]


class RemittanceCompareRequest(BaseModel):
    """Body of `POST /api/v1/remittance/compare`."""

    corridor_id: CorridorId = Field(
        description="Sending country and receiving country, e.g. SG-PH."
    )
    amount: float = Field(
        gt=0, description="Amount to send, in the corridor's sending currency (SGD for SG-PH)."
    )

    @field_validator("amount", mode="before")
    @classmethod
    def _finite(cls, value: object) -> object:
        # FastAPI echoes a rejected value back in its 422. NaN and Infinity cannot be written
        # as JSON, so the API would answer 500. A 0 fails the `gt` check with a plain 422.
        if isinstance(value, float) and not math.isfinite(value):
            return 0.0
        return value


# Stored documents, as far as the engine reads them (docs/data-model/collections/corridors.md,
# rates_cache.md). Fields the engine does not use are ignored.


class Quote(BaseModel):
    """The price of one surveyed send amount; amounts are in the sender's currency."""

    send_amount_lcu: float
    fee_lcu: float
    fx_margin_pct: float
    total_cost_pct: float


class CorridorProvider(BaseModel):
    """One surveyed service of a corridor. A firm appears once per service, so `rpw_id`."""

    rpw_id: int
    firm: str
    firm_type: str
    payment_instrument: str
    access_point: str
    pickup_method: str
    speed: str
    network_coverage: str | None = None
    note: str | None = None
    payout_currency: str
    interbank_rate: float
    surveyed_on: str
    quote_200: Quote
    quote_500: Quote


class CorridorSource(BaseModel):
    name: str
    url: str
    attribution: str


class CorridorDoc(BaseModel):
    corridor_id: str
    source_currency: str
    destination_currency: str
    period: str
    providers: list[CorridorProvider]
    source: CorridorSource


class RateDoc(BaseModel):
    """`rates_cache/{pair}`: the latest mid-market rate."""

    rate: float = Field(gt=0)
    provider: str
    rate_date: str
    fetched_at: datetime | None = None


# The response.


class RateInfo(BaseModel):
    """The mid-market rate every amount is worked out with."""

    pair: str = Field(description="Currency pair, e.g. SGD_PHP.")
    rate: float = Field(description="Units of the receiving currency for 1 unit sent.")
    source: Literal["live", "survey"] = Field(
        description="`live` from the cron's cache; `survey` (median of the survey) when none."
    )
    provider: str | None = Field(description="FX provider that answered; null for `survey`.")
    rate_date: str | None
    fetched_at: datetime | None
    stale: bool = Field(
        description="True when the rate is older than 6 hours or comes from the survey: warn."
    )


class SurveyInfo(BaseModel):
    """Where the prices come from. Show `attribution` wherever they are shown (World Bank terms)."""

    period: str = Field(description="Survey quarter, e.g. 2025_1Q.")
    surveyed_from: str
    surveyed_to: str
    source_name: str
    source_url: str
    attribution: str


class ProviderResult(BaseModel):
    """One service, worked out for the requested amount."""

    rpw_id: int
    firm: str
    firm_type: str
    payment_instrument: str = Field(description="How the sender pays.")
    access_point: str = Field(description="Where the sender starts.")
    pickup_method: str = Field(description="How the receiver collects.")
    speed: str
    speed_order: int = Field(description="0 fastest; sort by this, not by `speed`.")
    network_coverage: str | None
    note: str | None
    payout_currency: str
    comparable: bool = Field(
        description="False when the receiver is paid in another currency (USD): not ranked."
    )
    rank: int | None = Field(description="1 = the recipient receives most; null if not comparable.")
    estimated: bool = Field(
        description="True when the amount is outside the surveyed range (about USD 200 to 500)."
    )
    fee: float = Field(description="Flat fee, in the sending currency.")
    fx_margin_pct: float = Field(description="How much worse than mid-market the rate is.")
    rate_cost: float = Field(description="The rate markup as an amount, in the sending currency.")
    total_cost: float = Field(description="`fee` + `rate_cost`, in the sending currency.")
    total_cost_pct: float = Field(description="`total_cost` as a percentage of the amount sent.")
    recipient_receives: float | None = Field(description="In the receiving currency.")
    lost_to_costs: float | None = Field(
        description="Mid-market amount minus `recipient_receives`, in the receiving currency."
    )
    less_than_best: float | None = Field(
        description="What the best service gives the recipient over this one; 0 for rank 1."
    )


class ComparisonSummary(BaseModel):
    """The headline numbers over the ranked services."""

    comparable_count: int
    best_rpw_id: int
    best_firm: str
    best_recipient_receives: float
    worst_rpw_id: int
    worst_firm: str
    worst_recipient_receives: float
    extra_vs_worst: float = Field(description="Best minus worst, in the receiving currency.")
    mid_market_receives: float = Field(description="What the amount is worth with no costs.")
    median_total_cost_pct: float


class RemittanceComparison(BaseModel):
    """Response of `POST /api/v1/remittance/compare` (NF-P2-014)."""

    corridor_id: CorridorId
    send_amount: float
    send_currency: str
    receive_currency: str
    rate: RateInfo
    survey: SurveyInfo
    providers: list[ProviderResult] = Field(
        description="Ranked services first, then those that are not comparable."
    )
    summary: ComparisonSummary
