from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.schemas.remittance_trends import TrendDays
from app.services.remittance.trends import (
    HistoryNotFoundError,
    build_trends,
    daily_rates,
)

TODAY = date(2026, 9, 28)  # a Monday


def market_days(weeks: int, end: date = TODAY) -> list[date]:
    """Monday to Friday for `weeks` whole weeks, ending the Friday before `end`."""
    friday = end - timedelta(days=(end.weekday() - 4) % 7 or 7)
    start = friday - timedelta(weeks=weeks) + timedelta(days=3)
    days = [start + timedelta(days=i) for i in range((friday - start).days + 1)]
    return [day for day in days if day.weekday() < 5]


def history(
    days: list[date],
    *,
    base: float = 43.0,
    trend_per_day: float = 0.0,
    bump: dict[int, float] | None = None,
    provider: str = "frankfurter",
) -> dict[str, Any]:
    """A rates_history header whose daily rate drifts by `trend_per_day` percent a day, with
    `bump` adding a percentage on given weekdays (0 = Monday)."""
    bump = bump or {}
    daily = {}
    for index, day in enumerate(days):
        rate = base * (1 + trend_per_day / 100) ** index * (1 + bump.get(day.weekday(), 0) / 100)
        daily[day.isoformat()] = {"rate": rate, "provider": provider, "source": "backfill"}
    return {"base_currency": "SGD", "quote_currency": "PHP", "daily": daily}


def test_daily_rates_are_sorted_and_damaged_entries_skipped() -> None:
    doc = {
        "daily": {
            "2026-09-25": {"rate": 43.2, "provider": "frankfurter"},
            "2026-09-24": {"rate": 43.1, "provider": "exchangerate_api"},
            "not-a-date": {"rate": 43.0},
            "2026-09-23": {"rate": -1},
            "2026-09-22": {"provider": "frankfurter"},
            "2026-09-21": "43.0",
        }
    }

    rates = daily_rates(doc)

    assert [(r.day.isoformat(), r.rate, r.provider) for r in rates] == [
        ("2026-09-24", 43.1, "exchangerate_api"),
        ("2026-09-25", 43.2, "frankfurter"),
    ]


@pytest.mark.parametrize("doc", [None, {}, {"daily": {}}, {"daily": "broken"}])
def test_no_history_raises(doc: dict[str, Any] | None) -> None:
    with pytest.raises(HistoryNotFoundError):
        build_trends("SG-PH", doc, TrendDays(90), TODAY)


def test_points_cover_only_the_period_and_the_summary_matches_them() -> None:
    days = market_days(20)
    doc = history(days, trend_per_day=0.1)

    trends = build_trends("SG-PH", doc, TrendDays(30), TODAY)

    assert (trends.pair, trends.base_currency, trends.quote_currency) == ("SGD_PHP", "SGD", "PHP")
    assert trends.points[0].date > TODAY - timedelta(days=30)
    assert [p.date for p in trends.points] == sorted(p.date for p in trends.points)
    assert len(trends.points) == len([d for d in days if d > TODAY - timedelta(days=30)])
    summary = trends.summary
    assert summary is not None
    assert summary.first == trends.points[0] and summary.latest == trends.points[-1]
    assert summary.low == trends.points[0] and summary.high == trends.points[-1]  # rising
    assert summary.change_pct == pytest.approx(
        (summary.latest.rate / summary.first.rate - 1) * 100, abs=0.001
    )
    assert trends.last_date == days[-1]
    assert trends.providers == ["frankfurter"]


def test_a_period_without_points_still_answers_with_the_last_date() -> None:
    days = market_days(20, end=TODAY - timedelta(days=60))

    trends = build_trends("SG-PH", history(days), TrendDays(30), TODAY)

    assert trends.points == [] and trends.summary is None
    assert trends.last_date == days[-1]


def test_too_few_weeks_gives_no_best_day() -> None:
    trends = build_trends("SG-PH", history(market_days(5), bump={2: 0.5}), TrendDays(90), TODAY)

    assert trends.best_day is None
    assert trends.best_day_reason == "not_enough_history"
    assert trends.weekdays == []
    assert trends.weeks_analysed == 5


def test_a_weekday_that_is_reliably_better_is_the_best_day() -> None:
    doc = history(market_days(30), trend_per_day=-0.05, bump={2: 0.3})

    trends = build_trends("SG-PH", doc, TrendDays(90), TODAY)

    assert trends.best_day is not None
    assert trends.best_day.weekday == "wednesday"
    assert trends.best_day.advantage_pct == pytest.approx(0.24, abs=0.01)
    assert trends.best_day.beat_share == 1.0
    assert trends.best_day.weeks == 30
    assert trends.best_day_reason is None
    assert [s.weekday for s in trends.weekdays] == [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
    ]


def test_a_steady_trend_alone_does_not_make_a_best_day() -> None:
    # A rising rate makes Friday the best day on raw averages; against its own week, every
    # weekday's lead is small and the answer is "no clear pattern" rather than a false tip.
    trends = build_trends(
        "SG-PH", history(market_days(30), trend_per_day=0.01), TrendDays(90), TODAY
    )

    assert trends.best_day is None
    assert trends.best_day_reason == "no_clear_pattern"
    assert len(trends.weekdays) == 5


def test_weekend_rates_are_charted_but_not_compared() -> None:
    days = market_days(10)
    doc = history(days, bump={1: 0.4})
    saturday = days[-1] + timedelta(days=1)
    doc["daily"][saturday.isoformat()] = {"rate": 99.0, "provider": "exchangerate_api"}

    trends = build_trends("SG-PH", doc, TrendDays(30), TODAY)

    assert trends.points[-1].date == saturday
    assert trends.providers == ["exchangerate_api", "frankfurter"]
    assert trends.best_day is not None and trends.best_day.weekday == "tuesday"


def test_weeks_with_fewer_than_three_market_days_are_left_out() -> None:
    days = market_days(10)
    short_week = {d for d in days[:5] if d.weekday() > 1}  # keep only Mon and Tue of week 1
    kept = [d for d in days if d not in short_week]
    trends = build_trends("SG-PH", history(kept), TrendDays(90), TODAY)

    assert trends.weeks_analysed == 9


def test_only_the_last_52_weeks_are_analysed() -> None:
    old = market_days(40, end=TODAY - timedelta(weeks=60))
    recent = market_days(6)
    doc = history(old, bump={0: 0.5})
    doc["daily"].update(history(recent)["daily"])

    trends = build_trends("SG-PH", doc, TrendDays(365), TODAY)

    assert trends.weeks_analysed == 6
    assert trends.best_day_reason == "not_enough_history"


@pytest.mark.parametrize("corridor", ["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"])
def test_every_corridor_maps_to_its_pair(corridor: str) -> None:
    trends = build_trends(corridor, history(market_days(2)), TrendDays(30), TODAY)  # type: ignore[arg-type]

    assert trends.pair == f"{trends.base_currency}_{trends.quote_currency}"
    assert trends.corridor_id == corridor
