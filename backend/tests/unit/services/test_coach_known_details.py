"""What the Coach already knows about a worker, and keeping it (NF-FC-023): which entries become an
offer, what is left out, and that nothing counts until the worker keeps it."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.services.coach.known_details import (
    OFFER_ORDER,
    UnknownKnownSlotError,
    collect_known,
    contract_item,
    income_item,
    kept_slots,
    known_document,
    profile_items,
    savings_items,
    transfers_item,
)
from app.services.coach.prefill import Prefill

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


def salary(day: str = "2026-09-25", amount: Any = 650, currency: str = "SGD") -> dict[str, Any]:
    return {"category": "salary", "amount": amount, "currency": currency, "entry_date": day}


def saved(
    amount: Any, day: str = "2026-09-01", direction: str = "deposit", **extra: Any
) -> dict[str, Any]:
    return {
        "amount": amount,
        "currency": "SGD",
        "direction": direction,
        "entry_date": day,
        **extra,
    }


def sent(amount: Any, day: str, currency: str = "SGD") -> dict[str, Any]:
    return {"send_amount": amount, "send_currency": currency, "entry_date": day}


# --- the profile --------------------------------------------------------------------------------


def test_the_country_and_the_kind_of_work_come_from_the_profile() -> None:
    profile = {"host_country": "SG", "job_type": "domestic_worker", "home_country": "IN"}

    items = profile_items(profile)

    assert items == {
        "destination_country": {"value": "SG", "source": "profile", "as_of": None},
        "job_type": {"value": "domestic_worker", "source": "profile", "as_of": None},
    }


def test_a_profile_before_onboarding_offers_nothing() -> None:
    assert profile_items({}) == {}
    assert profile_items({"host_country": None, "job_type": 7}) == {}


# --- the salary ---------------------------------------------------------------------------------


def test_the_newest_logged_salary_is_offered_as_one_months_pay_with_its_date() -> None:
    entries = [salary("2026-08-25", 600), salary("2026-09-25", 650), salary("2026-07-25", 580)]

    assert income_item(entries) == {
        "value": {"amount": 650.0, "currency": "SGD", "period": "month"},
        "source": "income",
        "as_of": "2026-09-25",
    }


@pytest.mark.parametrize(
    "entry",
    [
        {**salary(), "category": "bonus"},
        {**salary(), "category": "overtime"},
        salary(amount=0),
        salary(amount=-10),
        salary(amount=True),
        salary(amount="650"),
        salary(amount=float("nan")),
        salary(currency="USD"),
        salary(day="25 September"),
        {k: v for k, v in salary().items() if k != "entry_date"},
    ],
)
def test_an_income_entry_that_is_not_a_usable_salary_is_passed_over(entry: dict[str, Any]) -> None:
    assert income_item([entry]) is None


def test_the_contract_salary_comes_first_and_keeps_its_own_period() -> None:
    contract = Prefill("c1", 4200.0, "AUD", "month", "Example Care")

    assert contract_item(contract) == {
        "value": {"amount": 4200.0, "currency": "AUD", "period": "month"},
        "source": "contract",
        "as_of": None,
    }
    found = collect_known(
        profile={},
        contract=contract,
        income=[salary()],
        savings=[],
        transfers=[],
        today=TODAY,
    )
    assert found["monthly_salary"]["source"] == "contract"


# --- savings and the account --------------------------------------------------------------------


def test_the_savings_balance_is_deposits_minus_withdrawals_in_the_main_currency() -> None:
    entries = [
        saved(500, "2026-08-01"),
        saved(900, "2026-09-01"),
        saved(200, "2026-09-10", direction="withdrawal"),
        {**saved(10000, "2026-09-12"), "currency": "INR"},
    ]

    items = savings_items(entries)

    assert items["savings"] == {
        "value": {"amount": 1200.0, "currency": "SGD", "period": "once"},
        "source": "savings",
        "as_of": "2026-09-10",
    }


def test_a_balance_of_zero_or_less_is_not_offered_since_it_says_nothing() -> None:
    assert "savings" not in savings_items([saved(100), saved(100, direction="withdrawal")])
    assert "savings" not in savings_items([saved(100), saved(300, direction="withdrawal")])


@pytest.mark.parametrize(
    ("types", "answer"),
    [
        (["bank"], "bank_account"),
        (["mobile_wallet"], "mobile_wallet"),
        (["bank", "mobile_wallet"], "both"),
        (["bank", "cash"], "bank_account"),
    ],
)
def test_the_account_type_of_the_savings_says_bank_wallet_or_both(
    types: list[str], answer: str
) -> None:
    entries = [saved(100, f"2026-09-0{i + 1}", account_type=kind) for i, kind in enumerate(types)]

    assert savings_items(entries)["bank_or_wallet"]["value"] == answer


def test_cash_or_no_account_type_does_not_say_the_worker_has_neither() -> None:
    assert "bank_or_wallet" not in savings_items([saved(100, account_type="cash"), saved(50)])


def test_the_main_currency_is_the_one_used_most_then_the_newest() -> None:
    inr = {**saved(1000, "2026-09-20"), "currency": "INR"}

    both = savings_items([saved(100, "2026-09-01"), inr])
    most = savings_items([saved(100, "2026-09-01"), saved(100, "2026-09-02"), inr])

    assert both["savings"]["value"]["currency"] == "INR"  # one each: the newest entry wins
    assert most["savings"]["value"]["currency"] == "SGD"


# --- the money sent home ------------------------------------------------------------------------


def test_what_is_sent_home_is_the_average_of_the_months_that_have_a_transfer() -> None:
    entries = [
        sent(400, "2026-08-28"),
        sent(200, "2026-09-05"),
        sent(400, "2026-09-26"),  # September: 600, August: 400, October: none
        sent(999, "2026-04-01"),  # too old
    ]

    assert transfers_item(entries, TODAY) == {
        "value": {"amount": 500.0, "currency": "SGD", "period": "month"},
        "source": "transfers",
        "as_of": "2026-09-26",
    }


def test_no_transfer_in_the_last_90_days_offers_nothing() -> None:
    assert transfers_item([sent(400, "2026-06-01")], TODAY) is None
    assert transfers_item([], TODAY) is None


def test_a_transfer_dated_in_the_future_or_in_an_odd_shape_is_left_out() -> None:
    entries = [sent(400, "2026-11-30"), sent(0, "2026-09-26"), sent("400", "2026-09-26")]

    assert transfers_item(entries, TODAY) is None


# --- the whole offer ----------------------------------------------------------------------------


def test_the_offer_lists_each_answer_once_in_the_interviews_order() -> None:
    found = collect_known(
        profile={"host_country": "SG", "job_type": "domestic_worker"},
        contract=None,
        income=[salary()],
        savings=[saved(1200, account_type="bank")],
        transfers=[sent(500, "2026-09-26")],
        today=TODAY,
    )

    assert list(found) == [
        "destination_country",
        "job_type",
        "monthly_salary",
        "remittance_target",
        "savings",
        "bank_or_wallet",
    ]
    assert tuple(found) == OFFER_ORDER


def test_a_worker_with_no_records_gets_no_offer() -> None:
    assert (
        collect_known(profile={}, contract=None, income=[], savings=[], transfers=[], today=TODAY)
        == {}
    )


def test_a_value_the_slot_would_refuse_is_never_offered() -> None:
    # A country that is not one of the six, a kind of work that does not exist.
    found = collect_known(
        profile={"host_country": "AE", "job_type": "pilot"},
        contract=None,
        income=[],
        savings=[],
        transfers=[],
        today=TODAY,
    )

    assert found == {}


# --- keeping ------------------------------------------------------------------------------------


def _known() -> dict[str, Any]:
    return known_document(
        collect_known(
            profile={"host_country": "SG", "job_type": "domestic_worker"},
            contract=Prefill("c1", 700.0, "SGD", "month", None),
            income=[],
            savings=[saved(1200, account_type="bank")],
            transfers=[],
            today=TODAY,
        )
    )


def test_a_kept_answer_is_a_confirmed_slot_that_names_where_it_came_from() -> None:
    kept = kept_slots(_known(), ["destination_country", "monthly_salary", "savings"], NOW, 0)

    assert set(kept) == {"destination_country", "monthly_salary", "savings"}
    assert kept["destination_country"] == {
        "value": "SG",
        "confidence": 1.0,
        "source": "profile_prefill",
        "confirmed": True,
        "updated_at": NOW,
        "turn": 0,
    }
    assert kept["monthly_salary"]["source"] == "contract_prefill"
    assert kept["savings"]["source"] == "identity_prefill"


def test_what_is_not_kept_is_not_stored() -> None:
    assert kept_slots(_known(), [], NOW, 0) == {}
    assert set(kept_slots(_known(), ["job_type"], NOW, 0)) == {"job_type"}


def test_keeping_an_answer_that_was_not_offered_is_refused() -> None:
    with pytest.raises(UnknownKnownSlotError, match="remittance_target"):
        kept_slots(_known(), ["job_type", "remittance_target"], NOW, 0)
