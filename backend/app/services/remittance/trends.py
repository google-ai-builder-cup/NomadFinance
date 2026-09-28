from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.constants import pair_for_corridor
from app.repositories.rate_repo import RateRepository
from app.schemas.remittance_compare import CorridorId
from app.schemas.remittance_trends import (
    NoBestDayReason,
    RemittanceTrends,
    TrendDays,
    TrendPoint,
    TrendSummary,
    Weekday,
    WeekdayStat,
)

logger = logging.getLogger(__name__)

WEEKDAYS: tuple[Weekday, ...] = ("monday", "tuesday", "wednesday", "thursday", "friday")

# The best day is looked for in the last year, whatever period the chart shows: a weekday
# pattern needs many weeks, and a 30-day chart has only four.
ANALYSIS_DAYS = 364
MIN_WEEKS = 8
MIN_DAYS_PER_WEEK = 3
# A weekday is only called "best" when it beats its week on average by this much and in more
# than half of the weeks. Below that, the differences are noise and a tip would mislead.
CLEAR_PATTERN_PCT = 0.05


class HistoryNotFoundError(Exception):
    """The pair has no daily rates stored yet (no cron run, no backfill)."""


@dataclass(frozen=True)
class DailyRate:
    day: date
    rate: float
    provider: str


def daily_rates(history: dict[str, Any] | None) -> list[DailyRate]:
    """The `daily` map of a rates_history header as a list, oldest first.

    Entries that are not a valid date with a positive rate are skipped, so one damaged entry
    never breaks the chart.
    """
    daily = (history or {}).get("daily")
    if not isinstance(daily, dict):
        return []
    rates: list[DailyRate] = []
    skipped = 0
    for key, entry in daily.items():
        try:
            day = date.fromisoformat(key)
            rate = float(entry["rate"])
        except (ValueError, TypeError, KeyError):
            skipped += 1
            continue
        if rate <= 0:
            skipped += 1
            continue
        rates.append(DailyRate(day, rate, str(entry.get("provider") or "unknown")))
    if skipped:
        logger.warning("rates_history_bad_entries count=%d", skipped)
    return sorted(rates, key=lambda item: item.day)


def summarize(points: list[TrendPoint]) -> TrendSummary | None:
    if not points:
        return None
    first, latest = points[0], points[-1]
    return TrendSummary(
        first=first,
        latest=latest,
        change_pct=round((latest.rate / first.rate - 1) * 100, 3),
        low=min(points, key=lambda p: p.rate),
        high=max(points, key=lambda p: p.rate),
        average=round(statistics.fmean(p.rate for p in points), 6),
    )


def weekday_stats(rates: list[DailyRate]) -> tuple[list[WeekdayStat], int]:
    """Each weekday against the average of its own week, and how many weeks counted.

    Comparing with the week, not with the whole period, keeps a rising or falling rate from
    favouring the days that happen to come later. Weekend entries (a failover provider can
    date a rate on a Saturday) and weeks with fewer than three market days are left out.
    """
    weeks: dict[tuple[int, int], list[DailyRate]] = defaultdict(list)
    for item in rates:
        if item.day.weekday() < len(WEEKDAYS):
            weeks[item.day.isocalendar()[:2]].append(item)

    deviations: dict[int, list[float]] = defaultdict(list)
    counted = 0
    for week in weeks.values():
        if len(week) < MIN_DAYS_PER_WEEK:
            continue
        counted += 1
        mean = statistics.fmean(item.rate for item in week)
        for item in week:
            deviations[item.day.weekday()].append((item.rate / mean - 1) * 100)

    stats = [
        WeekdayStat(
            weekday=name,
            advantage_pct=round(statistics.fmean(values), 3),
            weeks=len(values),
            beat_share=round(sum(value > 0 for value in values) / len(values), 2),
        )
        for index, name in enumerate(WEEKDAYS)
        if (values := deviations[index])
    ]
    return stats, counted


def best_day(
    stats: list[WeekdayStat], weeks: int
) -> tuple[WeekdayStat | None, NoBestDayReason | None]:
    if weeks < MIN_WEEKS:
        return None, "not_enough_history"
    best = max(stats, key=lambda stat: stat.advantage_pct)
    if best.advantage_pct < CLEAR_PATTERN_PCT or best.beat_share <= 0.5:
        return None, "no_clear_pattern"
    return best, None


def build_trends(
    corridor_id: CorridorId, history: dict[str, Any] | None, days: TrendDays, today: date
) -> RemittanceTrends:
    """The trend of one corridor's rate from its stored daily history (steps 4 and 7).

    Raises:
        HistoryNotFoundError: Nothing is stored for the corridor's pair yet.
    """
    pair = pair_for_corridor(corridor_id)
    rates = daily_rates(history)
    if not rates:
        raise HistoryNotFoundError(pair.pair_id)

    since = today - timedelta(days=days)
    in_period = [item for item in rates if item.day > since]
    points = [TrendPoint(date=item.day, rate=item.rate) for item in in_period]

    analysed = [item for item in rates if item.day > today - timedelta(days=ANALYSIS_DAYS)]
    stats, weeks = weekday_stats(analysed)
    best, reason = best_day(stats, weeks)
    return RemittanceTrends(
        corridor_id=corridor_id,
        pair=pair.pair_id,
        base_currency=pair.base,
        quote_currency=pair.quote,
        days=days,
        points=points,
        summary=summarize(points),
        last_date=rates[-1].day,
        best_day=best,
        best_day_reason=reason,
        weeks_analysed=weeks,
        weekdays=stats if weeks >= MIN_WEEKS else [],
        providers=sorted({item.provider for item in in_period}),
    )


async def get_trends(
    corridor_id: CorridorId, days: TrendDays, rates: RateRepository, today: date
) -> RemittanceTrends:
    """Read the pair's history (one Firestore document) and build the trend.

    Raises:
        HistoryNotFoundError: Nothing is stored for the corridor's pair yet.
    """
    pair = pair_for_corridor(corridor_id)
    history = await run_in_threadpool(rates.get_history, pair.pair_id)
    trends = build_trends(corridor_id, history, days, today)
    logger.info(
        "remittance_trends corridor=%s days=%d points=%d weeks=%d best_day=%s",
        corridor_id,
        days,
        len(trends.points),
        trends.weeks_analysed,
        trends.best_day.weekday if trends.best_day else trends.best_day_reason,
    )
    return trends
