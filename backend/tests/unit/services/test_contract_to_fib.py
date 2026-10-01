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
        "employer_name": "Example Household",
    }


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
