"""The figures of the 90-day plan: its rules (NF-FC-012)."""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.services.coach.plan_figures import (
    SEND_WEEKS,
    PlanInputs,
    Quote,
    compute_figures,
    months_to_clear,
    weeks_to_target,
)

# The mock of the contract (docs/mocks/coach/plan-01-created.json): an Indian care worker in
# Australia, pay 4,200, costs 2,155, sending 900.
COSTS = (
    ("accommodation", 1100.0),
    ("food", 450.0),
    ("transport", 160.0),
    ("phone_data", 45.0),
    ("deductions", 400.0),
)
BASE = PlanInputs(
    currency="AUD",
    salary=4200.0,
    remittance=900.0,
    recruitment_fee=2721.43,
    debt=2177.07,
    savings=454.0,
    debt_rate_yearly_percent=36.0,
    costs=COSTS,
    setup_costs=600.0,
    fee_cap_months=0.0,
)
QUOTE = Quote(
    slug="example-remit",
    name="Example Remit",
    fee=6.0,
    receives=48991.2,
    receive_currency="INR",
    quoted_at=datetime(2026, 10, 20, 9, 8, tzinfo=UTC),
)


def goals(figures: object) -> dict[str, float]:
    return {line.id: line.amount.amount for line in figures.budget.goals}  # type: ignore[attr-defined]


def test_the_contract_mock_worker_gets_the_mocks_figures() -> None:
    figures = compute_figures(BASE, "AU-IN", QUOTE)

    assert figures.available == 1145.0
    assert goals(figures) == {"remittance": 900.0, "debt_payment": 801.0, "emergency_fund": 286.0}
    assert figures.budget.left_over.amount == 58.0  # 1,145 - 801 - 286
    assert figures.emergency_fund.target.amount == 6465.0  # 3 x 2,155
    assert (
        figures.emergency_fund.weeks_to_target == 92
    )  # (6,465 - 454) / 286 = 21.02 months x 52/12
    assert figures.debt is not None and figures.debt.months_to_clear == 3
    assert [send.week for send in figures.remittance.schedule] == list(SEND_WEEKS)
    assert figures.budget.setup_costs is not None and figures.budget.setup_costs.amount == 600.0


def test_the_months_to_clear_and_weeks_to_target_formulas_match_the_mock() -> None:
    assert months_to_clear(2177.07, 500.0, 3.0) == 5
    assert weeks_to_target(6465.0, 454.0, 400.0) == 66


@pytest.mark.parametrize(
    ("debt", "payment", "rate", "expected"),
    [
        (1000.0, 100.0, 0.0, 10),
        (1000.0, 250.0, 0.0, 4),
        (1000.0, 30.0, 3.0, None),  # 30 only pays the 3% interest
        (0.0, 100.0, 0.0, None),
        (1000.0, 0.0, 0.0, None),
    ],
)
def test_months_to_clear(debt: float, payment: float, rate: float, expected: int | None) -> None:
    assert months_to_clear(debt, payment, rate) == expected


def test_a_payment_just_above_the_interest_takes_very_long() -> None:
    months = months_to_clear(1000.0, 31.0, 3.0)

    assert months is not None and months > 100


def test_weeks_to_target() -> None:
    assert weeks_to_target(1000.0, 1000.0, 0.0) == 0
    assert weeks_to_target(1000.0, 1500.0, 0.0) == 0
    assert weeks_to_target(1000.0, 0.0, 0.0) is None
    assert weeks_to_target(1300.0, 0.0, 100.0) == 57  # 13 months x 52/12 = 56.33, up


def test_a_costly_debt_is_paid_first_and_the_split_never_goes_over_what_is_left() -> None:
    figures = compute_figures(BASE, "AU-IN", QUOTE)  # 36% a year is costly
    cheap = compute_figures(replace(BASE, debt_rate_yearly_percent=12.0), "AU-IN", QUOTE)

    assert goals(figures)["debt_payment"] == 801.0  # 70% of 1,145
    assert goals(cheap)["debt_payment"] == 572.0  # 50%
    assert goals(cheap)["emergency_fund"] == 458.0  # 40%
    assert figures.budget.left_over.amount >= 0 and cheap.budget.left_over.amount >= 0


def test_the_debt_payment_never_passes_the_whole_debt_with_a_months_interest() -> None:
    figures = compute_figures(replace(BASE, debt=200.0, debt_rate_yearly_percent=None), None, None)

    assert goals(figures)["debt_payment"] == 200.0
    assert figures.debt is not None and figures.debt.months_to_clear == 1


def test_no_debt_means_no_debt_line_and_a_bigger_fund() -> None:
    figures = compute_figures(replace(BASE, debt=0.0), "AU-IN", QUOTE)

    assert figures.debt is None
    assert set(goals(figures)) == {"remittance", "emergency_fund"}
    assert goals(figures)["emergency_fund"] == 916.0  # 80% of 1,145


def test_when_costs_and_the_remittance_pass_the_pay_there_is_a_gap_and_no_other_goal() -> None:
    figures = compute_figures(replace(BASE, remittance=2500.0), None, None)

    assert figures.available == -455.0
    assert goals(figures) == {"remittance": 2500.0, "debt_payment": 0.0, "emergency_fund": 0.0}
    assert figures.budget.left_over.amount == -455.0
    assert figures.debt is not None and figures.debt.months_to_clear is None


def test_no_remittance_means_no_schedule() -> None:
    figures = compute_figures(replace(BASE, remittance=0.0), "AU-IN", None)

    assert figures.remittance.schedule == []
    assert figures.remittance.provider is None


def test_the_provider_is_quoted_only_with_a_corridor() -> None:
    with_corridor = compute_figures(BASE, "AU-IN", QUOTE)
    without = compute_figures(BASE, None, QUOTE)

    provider = with_corridor.remittance.provider
    assert provider is not None and provider.fee.amount == 6.0
    assert provider.receives.currency == "INR"
    assert provider.fx_rate == pytest.approx(48991.2 / 894.0, rel=1e-6)
    assert without.remittance.provider is None


def test_setup_costs_are_left_out_when_there_are_none() -> None:
    assert compute_figures(replace(BASE, setup_costs=0.0), None, None).budget.setup_costs is None


def _random(rng: random.Random) -> PlanInputs:
    salary = rng.uniform(300, 9000)
    return PlanInputs(
        currency="SGD",
        salary=salary,
        remittance=rng.choice([0.0, rng.uniform(0, 1.2) * salary]),
        recruitment_fee=rng.uniform(0, 5) * salary,
        debt=rng.choice([0.0, rng.uniform(0, 12) * salary]),
        savings=rng.choice([0.0, rng.uniform(0, 8) * salary]),
        debt_rate_yearly_percent=rng.choice([None, 0.0, rng.uniform(0, 120)]),
        costs=tuple((name, rng.uniform(0, 0.3) * salary) for name, _ in COSTS),
        setup_costs=rng.choice([0.0, rng.uniform(0, 1) * salary]),
        fee_cap_months=rng.choice([0.0, 1.0, 2.0]),
    )


def test_properties_over_2000_random_workers() -> None:
    rng = random.Random(7)
    for _ in range(2000):
        inputs = _random(rng)
        figures = compute_figures(inputs, None, None)  # the schema itself checks the sums
        again = compute_figures(inputs, None, None)
        paid = goals(figures)

        assert figures == again
        assert all(amount >= 0 for amount in paid.values())
        assert all(amount == int(amount) for key, amount in paid.items() if key != "remittance")
        if figures.available > 0:
            assert figures.budget.left_over.amount >= -0.005  # the split never overdraws
            assert paid.get("debt_payment", 0) + paid["emergency_fund"] <= figures.available
        else:
            assert paid.get("debt_payment", 0) == 0 and paid["emergency_fund"] == 0
        fund = figures.emergency_fund
        assert fund.target.amount == pytest.approx(3 * sum(a for _, a in inputs.costs), abs=0.08)
        if fund.weeks_to_target is not None and fund.weeks_to_target > 0:
            assert fund.monthly_saving.amount > 0
