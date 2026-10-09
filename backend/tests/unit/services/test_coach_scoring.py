"""The preparedness score: every rule of the rubric (docs/features/coach-scoring.md, v1)."""

from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

import pytest

from app.services.coach.scoring import (
    BANKED,
    BUFFER_MONTHS,
    DEBT_MONTHS,
    FEE_EXCESS_MONTHS,
    REMITTANCE_SHARE,
    WEIGHTS,
    NotScorableError,
    ScoreInputs,
    band_of,
    half_up,
    interpolate,
    score_inputs,
)

# A worker with nothing owed, plenty saved, a modest remittance, a fee at the cap, a bank account.
BASE = ScoreInputs(
    monthly_salary=2000.0,
    remittance_target=500.0,
    recruitment_fee=0.0,
    debt=0.0,
    savings=20000.0,
    debt_rate_yearly_percent=None,
    account="bank_account",
    essentials=500.0,
    fee_cap_months=1.0,
)


def points(score: Any) -> dict[str, float]:
    return {f.id: f.score for f in score.factors}


def with_(**changes: Any) -> ScoreInputs:
    return replace(BASE, **changes)


# --- the factors, at their anchors -------------------------------------------------------------


@pytest.mark.parametrize(("months", "expected"), DEBT_MONTHS)
def test_the_debt_factor_hits_each_anchor(months: float, expected: float) -> None:
    result = score_inputs(with_(debt=months * 2000.0))

    assert points(result)["debt_to_income"] == expected


@pytest.mark.parametrize(("months", "expected"), BUFFER_MONTHS)
def test_the_buffer_factor_hits_each_anchor(months: float, expected: float) -> None:
    result = score_inputs(with_(savings=months * (500.0 + 500.0)))  # outgoings 1,000

    assert points(result)["emergency_buffer"] == expected


@pytest.mark.parametrize(("share", "expected"), REMITTANCE_SHARE)
def test_the_remittance_factor_hits_each_anchor(share: float, expected: float) -> None:
    result = score_inputs(with_(remittance_target=share * 2000.0, essentials=0.0))

    assert points(result)["remittance_ratio"] == expected


@pytest.mark.parametrize(("excess", "expected"), FEE_EXCESS_MONTHS)
def test_the_fee_factor_hits_each_anchor(excess: float, expected: float) -> None:
    result = score_inputs(with_(recruitment_fee=(1.0 + excess) * 2000.0))

    assert points(result)["recruitment_fee_vs_cap"] == expected


@pytest.mark.parametrize("kind", list(BANKED))
def test_the_account_factor(kind: str) -> None:
    result = score_inputs(with_(account=kind))

    factor = next(f for f in result.factors if f.id == "banked_status")
    assert (factor.value, factor.score) == (BANKED[kind][0], BANKED[kind][1])


def test_points_between_two_anchors_are_on_a_line_and_outside_them_flat() -> None:
    assert interpolate(DEBT_MONTHS, 2.0) == 72.5  # between (1, 85) and (3, 60)
    assert interpolate(DEBT_MONTHS, -1) == 100 and interpolate(DEBT_MONTHS, 40) == 0


# --- the extra rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("yearly", "expected"),
    [(None, 85), (0, 85), (12, 85), (23.9, 85), (24, 75), (47.9, 75), (48, 65)],
)
def test_a_costly_debt_loses_points_by_its_yearly_rate(
    yearly: float | None, expected: float
) -> None:
    result = score_inputs(with_(debt=2000.0, debt_rate_yearly_percent=yearly))

    assert points(result)["debt_to_income"] == expected


def test_the_interest_penalty_never_takes_the_points_below_zero() -> None:
    result = score_inputs(with_(debt=40000.0, debt_rate_yearly_percent=60))

    assert points(result)["debt_to_income"] == 0


def test_a_rate_with_no_debt_costs_nothing() -> None:
    result = score_inputs(with_(debt=0.0, debt_rate_yearly_percent=60))

    assert points(result)["debt_to_income"] == 100


def test_sending_more_than_can_be_afforded_caps_the_remittance_points_at_25() -> None:
    # Pay 2,000, living costs 1,500, sending 500: the share (0.25) alone would score 100.
    affordable = score_inputs(with_(essentials=1500.0, remittance_target=500.0))
    short = score_inputs(with_(essentials=1500.0, remittance_target=600.0))

    assert points(affordable)["remittance_ratio"] == 100
    assert points(short)["remittance_ratio"] == 25  # 0.3 share is 100 points, capped


def test_the_cap_never_lifts_a_factor_that_is_already_lower() -> None:
    result = score_inputs(with_(essentials=1500.0, remittance_target=1800.0))  # share 0.9 = 0

    assert points(result)["remittance_ratio"] == 0


def test_a_worker_who_spends_nothing_does_not_divide_by_zero() -> None:
    result = score_inputs(with_(essentials=0.0, remittance_target=0.0, savings=1000.0))

    buffer = next(f for f in result.factors if f.id == "emergency_buffer")
    assert buffer.value == 2.0  # 1,000 over a quarter of the pay (500)


def test_pay_of_zero_cannot_be_scored() -> None:
    with pytest.raises(NotScorableError):
        score_inputs(with_(monthly_salary=0.0))


# --- the total, the band and the rounding ------------------------------------------------------


def test_the_weights_add_up_to_one() -> None:
    assert sum(WEIGHTS.values()) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("number", "expected"), [(59.25, 59), (90.5, 91), (0.5, 1), (0.49, 0), (22.0, 22)]
)
def test_rounding_is_half_up_not_half_to_even(number: float, expected: int) -> None:
    assert half_up(number) == expected


@pytest.mark.parametrize(
    ("total", "points", "band"),
    [
        (0, [50] * 5, "needs_work"),
        (39, [50] * 5, "needs_work"),
        (40, [50] * 5, "getting_ready"),
        (69, [50] * 5, "getting_ready"),
        (70, [50] * 5, "well_prepared"),
        (100, [100] * 5, "well_prepared"),
        (91, [100, 100, 100, 100, 19], "getting_ready"),  # the floor rule
        (91, [100, 100, 100, 100, 20], "well_prepared"),
        (30, [100, 100, 0, 0, 0], "needs_work"),  # the floor holds a band down, never up
    ],
)
def test_the_band_follows_the_total_and_the_floor_rule(
    total: int, points: list[int], band: str
) -> None:
    assert band_of(total, points) == band


def test_the_score_carries_its_version_and_five_whole_number_factors() -> None:
    result = score_inputs(BASE)

    assert result.rubric_version == 1
    assert [f.id for f in result.factors] == list(WEIGHTS)
    assert all(f.score == int(f.score) and 0 <= f.score <= 100 for f in result.factors)
    assert [f.weight for f in result.factors] == list(WEIGHTS.values())


# --- the worked example of the rubric page -----------------------------------------------------


def test_the_rubric_pages_worked_example_scores_59_and_getting_ready() -> None:
    """An Indian care worker in Australia, 1 AUD = 54 INR (the amounts are already in AUD)."""
    result = score_inputs(
        ScoreInputs(
            monthly_salary=4200.0,
            remittance_target=900.0,
            recruitment_fee=150000 / 54,
            debt=120000 / 54,
            savings=25000 / 54,
            debt_rate_yearly_percent=36.0,
            account="bank_account",
            essentials=2062.0,
            fee_cap_months=0.0,
        )
    )

    assert [f.score for f in result.factors] == [82, 5, 100, 47, 90]
    assert (result.total, result.band) == (59, "getting_ready")


# --- properties, on many random workers --------------------------------------------------------


def _random_inputs(rng: random.Random) -> ScoreInputs:
    salary = rng.uniform(100, 12000)
    return ScoreInputs(
        monthly_salary=salary,
        remittance_target=rng.uniform(0, 1.2) * salary,
        recruitment_fee=rng.choice([0.0, rng.uniform(0, 6) * salary]),
        debt=rng.choice([0.0, rng.uniform(0, 20) * salary]),
        savings=rng.choice([0.0, rng.uniform(0, 12) * salary]),
        debt_rate_yearly_percent=rng.choice([None, 0.0, rng.uniform(0, 120)]),
        account=rng.choice(list(BANKED)),
        essentials=rng.uniform(0, 1.2) * salary,
        fee_cap_months=rng.choice([0.0, 0.1, 1.0, 2.0]),
    )


CASES = [_random_inputs(random.Random(seed)) for seed in range(2000)]


def test_the_score_is_always_a_whole_number_from_0_to_100_and_never_changes() -> None:
    for inputs in CASES:
        first, again = score_inputs(inputs), score_inputs(inputs)

        assert first == again
        assert isinstance(first.total, int) and 0 <= first.total <= 100
        assert all(0 <= f.score <= 100 and f.score == int(f.score) for f in first.factors)


@pytest.mark.parametrize(
    ("field", "worse"),
    [
        ("debt", lambda v: v * 1.5 + 100),
        ("recruitment_fee", lambda v: v * 1.5 + 100),
        ("remittance_target", lambda v: v * 1.5 + 50),
    ],
)
def test_more_debt_a_bigger_fee_or_a_bigger_remittance_never_raises_the_score(
    field: str, worse: Any
) -> None:
    for inputs in CASES:
        before = score_inputs(inputs).total
        after = score_inputs(replace(inputs, **{field: worse(getattr(inputs, field))})).total

        assert after <= before, (field, inputs)


def test_less_savings_never_raises_the_score() -> None:
    for inputs in CASES:
        assert score_inputs(replace(inputs, savings=inputs.savings * 0.5)).total <= (
            score_inputs(inputs).total
        )


def test_a_worse_account_never_raises_the_score() -> None:
    order = ["none", "mobile_wallet", "bank_account", "both"]
    for inputs in CASES[:300]:
        totals = [score_inputs(replace(inputs, account=a)).total for a in order]

        assert totals == sorted(totals)


def test_a_higher_interest_never_raises_the_score() -> None:
    for inputs in CASES:
        low = score_inputs(replace(inputs, debt_rate_yearly_percent=5.0)).total
        high = score_inputs(replace(inputs, debt_rate_yearly_percent=80.0)).total

        assert high <= low


def test_a_looser_fee_cap_never_lowers_the_score() -> None:
    for inputs in CASES:
        assert score_inputs(replace(inputs, fee_cap_months=2.0)).total >= (
            score_inputs(replace(inputs, fee_cap_months=0.0)).total
        )
