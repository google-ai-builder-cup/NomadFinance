from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from app.constants import CURRENCY_PAIRS, pair_for_corridor
from app.repositories.corridor_repo import CorridorRepository
from app.repositories.rate_repo import RateRepository
from app.schemas.remittance_compare import CorridorDoc, CorridorId, RateDoc
from app.services.remittance.engine import (
    SPEED_ORDER,
    AmountOutOfRangeError,
    CorridorNotFoundError,
    amount_limits,
    calculate_comparison,
    compare_remittance,
)

pytestmark = pytest.mark.anyio

# The committed World Bank data that NF-P1-016 loads into Firestore.
RPW = Path(__file__).resolve().parents[4] / "data-scripts" / "data" / "processed"
DATA: dict[str, Any] = json.loads((RPW / "rpw_corridors.json").read_text(encoding="utf-8"))
RAW = {c["corridor_id"]: c for c in DATA["corridors"]}
CORRIDORS = sorted(RAW)
NOW = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


def real(corridor_id: str) -> CorridorDoc:
    """A corridor as the loader stores it: the parsed file plus its `source` block."""
    return CorridorDoc.model_validate(RAW[corridor_id] | {"source": DATA["source"]})


def rate(value: float = 43.0, age: timedelta | None = timedelta(minutes=30)) -> RateDoc:
    return RateDoc(
        rate=value,
        provider="frankfurter",
        rate_date="2026-09-28",
        fetched_at=None if age is None else NOW - age,
    )


def provider(rpw_id: int, firm: str, **over: Any) -> dict[str, Any]:
    """A synthetic service whose two survey quotes are 200 and 500 SGD."""
    values: dict[str, Any] = {
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
        "quote_200": {
            "send_amount_lcu": 200,
            "fee_lcu": 5,
            "fx_margin_pct": 1,
            "total_cost_pct": 0,
        },
        "quote_500": {
            "send_amount_lcu": 500,
            "fee_lcu": 5,
            "fx_margin_pct": 1,
            "total_cost_pct": 0,
        },
    }
    return values | over


def synthetic(*providers: dict[str, Any]) -> CorridorDoc:
    return CorridorDoc.model_validate(
        {
            "corridor_id": "SG-PH",
            "source_currency": "SGD",
            "destination_currency": "PHP",
            "period": "2025_1Q",
            "providers": list(providers),
            "source": DATA["source"],
        }
    )


def compare(
    corridor: CorridorDoc, amount: float, cached: RateDoc | None = None, cid: CorridorId = "SG-PH"
) -> Any:
    return calculate_comparison(cid, corridor, amount, cached or rate(), NOW)


# The cost model against the survey ------------------------------------------------------


@pytest.mark.parametrize("corridor_id", CORRIDORS)
@pytest.mark.parametrize("quote", ["quote_200", "quote_500"])
def test_reproduces_every_published_total_cost_at_the_two_survey_amounts(
    corridor_id: str, quote: str
) -> None:
    corridor = real(corridor_id)
    published = {p["rpw_id"]: p[quote]["total_cost_pct"] for p in RAW[corridor_id]["providers"]}
    amount = RAW[corridor_id]["providers"][0][quote]["send_amount_lcu"]

    result = compare(corridor, amount, cid=cast(CorridorId, corridor_id))

    assert len(result.providers) == len(published)
    for row in result.providers:
        assert row.total_cost_pct == pytest.approx(published[row.rpw_id], abs=0.011)
        assert not row.estimated


def test_every_service_is_kept_even_when_a_firm_appears_many_times() -> None:
    result = compare(real("SG-PH"), 260)

    assert len(result.providers) == 39
    assert len({row.rpw_id for row in result.providers}) == 39
    assert len({row.firm for row in result.providers}) < 39


def test_a_known_service_at_a_survey_amount() -> None:
    # A-Express Remit, SGD 260: fee 5, margin 0.62%, published total cost 2.54%.
    result = compare(real("SG-PH"), 260, rate(43.0))
    row = next(r for r in result.providers if r.rpw_id == 521252425)

    assert (row.fee, row.fx_margin_pct, row.total_cost_pct) == (5.0, 0.62, 2.54)
    assert row.rate_cost == pytest.approx(1.61, abs=0.005)
    assert row.total_cost == pytest.approx(6.61, abs=0.005)
    exact_pct = 5 / 260 * 100 + 0.62  # the published 2.54 is this, rounded
    assert row.recipient_receives == pytest.approx(260 * 43.0 * (1 - exact_pct / 100), abs=0.01)
    assert row.lost_to_costs == pytest.approx(260 * 43.0 * exact_pct / 100, abs=0.01)


def test_fee_and_margin_are_interpolated_between_the_survey_amounts() -> None:
    steep = provider(
        1,
        "Tiered",
        quote_200={"send_amount_lcu": 200, "fee_lcu": 5, "fx_margin_pct": 1, "total_cost_pct": 0},
        quote_500={"send_amount_lcu": 500, "fee_lcu": 9, "fx_margin_pct": 2, "total_cost_pct": 0},
    )

    row = compare(synthetic(steep), 350).providers[0]

    assert row.fee == 7.0 and row.fx_margin_pct == 1.5
    assert not row.estimated
    assert row.total_cost == pytest.approx(7 + 350 * 0.015, abs=0.005)


def test_outside_the_survey_amounts_the_nearest_survey_point_is_kept_and_marked() -> None:
    steep = provider(
        1,
        "Tiered",
        quote_200={"send_amount_lcu": 200, "fee_lcu": 5, "fx_margin_pct": 1, "total_cost_pct": 0},
        quote_500={"send_amount_lcu": 500, "fee_lcu": 9, "fx_margin_pct": 2, "total_cost_pct": 0},
    )
    corridor = synthetic(steep)

    small, large = compare(corridor, 100).providers[0], compare(corridor, 2000).providers[0]

    assert (small.fee, small.fx_margin_pct, small.estimated) == (5.0, 1.0, True)
    assert (large.fee, large.fx_margin_pct, large.estimated) == (9.0, 2.0, True)


def test_a_flat_fee_weighs_more_on_a_small_amount() -> None:
    corridor = synthetic(provider(1, "Flat"))

    small, large = compare(corridor, 100).providers[0], compare(corridor, 400).providers[0]

    assert small.total_cost_pct == pytest.approx(5 + 1, abs=0.01)
    assert large.total_cost_pct == pytest.approx(5 / 400 * 100 + 1, abs=0.01)


# Limits ---------------------------------------------------------------------------------


def test_limits_are_a_quarter_of_the_lower_survey_amount_to_ten_times_the_upper() -> None:
    assert amount_limits(real("SG-PH")) == (65.0, 6450.0)
    assert amount_limits(real("JP-PH")) == (4250.0, 420000.0)


@pytest.mark.parametrize("amount", [64.99, 6450.01, 1, 10**9])
def test_an_amount_outside_the_limits_is_refused_with_the_limits(amount: float) -> None:
    with pytest.raises(AmountOutOfRangeError) as caught:
        compare(real("SG-PH"), amount)

    assert (caught.value.minimum, caught.value.maximum, caught.value.currency) == (
        65.0,
        6450.0,
        "SGD",
    )


@pytest.mark.parametrize("amount", [65.0, 6450.0])
def test_the_limits_themselves_are_allowed(amount: float) -> None:
    assert compare(real("SG-PH"), amount).providers


# Ranking --------------------------------------------------------------------------------


def test_services_are_ranked_by_what_the_recipient_receives() -> None:
    cheap = provider(1, "Cheap", quote_200=_q(200, 1, 0.5), quote_500=_q(500, 1, 0.5))
    middle = provider(2, "Middle", quote_200=_q(200, 4, 1.0), quote_500=_q(500, 4, 1.0))
    dear = provider(3, "Dear", quote_200=_q(200, 9, 3.0), quote_500=_q(500, 9, 3.0))

    result = compare(synthetic(dear, cheap, middle), 300)

    assert [(r.firm, r.rank) for r in result.providers] == [
        ("Cheap", 1),
        ("Middle", 2),
        ("Dear", 3),
    ]
    received = [r.recipient_receives for r in result.providers]
    assert received == sorted(received, reverse=True)


def _q(amount: float, fee: float, margin: float) -> dict[str, float]:
    return {
        "send_amount_lcu": amount,
        "fee_lcu": fee,
        "fx_margin_pct": margin,
        "total_cost_pct": 0,
    }


def test_a_tie_goes_to_the_faster_service_then_to_the_name() -> None:
    slow = provider(1, "Alpha", speed="3-5 days")
    fast = provider(2, "Zulu", speed="Less than one hour")
    same_a = provider(3, "Bravo", speed="Same day")
    same_b = provider(4, "Alpha", speed="Same day")

    result = compare(synthetic(slow, fast, same_a, same_b), 300)

    assert [r.firm for r in result.providers] == ["Zulu", "Alpha", "Bravo", "Alpha"]
    assert [r.speed for r in result.providers][:2] == ["Less than one hour", "Same day"]
    assert [r.rank for r in result.providers] == [1, 2, 3, 4]


@pytest.mark.parametrize("corridor_id", CORRIDORS)
def test_the_order_never_depends_on_the_live_rate(corridor_id: str) -> None:
    corridor = real(corridor_id)
    amount = RAW[corridor_id]["providers"][0]["quote_200"]["send_amount_lcu"] * 1.3
    cid = cast(CorridorId, corridor_id)

    one = calculate_comparison(cid, corridor, amount, rate(1.0), NOW)
    other = calculate_comparison(cid, corridor, amount, rate(987.65), NOW)

    assert [r.rpw_id for r in one.providers] == [r.rpw_id for r in other.providers]


@pytest.mark.parametrize("corridor_id", CORRIDORS)
def test_ranks_are_one_to_n_and_amounts_fall_down_the_list(corridor_id: str) -> None:
    amount = RAW[corridor_id]["providers"][0]["quote_500"]["send_amount_lcu"]

    result = calculate_comparison(
        cast(CorridorId, corridor_id), real(corridor_id), amount, rate(), NOW
    )

    ranked = [r for r in result.providers if r.rank is not None]
    assert [r.rank for r in ranked] == list(range(1, len(ranked) + 1))
    received = [r.recipient_receives for r in ranked if r.recipient_receives is not None]
    assert len(received) == len(ranked)
    assert received == sorted(received, reverse=True)
    assert ranked[0].less_than_best == 0
    assert all(r.less_than_best is not None and r.less_than_best >= 0 for r in ranked)


def test_a_service_paying_out_in_another_currency_is_listed_last_and_not_ranked() -> None:
    result = compare(real("SG-PH"), 260)

    unranked = [r for r in result.providers if not r.comparable]
    assert [r.firm for r in unranked] == ["DBS"]
    assert result.providers[-1] is unranked[0]
    dbs = unranked[0]
    assert dbs.rank is None and dbs.recipient_receives is None
    assert dbs.lost_to_costs is None and dbs.less_than_best is None
    assert dbs.payout_currency == "USD"
    assert dbs.total_cost_pct > 0  # its cost is still shown
    assert result.summary.comparable_count == 38


def test_japan_lists_its_four_dollar_payout_services_after_the_ranked_ones() -> None:
    result = compare(real("JP-PH"), 17000, cid="JP-PH")

    flags = [r.comparable for r in result.providers]
    assert flags == sorted(flags, reverse=True)
    assert flags.count(False) == 4
    tail = [r.total_cost_pct for r in result.providers if not r.comparable]
    assert tail == sorted(tail)


def test_a_corridor_with_nothing_comparable_is_reported_as_unavailable() -> None:
    dollars = provider(1, "Dollars", payout_currency="USD")

    with pytest.raises(CorridorNotFoundError):
        compare(synthetic(dollars), 300)


def test_a_service_cheaper_than_mid_market_is_shown_as_it_is() -> None:
    # InstaReM on AU-IN was surveyed at a total cost of -0.24%.
    result = compare(real("AU-IN"), 200, rate(55.0), cid="AU-IN")
    row = next(r for r in result.providers if r.total_cost_pct < 0)

    assert row.recipient_receives is not None
    assert row.recipient_receives > result.summary.mid_market_receives
    assert row.lost_to_costs is not None and row.lost_to_costs < 0
    assert row.rank == 1


# The live rate --------------------------------------------------------------------------


def test_a_fresh_cached_rate_is_used_and_not_stale() -> None:
    result = compare(real("SG-PH"), 260, rate(43.25, timedelta(hours=1)))

    assert (result.rate.source, result.rate.provider) == ("live", "frankfurter")
    assert result.rate.rate == 43.25 and result.rate.pair == "SGD_PHP"
    assert result.rate.stale is False
    assert result.summary.mid_market_receives == pytest.approx(260 * 43.25, abs=0.01)


@pytest.mark.parametrize(
    ("age", "stale"),
    [
        (timedelta(hours=5, minutes=59), False),
        (timedelta(hours=6, minutes=1), True),
        (timedelta(days=3), True),
        (None, True),
    ],
)
def test_a_rate_older_than_six_hours_is_flagged_stale(age: timedelta | None, stale: bool) -> None:
    assert compare(real("SG-PH"), 260, rate(43.0, age)).rate.stale is stale


def test_a_naive_timestamp_is_read_as_utc() -> None:
    naive = RateDoc(
        rate=43.0,
        provider="frankfurter",
        rate_date="2026-09-28",
        fetched_at=(NOW - timedelta(hours=1)).replace(tzinfo=None),
    )

    assert compare(real("SG-PH"), 260, naive).rate.stale is False


def test_without_a_cached_rate_the_survey_median_is_used_and_flagged() -> None:
    corridor = real("SG-PH")

    result = calculate_comparison("SG-PH", corridor, 260, None, NOW)

    assert result.rate.source == "survey" and result.rate.stale is True
    assert result.rate.provider is None and result.rate.fetched_at is None
    assert 42.9 < result.rate.rate < 43.5  # the survey's SGD/PHP range
    assert result.providers  # and the comparison still works


def test_the_survey_rate_ignores_services_that_pay_out_in_dollars() -> None:
    pesos = [provider(1, "A", interbank_rate=43.0), provider(2, "B", interbank_rate=43.4)]
    dollars = [
        provider(n, f"D{n}", payout_currency="USD", interbank_rate=0.74) for n in range(3, 8)
    ]

    result = calculate_comparison("SG-PH", synthetic(*pesos, *dollars), 300, None, NOW)

    assert result.rate.rate == pytest.approx(43.2)


# Summary, survey and rounding -----------------------------------------------------------


def test_the_summary_names_the_best_and_worst_and_their_difference() -> None:
    result = compare(real("SG-PH"), 260, rate(43.0))
    ranked = [r for r in result.providers if r.rank is not None]
    summary = result.summary

    assert (summary.best_rpw_id, summary.best_firm) == (ranked[0].rpw_id, ranked[0].firm)
    assert (summary.worst_rpw_id, summary.worst_firm) == (ranked[-1].rpw_id, ranked[-1].firm)
    assert summary.best_recipient_receives == ranked[0].recipient_receives
    assert summary.worst_recipient_receives == ranked[-1].recipient_receives
    assert summary.extra_vs_worst == pytest.approx(
        summary.best_recipient_receives - summary.worst_recipient_receives, abs=0.011
    )
    assert summary.extra_vs_worst > 0
    assert summary.comparable_count == len(ranked)
    assert summary.mid_market_receives == pytest.approx(260 * 43.0, abs=0.01)
    costs = sorted(r.total_cost_pct for r in ranked)
    assert costs[0] <= summary.median_total_cost_pct <= costs[-1]


def test_the_survey_block_carries_the_period_dates_and_attribution() -> None:
    survey = compare(real("SG-PH"), 260).survey

    assert survey.period == "2025_1Q"
    assert (survey.surveyed_from, survey.surveyed_to) == ("2025-02-05", "2025-02-28")
    assert survey.source_name == "World Bank Remittance Prices Worldwide"
    assert survey.attribution.startswith("The World Bank, Remittance Prices Worldwide")
    assert survey.source_url.startswith("http")


def test_amounts_are_rounded_to_two_decimals_and_the_rate_to_six() -> None:
    result = compare(real("MY-ID"), 1000.123456, rate(3700.123456789))

    def decimals(value: float) -> int:
        return len(repr(value).split(".")[1]) if "." in repr(value) else 0

    for row in result.providers:
        for value in (
            row.fee,
            row.fx_margin_pct,
            row.rate_cost,
            row.total_cost,
            row.total_cost_pct,
        ):
            assert decimals(value) <= 2
        if row.recipient_receives is not None:
            assert decimals(row.recipient_receives) <= 2
    assert decimals(result.rate.rate) <= 6
    assert decimals(result.summary.extra_vs_worst) <= 2


def test_delivery_speeds_sort_by_number() -> None:
    result = compare(real("SG-PH"), 260)

    for row in result.providers:
        assert row.speed_order == SPEED_ORDER.index(row.speed)
    assert SPEED_ORDER[0] == "Less than one hour" and SPEED_ORDER[-1] == "6 days or more"
    unknown = provider(9, "Odd", speed="By carrier pigeon")
    assert compare(synthetic(unknown), 300).providers[0].speed_order == len(SPEED_ORDER)


def test_the_result_repeats_exactly_for_the_same_request() -> None:
    first = compare(real("AU-PH"), 350, cid="AU-PH")
    second = compare(real("AU-PH"), 350, cid="AU-PH")

    assert first.model_dump() == second.model_dump()


# The six corridors and their FX pairs ---------------------------------------------------


def test_each_corridor_maps_to_its_currency_pair() -> None:
    assert {pair_for_corridor(c).pair_id for c in CORRIDORS} == {p.pair_id for p in CURRENCY_PAIRS}
    assert pair_for_corridor("SG-PH").pair_id == "SGD_PHP"
    assert pair_for_corridor("JP-PH").pair_id == "JPY_PHP"
    with pytest.raises(KeyError):
        pair_for_corridor("KR-NP")


@pytest.mark.parametrize("corridor_id", CORRIDORS)
def test_the_pair_currencies_match_the_corridor_document(corridor_id: str) -> None:
    pair, corridor = pair_for_corridor(corridor_id), real(corridor_id)

    assert (pair.base, pair.quote) == (corridor.source_currency, corridor.destination_currency)


# Reading from Firestore -----------------------------------------------------------------


class FakeCorridors:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self.docs = docs
        self.calls: list[str] = []

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        self.calls.append(corridor_id)
        return self.docs.get(corridor_id)


class FakeRates:
    def __init__(self, docs: dict[str, dict[str, Any]]) -> None:
        self.docs = docs
        self.calls: list[str] = []

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        self.calls.append(pair_id)
        return self.docs.get(pair_id)


def stored(corridor_id: str) -> dict[str, Any]:
    doc: dict[str, Any] = RAW[corridor_id] | {"source": DATA["source"]}
    return doc


async def run(
    corridors: FakeCorridors,
    rates: FakeRates,
    corridor_id: CorridorId = "SG-PH",
    amount: float = 260,
) -> Any:
    return await compare_remittance(
        corridor_id,
        amount,
        cast(CorridorRepository, corridors),
        cast(RateRepository, rates),
        NOW,
    )


async def test_reads_the_corridor_and_the_rate_of_its_pair() -> None:
    corridors = FakeCorridors({"SG-PH": stored("SG-PH")})
    rates = FakeRates(
        {
            "SGD_PHP": {
                "rate": 43.1,
                "provider": "wise",
                "rate_date": "2026-09-28",
                "fetched_at": NOW - timedelta(minutes=10),
            }
        }
    )

    result = await run(corridors, rates)

    assert corridors.calls == ["SG-PH"] and rates.calls == ["SGD_PHP"]
    assert result.rate.source == "live" and result.rate.provider == "wise"
    assert result.summary.comparable_count == 38


async def test_an_unloaded_corridor_is_reported_before_any_rate_is_read() -> None:
    rates = FakeRates({})

    with pytest.raises(CorridorNotFoundError):
        await run(FakeCorridors({}), rates)

    assert rates.calls == []


async def test_a_missing_rate_falls_back_to_the_survey() -> None:
    result = await run(FakeCorridors({"SG-PH": stored("SG-PH")}), FakeRates({}))

    assert result.rate.source == "survey" and result.rate.stale is True


async def test_an_amount_out_of_range_raises_with_the_currency() -> None:
    with pytest.raises(AmountOutOfRangeError, match="SGD"):
        await run(FakeCorridors({"SG-PH": stored("SG-PH")}), FakeRates({}), amount=5)


async def test_a_damaged_corridor_document_is_an_error_not_a_wrong_answer() -> None:
    broken = {"corridor_id": "SG-PH", "providers": "not a list"}

    with pytest.raises(ValueError):  # pydantic.ValidationError is a ValueError
        await run(FakeCorridors({"SG-PH": broken}), FakeRates({}))


async def test_the_log_line_never_holds_the_amount(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.remittance.engine")

    await run(FakeCorridors({"SG-PH": stored("SG-PH")}), FakeRates({}), amount=1234.56)

    text = " ".join(record.getMessage() for record in caplog.records)
    assert "remittance_compare corridor=SG-PH" in text
    assert "1234" not in text
