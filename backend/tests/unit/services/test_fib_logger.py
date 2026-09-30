from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.repositories.fib_repo import EntryKind
from app.schemas.fib import BillLogRequest, IncomeLogRequest, SavingsLogRequest
from app.services.fib.logger import log_bill, log_income, log_savings

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


class FakeFib:
    """Stands in for `FibRepository`."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}
        self._next_id = 0

    def new_id(self, uid: str, kind: EntryKind) -> str:
        self._next_id += 1
        return f"e_{self._next_id}"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


# --- income --------------------------------------------------------------------------------


async def test_income_is_stored_with_user_category_and_unverified() -> None:
    body = IncomeLogRequest(amount=650, currency="SGD", category="salary", employer_name="Acme")
    fib = FakeFib()

    result = await log_income("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert result.entry_id == "e_1"
    assert (result.amount, result.currency, result.category) == (650, "SGD", "salary")
    assert result.category_source == "user"
    assert result.verified is False
    assert result.employer_name == "Acme"
    assert result.entry_date == NOW.date()

    stored = fib.docs["uid/income/e_1"]
    assert stored["verified"] is False
    assert stored["category_source"] == "user"
    assert stored["source"] == "manual"
    assert stored["entry_date"] == "2026-09-30"


async def test_income_without_employer_or_notes_omits_them() -> None:
    body = IncomeLogRequest(amount=100, currency="SGD", category="bonus")
    fib = FakeFib()

    await log_income("uid", body, fib, NOW)  # type: ignore[arg-type]

    stored = fib.docs["uid/income/e_1"]
    assert "employer_name" not in stored
    assert "notes" not in stored


async def test_income_entry_date_is_kept_when_given() -> None:
    body = IncomeLogRequest(
        amount=100, currency="SGD", category="overtime", entry_date=date(2026, 8, 1)
    )

    result = await log_income("uid", body, FakeFib(), NOW)  # type: ignore[arg-type]

    assert result.entry_date == date(2026, 8, 1)


# --- bill ------------------------------------------------------------------------------------


async def test_bill_without_a_category_stores_none_and_no_category_source() -> None:
    body = BillLogRequest(amount=38.5, currency="SGD", paid=True, vendor="Example Telecom")
    fib = FakeFib()

    result = await log_bill("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert result.category is None
    assert result.category_source is None
    stored = fib.docs["uid/bills/e_1"]
    assert "category" not in stored
    assert "category_source" not in stored


async def test_bill_with_a_category_is_marked_user_sourced() -> None:
    body = BillLogRequest(amount=38.5, currency="SGD", paid=True, category="phone_internet")
    fib = FakeFib()

    result = await log_bill("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert (result.category, result.category_source) == ("phone_internet", "user")
    stored = fib.docs["uid/bills/e_1"]
    assert (stored["category"], stored["category_source"]) == ("phone_internet", "user")


async def test_bill_date_is_stored_separately_from_entry_date() -> None:
    body = BillLogRequest(
        amount=38.5,
        currency="SGD",
        paid=True,
        entry_date=date(2026, 9, 24),
        bill_date=date(2026, 9, 20),
    )
    fib = FakeFib()

    result = await log_bill("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert (result.entry_date, result.bill_date) == (date(2026, 9, 24), date(2026, 9, 20))
    assert fib.docs["uid/bills/e_1"]["bill_date"] == "2026-09-20"


async def test_unpaid_bill_is_stored_as_such() -> None:
    body = BillLogRequest(amount=20, currency="SGD", paid=False)

    result = await log_bill("uid", body, FakeFib(), NOW)  # type: ignore[arg-type]

    assert result.paid is False


# --- savings ---------------------------------------------------------------------------------


async def test_savings_deposit_is_stored() -> None:
    body = SavingsLogRequest(amount=120, currency="SGD", direction="deposit", account_type="bank")
    fib = FakeFib()

    result = await log_savings("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert (result.amount, result.direction, result.account_type) == (120, "deposit", "bank")
    stored = fib.docs["uid/savings/e_1"]
    assert stored["direction"] == "deposit"
    assert stored["account_type"] == "bank"


async def test_savings_without_account_type_omits_it() -> None:
    body = SavingsLogRequest(amount=50, currency="SGD", direction="withdrawal")
    fib = FakeFib()

    result = await log_savings("uid", body, fib, NOW)  # type: ignore[arg-type]

    assert result.account_type is None
    assert "account_type" not in fib.docs["uid/savings/e_1"]


async def test_savings_amount_is_always_positive_even_for_a_withdrawal() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        SavingsLogRequest(amount=-50, currency="SGD", direction="withdrawal")


# --- shared: notes and currency validation ----------------------------------------------------


async def test_blank_notes_are_dropped_by_the_request_model() -> None:
    body = IncomeLogRequest(amount=1, currency="SGD", category="salary", notes="   ")

    assert body.notes is None


@pytest.mark.parametrize("currency", ["sgd", "SG", "SGDD", "123"])
async def test_a_malformed_currency_code_is_rejected(currency: str) -> None:
    with pytest.raises(ValueError):
        SavingsLogRequest(amount=1, currency=currency, direction="deposit")
