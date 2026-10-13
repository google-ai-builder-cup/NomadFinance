from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.schemas.contract import DocumentKind
from app.schemas.contract_complaint import ContractFacts
from app.services.cross_pillar.contract_to_fib import build_income_entry, log_contract_income
from tests.fixtures.pipeline_fakes import FakeFib

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _facts(**over: Any) -> ContractFacts:
    values: dict[str, Any] = {
        "employer_name": "Example Household",
        "agency_name": None,
        "salary_amount": 650.0,
        "salary_currency": "SGD",
        "salary_period": "month",
    }
    return ContractFacts.model_validate(values | over)


# --- build_income_entry -------------------------------------------------------------------


def test_an_employment_contract_with_a_salary_builds_an_entry() -> None:
    entry = build_income_entry(_facts(), "employment_contract")

    assert entry == {
        "amount": 650.0,
        "currency": "SGD",
        "category": "salary",
        "category_source": "user",
        "verified": True,
        "source": "contract",
        "salary_period": "month",
        "monthly_amount": 650.0,
        "employer_name": "Example Household",
    }


@pytest.mark.parametrize(
    ("period", "amount", "monthly"),
    [("month", 650.0, 650.0), ("week", 150.0, 650.0), ("hour", 18.0, None), ("day", 90.0, None)],
)
def test_what_a_salary_comes_to_in_a_month_is_stored_beside_the_stated_figure(
    period: str, amount: float, monthly: float | None
) -> None:
    entry = build_income_entry(
        _facts(salary_amount=amount, salary_period=period), "employment_contract"
    )

    assert entry is not None
    # The figure is as the contract states it (the PDF prints it with its period);
    # the month's worth is separate, and None where it cannot be known.
    assert entry["amount"] == amount and entry["salary_period"] == period
    assert entry["monthly_amount"] == monthly


def test_no_period_stated_is_read_as_a_month() -> None:
    entry = build_income_entry(_facts(salary_period=None), "employment_contract")

    assert entry is not None
    assert "salary_period" not in entry and entry["monthly_amount"] == 650.0


def test_no_employer_name_omits_the_field_rather_than_storing_none() -> None:
    entry = build_income_entry(_facts(employer_name=None), "employment_contract")

    assert entry is not None
    assert "employer_name" not in entry


@pytest.mark.parametrize("document_kind", ["recruitment_agreement", "loan_agreement", "other"])
def test_only_an_employment_contract_builds_an_entry(document_kind: DocumentKind) -> None:
    assert build_income_entry(_facts(), document_kind) is None


def test_no_salary_amount_is_nothing_to_log() -> None:
    assert build_income_entry(_facts(salary_amount=None), "employment_contract") is None


def test_no_salary_currency_is_nothing_to_log() -> None:
    assert build_income_entry(_facts(salary_currency=None), "employment_contract") is None


# --- log_contract_income -------------------------------------------------------------------


async def test_logs_the_entry_under_a_contract_derived_id() -> None:
    fib = FakeFib()

    entry_id = await log_contract_income(
        "worker-1", "c_01", "employment_contract", _facts(), fib, NOW  # type: ignore[arg-type]
    )

    assert entry_id == "contract_c_01"
    stored = fib.docs["worker-1/income/contract_c_01"]
    assert stored["amount"] == 650.0
    assert stored["verified"] is True
    assert stored["source"] == "contract"
    assert stored["entry_date"] == "2026-09-30"
    # What financial_profile.verified_employment is built from (profile_builder.py).
    assert stored["contract_ref"] == "c_01"


async def test_re_analysing_the_same_contract_overwrites_not_duplicates() -> None:
    fib = FakeFib()
    await log_contract_income(
        "worker-1", "c_01", "employment_contract", _facts(salary_amount=600.0), fib, NOW  # type: ignore[arg-type]
    )

    await log_contract_income(
        "worker-1", "c_01", "employment_contract", _facts(salary_amount=650.0), fib, NOW  # type: ignore[arg-type]
    )

    assert len(fib.docs) == 1
    assert fib.docs["worker-1/income/contract_c_01"]["amount"] == 650.0


async def test_nothing_to_log_writes_nothing() -> None:
    fib = FakeFib()

    entry_id = await log_contract_income(
        "worker-1", "c_01", "loan_agreement", _facts(), fib, NOW  # type: ignore[arg-type]
    )

    assert entry_id is None
    assert fib.docs == {}


async def test_a_second_contract_in_the_same_month_replaces_the_first() -> None:
    fib = FakeFib()
    fib.docs["worker-1/income/manual_1"] = {"source": "manual", "entry_date": "2026-09-05"}
    fib.docs["worker-1/income/contract_old"] = {"source": "contract", "entry_date": "2026-08-30"}
    await log_contract_income(
        "worker-1", "c_01", "employment_contract", _facts(salary_amount=600.0), fib, NOW  # type: ignore[arg-type]
    )

    await log_contract_income(
        "worker-1", "c_02", "employment_contract", _facts(salary_amount=700.0), fib, NOW  # type: ignore[arg-type]
    )

    assert sorted(fib.docs) == [
        "worker-1/income/contract_c_02",
        "worker-1/income/contract_old",  # last month's salary stays
        "worker-1/income/manual_1",  # the worker's own entries are never touched
    ]
    assert fib.docs["worker-1/income/contract_c_02"]["amount"] == 700.0


async def test_an_entry_from_before_contract_ref_is_replaced_too() -> None:
    # Written by the first version, without contract_ref: the profile never showed it.
    fib = FakeFib()
    fib.docs["worker-1/income/contract_c_01"] = {
        "source": "contract",
        "verified": True,
        "entry_date": "2026-09-12",
        "amount": 650.0,
    }

    await log_contract_income(
        "worker-1", "c_01", "employment_contract", _facts(), fib, NOW  # type: ignore[arg-type]
    )

    assert fib.docs["worker-1/income/contract_c_01"]["contract_ref"] == "c_01"
