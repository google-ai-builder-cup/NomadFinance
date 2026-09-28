from __future__ import annotations

import logging
import statistics
from datetime import UTC, datetime

from fastapi.concurrency import run_in_threadpool

from app.constants import RATE_MAX_AGE, pair_for_corridor
from app.repositories.corridor_repo import CorridorRepository
from app.repositories.rate_repo import RateRepository
from app.schemas.remittance_compare import (
    ComparisonSummary,
    CorridorDoc,
    CorridorId,
    CorridorProvider,
    ProviderResult,
    RateDoc,
    RateInfo,
    RemittanceComparison,
    SurveyInfo,
)

logger = logging.getLogger(__name__)

# The survey priced two amounts (about USD 200 and 500). Between them the fee and the rate
# margin are interpolated; beyond them the nearest survey point is kept and the result is
# marked as an estimate. Outside these multiples of the two amounts nothing is calculated.
MIN_AMOUNT_FACTOR = 0.25
MAX_AMOUNT_FACTOR = 10.0

# Fastest first (World Bank's own wording), so the table can sort by number.
SPEED_ORDER: tuple[str, ...] = (
    "Less than one hour",
    "Same day",
    "Next day",
    "2 days",
    "3-5 days",
    "6 days or more",
)


class CorridorNotFoundError(Exception):
    """No prices are loaded for this corridor (NF-P1-016), or none of them can be compared."""


class AmountOutOfRangeError(Exception):
    """The amount is outside what the survey can be stretched to."""

    def __init__(self, minimum: float, maximum: float, currency: str) -> None:
        super().__init__(f"{minimum:g}..{maximum:g} {currency}")
        self.minimum = minimum
        self.maximum = maximum
        self.currency = currency


def amount_limits(corridor: CorridorDoc) -> tuple[float, float]:
    """The smallest and largest amount, in the sending currency, that can be compared."""
    low = min(p.quote_200.send_amount_lcu for p in corridor.providers)
    high = max(p.quote_500.send_amount_lcu for p in corridor.providers)
    return low * MIN_AMOUNT_FACTOR, high * MAX_AMOUNT_FACTOR


def _terms(provider: CorridorProvider, amount: float) -> tuple[float, float, bool]:
    """Fee, rate margin (%) and whether this is an estimate, for `amount`.

    The survey's own `total_cost_pct` is exactly `fee / amount * 100 + fx_margin_pct` (all 442
    published quotes agree to 0.005 points), so this reproduces it at the two survey amounts.
    """
    low, high = provider.quote_200, provider.quote_500
    if amount <= low.send_amount_lcu:
        return low.fee_lcu, low.fx_margin_pct, amount < low.send_amount_lcu
    if amount >= high.send_amount_lcu:
        return high.fee_lcu, high.fx_margin_pct, amount > high.send_amount_lcu
    share = (amount - low.send_amount_lcu) / (high.send_amount_lcu - low.send_amount_lcu)
    fee = low.fee_lcu + share * (high.fee_lcu - low.fee_lcu)
    margin = low.fx_margin_pct + share * (high.fx_margin_pct - low.fx_margin_pct)
    return fee, margin, False


def _resolve_rate(
    corridor: CorridorDoc, pair_id: str, cached: RateDoc | None, now: datetime
) -> RateInfo:
    if cached is not None:
        fetched = cached.fetched_at
        if fetched is not None and fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        return RateInfo(
            pair=pair_id,
            rate=cached.rate,
            source="live",
            provider=cached.provider,
            rate_date=cached.rate_date,
            fetched_at=fetched,
            stale=fetched is None or now - fetched > RATE_MAX_AGE,
        )
    # The cron has not written this pair yet: the survey's own mid-market rates, of a past
    # date, are better than no answer. `stale` tells the app to say so.
    survey_rates = [
        p.interbank_rate
        for p in corridor.providers
        if p.payout_currency == corridor.destination_currency
    ]
    return RateInfo(
        pair=pair_id,
        rate=statistics.median(survey_rates),
        source="survey",
        provider=None,
        rate_date=None,
        fetched_at=None,
        stale=True,
    )


def _speed_order(speed: str) -> int:
    return SPEED_ORDER.index(speed) if speed in SPEED_ORDER else len(SPEED_ORDER)


def calculate_comparison(
    corridor_id: CorridorId,
    corridor: CorridorDoc,
    amount: float,
    cached_rate: RateDoc | None,
    now: datetime,
) -> RemittanceComparison:
    """Work out what every service costs for `amount` and rank them. No I/O.

    The cost of a service is its fee plus the rate markup, as the World Bank defines it:
    `total_cost_pct = fee / amount * 100 + fx_margin_pct`. The recipient receives
    `amount * rate * (1 - total_cost_pct / 100)`. Every service of a corridor is worked out
    with the same mid-market rate, so the rate changes the amounts, never the order.

    Args:
        corridor_id: The corridor asked for.
        corridor: The stored corridor with its surveyed services.
        amount: Amount to send, in the corridor's sending currency.
        cached_rate: `rates_cache` for the corridor's pair, or None.
        now: Current UTC time, to judge how old the cached rate is.

    Returns:
        Services that pay out in the receiving currency, best first with `rank`; then those
        paying out in another currency (`comparable` false, no rank).

    Raises:
        AmountOutOfRangeError: `amount` is outside `amount_limits`.
        CorridorNotFoundError: No service of the corridor can be compared.
    """
    minimum, maximum = amount_limits(corridor)
    if not minimum <= amount <= maximum:
        raise AmountOutOfRangeError(minimum, maximum, corridor.source_currency)

    pair = pair_for_corridor(corridor_id)
    rate = _resolve_rate(corridor, pair.pair_id, cached_rate, now)
    mid_market = amount * rate.rate

    rows: list[ProviderResult] = []
    for provider in corridor.providers:
        fee, margin, estimated = _terms(provider, amount)
        rate_cost = amount * margin / 100
        total_cost = fee + rate_cost
        total_pct = total_cost / amount * 100
        comparable = provider.payout_currency == corridor.destination_currency
        receives = mid_market * (1 - total_pct / 100) if comparable else None
        rows.append(
            ProviderResult(
                rpw_id=provider.rpw_id,
                firm=provider.firm,
                firm_type=provider.firm_type,
                payment_instrument=provider.payment_instrument,
                access_point=provider.access_point,
                pickup_method=provider.pickup_method,
                speed=provider.speed,
                speed_order=_speed_order(provider.speed),
                network_coverage=provider.network_coverage,
                note=provider.note,
                payout_currency=provider.payout_currency,
                comparable=comparable,
                rank=None,
                estimated=estimated,
                fee=fee,
                fx_margin_pct=margin,
                rate_cost=rate_cost,
                total_cost=total_cost,
                total_cost_pct=total_pct,
                recipient_receives=receives,
                lost_to_costs=None if receives is None else mid_market - receives,
                less_than_best=None,
            )
        )

    ranked = sorted(
        (row for row in rows if row.comparable),
        # Ties (services priced the same) go to the faster one, then by name, so the order
        # never changes between two identical requests.
        key=lambda row: (-(row.recipient_receives or 0.0), row.speed_order, row.firm, row.rpw_id),
    )
    if not ranked:
        raise CorridorNotFoundError(f"no comparable service in {corridor_id}")
    others = sorted((row for row in rows if not row.comparable), key=lambda row: row.total_cost_pct)

    best_receives = ranked[0].recipient_receives or 0.0
    for position, row in enumerate(ranked, start=1):
        row.rank = position
        row.less_than_best = best_receives - (row.recipient_receives or 0.0)
    best, worst = ranked[0], ranked[-1]
    summary = ComparisonSummary(
        comparable_count=len(ranked),
        best_rpw_id=best.rpw_id,
        best_firm=best.firm,
        best_recipient_receives=best_receives,
        worst_rpw_id=worst.rpw_id,
        worst_firm=worst.firm,
        worst_recipient_receives=worst.recipient_receives or 0.0,
        extra_vs_worst=best_receives - (worst.recipient_receives or 0.0),
        mid_market_receives=mid_market,
        median_total_cost_pct=statistics.median(row.total_cost_pct for row in ranked),
    )

    surveyed = sorted(p.surveyed_on for p in corridor.providers)
    result = RemittanceComparison(
        corridor_id=corridor_id,
        send_amount=amount,
        send_currency=corridor.source_currency,
        receive_currency=corridor.destination_currency,
        rate=rate,
        survey=SurveyInfo(
            period=corridor.period,
            surveyed_from=surveyed[0],
            surveyed_to=surveyed[-1],
            source_name=corridor.source.name,
            source_url=corridor.source.url,
            attribution=corridor.source.attribution,
        ),
        providers=[*ranked, *others],
        summary=summary,
    )
    return _rounded(result)


def _rounded(result: RemittanceComparison) -> RemittanceComparison:
    """Round every amount to two decimals, once, after the sums are done."""
    for row in result.providers:
        row.fee = round(row.fee, 2)
        row.fx_margin_pct = round(row.fx_margin_pct, 2)
        row.rate_cost = round(row.rate_cost, 2)
        row.total_cost = round(row.total_cost, 2)
        row.total_cost_pct = round(row.total_cost_pct, 2)
        if row.recipient_receives is not None and row.lost_to_costs is not None:
            row.recipient_receives = round(row.recipient_receives, 2)
            row.lost_to_costs = round(row.lost_to_costs, 2)
        if row.less_than_best is not None:
            row.less_than_best = round(row.less_than_best, 2)
    summary = result.summary
    summary.best_recipient_receives = round(summary.best_recipient_receives, 2)
    summary.worst_recipient_receives = round(summary.worst_recipient_receives, 2)
    summary.extra_vs_worst = round(summary.extra_vs_worst, 2)
    summary.mid_market_receives = round(summary.mid_market_receives, 2)
    summary.median_total_cost_pct = round(summary.median_total_cost_pct, 2)
    result.rate.rate = round(result.rate.rate, 6)
    return result


async def compare_remittance(
    corridor_id: CorridorId,
    amount: float,
    corridors: CorridorRepository,
    rates: RateRepository,
    now: datetime,
) -> RemittanceComparison:
    """Compare every surveyed way to send `amount` along a corridor. Steps 2 to 6 of the pipeline.

    Args:
        corridor_id: One of the six corridors.
        amount: Amount to send, in the corridor's sending currency.
        corridors: Repository for `corridors`.
        rates: Repository for `rates_cache`.
        now: Current UTC time.

    Returns:
        The ranked comparison; see `calculate_comparison`.

    Raises:
        CorridorNotFoundError: The corridor is not loaded, or nothing in it can be compared.
        AmountOutOfRangeError: `amount` is outside the range the survey can be stretched to.
    """
    raw = await run_in_threadpool(corridors.get_corridor, corridor_id)
    if raw is None:
        raise CorridorNotFoundError(f"corridor {corridor_id!r} is not loaded")
    corridor = CorridorDoc.model_validate(raw)
    pair = pair_for_corridor(corridor_id)
    raw_rate = await run_in_threadpool(rates.get_rate, pair.pair_id)
    cached = RateDoc.model_validate(raw_rate) if raw_rate is not None else None

    result = calculate_comparison(corridor_id, corridor, amount, cached, now)
    logger.info(
        "remittance_compare corridor=%s providers=%d ranked=%d rate=%s stale=%s estimated=%d",
        corridor_id,
        len(result.providers),
        result.summary.comparable_count,
        result.rate.source,
        result.rate.stale,
        sum(row.estimated for row in result.providers),
    )
    return result
