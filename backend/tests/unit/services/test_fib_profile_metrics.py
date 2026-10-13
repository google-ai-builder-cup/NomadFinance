from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.services.fib.profile_metrics import (
    Entry,
    bill_payment_reliability,
    compute_metrics,
    entries_in_window,
    income_stability,
    overall_score,
    remittance_consistency,
    savings_rate,
    window_start,
)

TODAY = date(2026, 10, 15)


def _e(day: str, **data: Any) -> Entry:
    return Entry(date.fromisoformat(day), {"entry_date": day} | data)


def _income(day: str, amount: float = 650, currency: str = "SGD") -> Entry:
    return _e(day, amount=amount, currency=currency)


def _same(amount: float, currency: str) -> float | None:
    return amount


def _sgd_to_inr(amount: float, currency: str) -> float | None:
    return {"SGD": amount * 60, "INR": amount}.get(currency)


def test_the_window_is_this_month_and_the_eleven_before() -> None:
    assert window_start(TODAY) == date(2025, 11, 1)
    assert window_start(date(2026, 1, 5)) == date(2025, 2, 1)


def test_entries_outside_the_window_in_the_future_or_with_a_bad_date_are_dropped() -> None:
    raw = [
        ("a", {"entry_date": "2026-09-01"}),
        ("b", {"entry_date": "2025-10-31"}),  # a day before the window
        ("c", {"entry_date": "2025-11-01"}),
        ("d", {"entry_date": "2026-10-16"}),  # tomorrow
        ("e", {"entry_date": "not a date"}),
        ("f", {}),
    ]

    kept = entries_in_window(raw, TODAY)

    assert [e.data["entry_date"] for e in kept] == ["2026-09-01", "2025-11-01"]


def test_steady_monthly_income_scores_100() -> None:
    income = [_income("2026-07-25"), _income("2026-08-25"), _income("2026-09-25")]

    result = income_stability(income, _same, TODAY)

    assert result["score"] == 100
    assert result["detail"]["months_with_income"] == 3
    # Oct 15 has no income yet, so the running month is not counted against the worker.
    assert result["detail"]["months_in_period"] == 3
    assert result["detail"]["mean_monthly_income"] == 650


def test_the_running_month_counts_once_it_has_income() -> None:
    income = [_income("2026-09-25"), _income("2026-10-02")]

    result = income_stability(income, _same, TODAY)

    assert result["detail"]["months_in_period"] == 2
    assert result["score"] == 100


def test_a_month_without_income_lowers_the_score() -> None:
    income = [_income("2026-07-25"), _income("2026-09-25")]

    result = income_stability(income, _same, TODAY)

    assert result["detail"]["months_in_period"] == 3
    assert result["score"] == 67


def test_income_that_varies_scores_lower() -> None:
    income = [_income("2026-08-25", 100), _income("2026-09-25", 300)]

    result = income_stability(income, _same, TODAY)

    # mean 200, standard deviation 100: variation 0.5, full coverage.
    assert result["detail"]["monthly_variation"] == 0.5
    assert result["score"] == 50


def test_several_entries_in_one_month_add_up() -> None:
    income = [_income("2026-09-05", 300), _income("2026-09-25", 350), _income("2026-08-25", 650)]

    assert income_stability(income, _same, TODAY)["score"] == 100


def test_income_is_converted_and_unconvertible_entries_are_excluded() -> None:
    income = [
        _income("2026-08-25", 100, "SGD"),
        _income("2026-09-25", 100, "SGD"),
        _income("2026-09-26", 5000, "KRW"),
    ]

    result = income_stability(income, _sgd_to_inr, TODAY)

    assert result["detail"]["mean_monthly_income"] == 6000
    assert result["detail"]["excluded_entries"] == 1


@pytest.mark.parametrize(
    ("income", "reason"),
    [
        ([], "no_income_entries"),
        ([_income("2026-09-25", 10, "KRW")], "no_income_in_a_convertible_currency"),
    ],
)
def test_income_stability_without_usable_income_has_no_score(
    income: list[Entry], reason: str
) -> None:
    result = income_stability(income, _sgd_to_inr, TODAY)

    assert result == {"score": None, "detail": {"reason": reason}}


def _saving(amount: float, direction: str = "deposit", currency: str = "SGD") -> Entry:
    return _e("2026-09-26", amount=amount, currency=currency, direction=direction)


def test_saving_the_target_share_of_income_scores_100() -> None:
    result = savings_rate([_income("2026-09-25", 1000)], [_saving(200)], _same)

    assert result["score"] == 100
    assert result["detail"]["savings_rate"] == 0.2


def test_saving_half_the_target_scores_50() -> None:
    result = savings_rate(
        [_income("2026-09-25", 1000)], [_saving(150), _saving(50, "withdrawal")], _same
    )

    assert result["detail"]["net_savings"] == 100
    assert result["detail"]["savings_rate"] == 0.1
    assert result["score"] == 50


def test_more_withdrawn_than_deposited_scores_0_and_keeps_the_negative_net() -> None:
    result = savings_rate(
        [_income("2026-09-25", 1000)], [_saving(50), _saving(150, "withdrawal")], _same
    )

    assert result["score"] == 0
    assert result["detail"]["net_savings"] == -100


def test_saving_more_than_the_target_is_capped_at_100() -> None:
    assert savings_rate([_income("2026-09-25", 100)], [_saving(90)], _same)["score"] == 100


def test_savings_rate_needs_income_and_savings_entries() -> None:
    assert savings_rate([], [_saving(50)], _same)["detail"]["reason"].startswith("no_income")
    assert savings_rate([_income("2026-09-25")], [], _same)["detail"]["reason"] == (
        "no_savings_entries"
    )
    assert savings_rate([_income("2026-09-25")], [_saving(5, currency="KRW")], _sgd_to_inr)[
        "detail"
    ]["reason"] == ("no_savings_in_a_convertible_currency")


def _transfer(day: str, received: float = 25000, cost: float | None = 1.2) -> Entry:
    data: dict[str, Any] = {"receive_amount": received, "receive_currency": "INR"}
    if cost is not None:
        data["cost_pct"] = cost
    return _e(day, **data)


def test_a_transfer_every_month_scores_100() -> None:
    transfers = [_transfer("2026-07-26"), _transfer("2026-08-26"), _transfer("2026-09-26")]

    result = remittance_consistency(transfers, _sgd_to_inr, TODAY)

    assert result["score"] == 100
    assert result["detail"]["transfer_count"] == 3
    assert result["detail"]["total_received"] == 75000


def test_a_month_without_a_transfer_lowers_the_score() -> None:
    result = remittance_consistency(
        [_transfer("2026-07-26"), _transfer("2026-09-26")], _same, TODAY
    )

    assert result["detail"]["months_in_period"] == 3
    assert result["score"] == 67


def test_the_months_start_at_the_first_transfer_not_the_start_of_logging() -> None:
    result = remittance_consistency([_transfer("2026-09-26")], _same, TODAY)

    assert result["detail"]["months_in_period"] == 1
    assert result["score"] == 100


def test_average_cost_ignores_transfers_without_one() -> None:
    transfers = [
        _transfer("2026-08-26", cost=1.0),
        _transfer("2026-09-26", cost=2.0),
        _transfer("2026-09-27", cost=None),
    ]

    assert remittance_consistency(transfers, _same, TODAY)["detail"]["average_cost_pct"] == 1.5
    assert (
        remittance_consistency([_transfer("2026-09-26", cost=None)], _same, TODAY)["detail"][
            "average_cost_pct"
        ]
        is None
    )


def test_no_transfers_has_no_score() -> None:
    assert remittance_consistency([], _same, TODAY)["detail"]["reason"] == "no_transfers"


def test_bill_reliability_is_the_share_of_paid_bills() -> None:
    bills = [_e("2026-09-01", paid=True)] * 3 + [_e("2026-09-02", paid=False)]

    result = bill_payment_reliability(bills)

    assert result["score"] == 75
    assert result["detail"] == {"bills_total": 4, "bills_paid": 3, "bills_unpaid": 1}
    assert bill_payment_reliability([])["detail"]["reason"] == "no_bills"


def test_the_overall_score_averages_only_the_metrics_that_have_one() -> None:
    metrics: dict[str, dict[str, Any]] = {
        "a": {"score": 80, "detail": {}},
        "b": {"score": None, "detail": {"reason": "x"}},
        "c": {"score": 60, "detail": {}},
    }

    assert overall_score(metrics) == 70
    assert overall_score({"a": {"score": None, "detail": {}}}) is None


def test_compute_metrics_returns_the_four_design_doc_metrics() -> None:
    metrics = compute_metrics([], [], [_e("2026-09-01", paid=True)], [], _same, TODAY)

    assert list(metrics) == [
        "income_stability",
        "savings_rate",
        "remittance_consistency",
        "bill_payment_reliability",
    ]
    assert metrics["bill_payment_reliability"]["score"] == 100
    assert metrics["income_stability"]["score"] is None


# --- a salary read from a contract ----------------------------------------------------------


def _contract(day: str, amount: float, **data: Any) -> Entry:
    return _e(day, amount=amount, currency="AUD", source="contract", **data)


def test_an_hourly_contract_rate_is_not_added_up_as_a_months_pay() -> None:
    income = [
        _income("2026-08-25", 3000, "AUD"),
        _income("2026-09-25", 3000, "AUD"),
        _contract("2026-10-01", 18, salary_period="hour", monthly_amount=None),
    ]

    result = income_stability(income, _same, TODAY)

    # 18 an hour is no month's income: it is left out, and counted as left out.
    assert result["detail"]["mean_monthly_income"] == 3000
    assert result["detail"]["excluded_entries"] == 1


def test_a_weekly_contract_salary_counts_as_a_months_worth() -> None:
    income = [_contract("2026-09-25", 150, salary_period="week", monthly_amount=650)]

    result = income_stability(income, _same, TODAY)

    assert result["detail"]["mean_monthly_income"] == 650


def test_a_contract_entry_logged_before_the_monthly_figure_existed_counts_as_written() -> None:
    income = [_contract("2026-09-25", 650)]

    result = income_stability(income, _same, TODAY)

    assert result["detail"]["mean_monthly_income"] == 650


def test_a_manual_entry_is_never_touched_by_the_contract_rule() -> None:
    income = [_income("2026-09-25", 650)]
    income[0].data["monthly_amount"] = None  # not a contract entry: ignored

    result = income_stability(income, _same, TODAY)

    assert result["detail"]["mean_monthly_income"] == 650
