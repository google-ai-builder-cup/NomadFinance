from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from app.repositories.corridor_repo import CorridorRepository
from app.repositories.rate_repo import RateRepository
from app.services.remittance.engine import AmountOutOfRangeError, CorridorNotFoundError
from app.services.remittance.savings import get_savings, monthly_averages, target_months
from app.services.remittance.trends import DailyRate, HistoryNotFoundError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)

SOURCE = {"name": "World Bank", "url": "http://remittanceprices.worldbank.org", "attribution": "x"}


def provider(rpw_id: int, firm: str, total_cost_pct: float) -> dict[str, Any]:
    """A synthetic service whose fee/margin add up to `total_cost_pct` at any survey amount."""
    quote = {
        "send_amount_lcu": 200,
        "fee_lcu": 0,
        "fx_margin_pct": total_cost_pct,
        "total_cost_pct": total_cost_pct,
    }
    return {
        "rpw_id": rpw_id,
        "firm": firm,
        "firm_type": "Money Transfer Operator",
        "payment_instrument": "Cash",
        "access_point": "Agent",
        "pickup_method": "Cash",
        "speed": "Same day",
        "network_coverage": None,
        "note": None,
        "payout_currency": "PHP",
        "interbank_rate": 43.0,
        "surveyed_on": "2025-02-10",
        "quote_200": quote,
        "quote_500": quote | {"send_amount_lcu": 500},
    }


def corridor_doc(*providers: dict[str, Any]) -> dict[str, Any]:
    return {
        "corridor_id": "SG-PH",
        "source_currency": "SGD",
        "destination_currency": "PHP",
        "period": "2025_1Q",
        "providers": list(providers),
        "source": SOURCE,
    }


CHEAP_AND_PRICEY = corridor_doc(provider(1, "Cheap", 0.0), provider(2, "Pricey", 10.0))


def history(rates_by_iso_date: dict[str, float]) -> dict[str, Any]:
    daily = {
        day: {"rate": rate, "provider": "frankfurter"} for day, rate in rates_by_iso_date.items()
    }
    return {"base_currency": "SGD", "quote_currency": "PHP", "daily": daily}


class FakeCorridors:
    def __init__(self, doc: dict[str, Any] | None) -> None:
        self.doc = doc

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        return self.doc


class FakeRates:
    def __init__(self, history_doc: dict[str, Any] | None) -> None:
        self.history_doc = history_doc

    def get_history(self, pair_id: str) -> dict[str, Any] | None:
        return self.history_doc


async def run(
    corridors: dict[str, Any] | None,
    rate_history: dict[str, Any] | None,
    amount: float = 500,
    months: int = 3,
) -> Any:
    return await get_savings(
        "SG-PH",
        amount,
        months,
        cast(CorridorRepository, FakeCorridors(corridors)),
        cast(RateRepository, FakeRates(rate_history)),
        NOW,
    )


# target_months -----------------------------------------------------------------------------


def test_target_months_excludes_the_current_month_oldest_first() -> None:
    assert target_months((2026, 9), 3) == [(2026, 6), (2026, 7), (2026, 8)]


def test_target_months_rolls_over_the_year_boundary() -> None:
    assert target_months((2026, 1), 2) == [(2025, 11), (2025, 12)]


def test_target_months_twelve_back_from_january() -> None:
    result = target_months((2026, 1), 12)

    assert result[0] == (2025, 1)
    assert result[-1] == (2025, 12)
    assert len(result) == 12


# monthly_averages ----------------------------------------------------------------------------


def test_monthly_averages_only_covers_requested_months() -> None:
    rates = [
        DailyRate(day=date(2026, 6, 1), rate=40.0, provider="x"),
        DailyRate(day=date(2026, 6, 2), rate=42.0, provider="x"),
        DailyRate(day=date(2026, 7, 15), rate=50.0, provider="x"),
        # Outside the requested window: must not affect the result.
        DailyRate(day=date(2025, 1, 1), rate=999.0, provider="x"),
    ]

    averages = monthly_averages(rates, [(2026, 6), (2026, 7)])

    assert averages == {(2026, 6): 41.0, (2026, 7): 50.0}


# get_savings -----------------------------------------------------------------------------------


async def test_computes_best_minus_worst_per_month_and_totals() -> None:
    rate_history = history(
        {
            "2026-06-10": 40.0,
            "2026-06-20": 40.0,
            "2026-07-15": 41.0,
            "2026-08-01": 42.0,
        }
    )

    result = await run(CHEAP_AND_PRICEY, rate_history)

    assert (result.best_firm, result.worst_firm) == ("Cheap", "Pricey")
    assert (result.best_rpw_id, result.worst_rpw_id) == (1, 2)
    assert result.months_requested == 3
    assert result.months_used == 3
    assert [m.month for m in result.months] == ["2026-06", "2026-07", "2026-08"]
    assert [m.savings for m in result.months] == [2000.0, 2050.0, 2100.0]
    assert result.total_best_receives == 61500.0
    assert result.total_worst_receives == 55350.0
    assert result.total_savings == 6150.0


async def test_months_used_is_less_than_requested_when_history_is_short() -> None:
    rate_history = history({"2026-08-01": 42.0})

    result = await run(CHEAP_AND_PRICEY, rate_history, months=5)

    assert result.months_requested == 5
    assert result.months_used == 1
    assert [m.month for m in result.months] == ["2026-08"]


async def test_the_current_incomplete_month_is_never_used() -> None:
    rate_history = history({"2026-09-15": 100.0, "2026-08-01": 42.0})

    result = await run(CHEAP_AND_PRICEY, rate_history, months=1)

    assert [m.month for m in result.months] == ["2026-08"]


async def test_a_single_comparable_provider_has_zero_savings() -> None:
    rate_history = history({"2026-08-01": 42.0})
    only_one = corridor_doc(provider(1, "OnlyOne", 5.0))

    result = await run(only_one, rate_history, months=1)

    assert result.best_firm == result.worst_firm == "OnlyOne"
    assert result.total_savings == 0.0


async def test_no_history_at_all_is_history_not_found() -> None:
    with pytest.raises(HistoryNotFoundError):
        await run(CHEAP_AND_PRICEY, None)


async def test_history_outside_the_requested_window_is_history_not_found() -> None:
    rate_history = history({"2025-01-01": 40.0})

    with pytest.raises(HistoryNotFoundError):
        await run(CHEAP_AND_PRICEY, rate_history, months=3)


async def test_unknown_corridor_is_corridor_not_found() -> None:
    with pytest.raises(CorridorNotFoundError):
        await run(None, history({"2026-08-01": 42.0}))


async def test_amount_out_of_range_still_propagates() -> None:
    with pytest.raises(AmountOutOfRangeError):
        await run(CHEAP_AND_PRICEY, history({"2026-08-01": 42.0}), amount=1)
