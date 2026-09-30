from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Final

from fastapi.concurrency import run_in_threadpool

from app.constants import pair_for_corridor
from app.repositories.corridor_repo import CorridorRepository
from app.repositories.rate_repo import RateRepository
from app.schemas.remittance_compare import CorridorDoc, CorridorId
from app.schemas.remittance_savings import MonthlySavings, RemittanceSavings
from app.services.remittance.engine import CorridorNotFoundError, calculate_comparison
from app.services.remittance.trends import DailyRate, HistoryNotFoundError, daily_rates

logger = logging.getLogger(__name__)

MIN_MONTHS: Final = 1
MAX_MONTHS: Final = 12

MonthKey = tuple[int, int]


def _month_key(year: int, month: int) -> MonthKey:
    return year, month


def _add_months(key: MonthKey, delta: int) -> MonthKey:
    year, month = key
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def target_months(today_month: MonthKey, months: int) -> list[MonthKey]:
    """The `months` full calendar months just before `today_month`, oldest first.

    The current, still-incomplete month is never included: averaging a handful of days
    against a full month elsewhere would understate or overstate that month for no reason.
    """
    return [_add_months(today_month, delta=-offset) for offset in range(months, 0, -1)]


def monthly_averages(rates: list[DailyRate], months: list[MonthKey]) -> dict[MonthKey, float]:
    """The average mid-market rate of each requested month that has at least one rate."""
    wanted = set(months)
    buckets: dict[MonthKey, list[float]] = defaultdict(list)
    for item in rates:
        key = _month_key(item.day.year, item.day.month)
        if key in wanted:
            buckets[key].append(item.rate)
    return {key: statistics.fmean(values) for key, values in buckets.items()}


async def get_savings(
    corridor_id: CorridorId,
    amount: float,
    months: int,
    corridors: CorridorRepository,
    rates: RateRepository,
    now: datetime,
) -> RemittanceSavings:
    """What choosing the best comparable service, instead of the worst, would have been worth.

    The best and worst service (and their total cost as a percentage of `amount`) come from
    `calculate_comparison`, the same ranking `/compare` shows; a fixed `amount` ranks the same
    whatever the rate is, so the survey's own median rate is used and no live rate is read.
    Each of the last `months` full calendar months is then priced at its own average mid-market
    rate from `rates_history` (NF-P2-015's `daily_rates`), reusing the survey's fee and margin
    for both services rather than recomputing them.

    Args:
        corridor_id: One of the six corridors.
        amount: Amount to send, in the corridor's sending currency.
        months: Full months to look back over, 1 to 12.
        corridors: Repository for `corridors`.
        rates: Repository for `rates_cache` / `rates_history`.
        now: Current UTC time; only its calendar month matters.

    Returns:
        The comparison, one entry per month that had rate history (may be fewer than `months`).

    Raises:
        CorridorNotFoundError: The corridor is not loaded, or nothing in it can be compared.
        AmountOutOfRangeError: `amount` is outside the range the survey can be stretched to.
        HistoryNotFoundError: No month in the requested period has any stored rate history.
    """
    raw_corridor = await run_in_threadpool(corridors.get_corridor, corridor_id)
    if raw_corridor is None:
        raise CorridorNotFoundError(f"corridor {corridor_id!r} is not loaded")
    corridor = CorridorDoc.model_validate(raw_corridor)

    comparison = calculate_comparison(corridor_id, corridor, amount, cached_rate=None, now=now)
    providers_by_id = {p.rpw_id: p for p in comparison.providers}
    best = providers_by_id[comparison.summary.best_rpw_id]
    worst = providers_by_id[comparison.summary.worst_rpw_id]

    pair = pair_for_corridor(corridor_id)
    raw_history = await run_in_threadpool(rates.get_history, pair.pair_id)
    history = daily_rates(raw_history)
    if not history:
        raise HistoryNotFoundError(pair.pair_id)

    wanted_months = target_months((now.year, now.month), months)
    averages = monthly_averages(history, wanted_months)
    if not averages:
        raise HistoryNotFoundError(pair.pair_id)

    raw_entries = [
        (year, month, averages[(year, month)])
        for year, month in wanted_months
        if (year, month) in averages
    ]
    monthly: list[MonthlySavings] = []
    total_best = total_worst = 0.0
    for year, month, avg_rate in raw_entries:
        best_receives = amount * avg_rate * (1 - best.total_cost_pct / 100)
        worst_receives = amount * avg_rate * (1 - worst.total_cost_pct / 100)
        total_best += best_receives
        total_worst += worst_receives
        monthly.append(
            MonthlySavings(
                month=f"{year:04d}-{month:02d}",
                average_rate=round(avg_rate, 6),
                best_receives=round(best_receives, 2),
                worst_receives=round(worst_receives, 2),
                savings=round(best_receives - worst_receives, 2),
            )
        )

    result = RemittanceSavings(
        corridor_id=corridor_id,
        send_amount=amount,
        send_currency=comparison.send_currency,
        receive_currency=comparison.receive_currency,
        months_requested=months,
        months_used=len(monthly),
        best_rpw_id=best.rpw_id,
        best_firm=best.firm,
        worst_rpw_id=worst.rpw_id,
        worst_firm=worst.firm,
        total_best_receives=round(total_best, 2),
        total_worst_receives=round(total_worst, 2),
        total_savings=round(total_best - total_worst, 2),
        months=monthly,
        survey=comparison.survey,
    )
    logger.info(
        "remittance_savings corridor=%s months_requested=%d months_used=%d savings=%s",
        corridor_id,
        months,
        result.months_used,
        result.total_savings,
    )
    return result
