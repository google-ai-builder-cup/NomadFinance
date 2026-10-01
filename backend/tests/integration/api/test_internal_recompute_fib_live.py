"""End-to-end: the weekly recompute through the real endpoint to the real reasoning-tier
model; the scheduler token, Firestore and the FX cache are faked.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_internal_recompute_fib_live.py -v -s

`-s` prints the reports and the run time (D-08 latency record for the narrative).
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import require_cloud_scheduler
from app.main import create_app
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.repositories.rate_repo import get_rate_repository
from app.repositories.user_repo import get_user_repository

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

URL = "/api/v1/internal/recompute-fib-profiles"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"
EMPLOYER = "Zzyzx Household Services"


def _months(count: int) -> list[str]:
    """The last `count` months as YYYY-MM, ending with the current one."""
    today = date.today()
    index = today.year * 12 + today.month - 1
    return [f"{i // 12}-{(i % 12) + 1:02d}" for i in range(index - count + 1, index + 1)]


def _history() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Six months for a domestic worker in Singapore sending money to India.

    All dated the 1st, so none is in the future whatever day the test runs.
    """
    months = _months(6)
    income, transfers, bills, savings = [], [], [], []
    for n, month in enumerate(months):
        # One missed transfer month and a bonus month, so the metrics are not all perfect.
        income.append(
            (
                f"i{n}",
                {
                    "entry_date": f"{month}-01",
                    "amount": 650 + (100 if n == 3 else 0),
                    "currency": "SGD",
                    "employer_name": EMPLOYER,
                    "category": "salary",
                },
            )
        )
        if n != 2:
            transfers.append(
                (
                    f"t{n}",
                    {
                        "entry_date": f"{month}-01",
                        "receive_amount": 38000,
                        "receive_currency": "INR",
                        "cost_pct": 1.4,
                    },
                )
            )
        bills.append(
            (
                f"b{n}",
                {
                    "entry_date": f"{month}-01",
                    "amount": 38.5,
                    "currency": "SGD",
                    "paid": n != 4,
                    "category": "phone_internet",
                },
            )
        )
        if n % 2 == 0:
            savings.append(
                (
                    f"s{n}",
                    {
                        "entry_date": f"{month}-01",
                        "amount": 120,
                        "currency": "SGD",
                        "direction": "deposit",
                    },
                )
            )
    return {"income": income, "transfers": transfers, "bills": bills, "savings": savings}


def _sparse() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    month = _months(1)[0]
    return {
        "bills": [
            ("b1", {"entry_date": f"{month}-01", "amount": 20, "currency": "SGD", "paid": True})
        ],
        "income": [("i1", {"entry_date": f"{month}-01", "amount": 900, "currency": "SGD"})],
    }


def _show(text: str) -> None:
    """Print a report; the Windows console codepage cannot show Hindi."""
    try:
        print("\n" + text)
    except UnicodeEncodeError:
        print("\n" + ascii(text))


class FakeFib:
    def __init__(self) -> None:
        self.data = {"priya": _history(), "rajesh": _sparse()}
        self.saved: dict[str, dict[str, Any]] = {}

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        return self.data[uid].get(kind, [])

    def save_profile(self, uid: str, profile: dict[str, Any]) -> None:
        self.saved[uid] = profile


class FakeUsers:
    profiles = {
        "priya": {"home_country": "IN", "preferred_language": "hi"},
        "rajesh": {"home_country": "IN", "preferred_language": "en"},
    }

    def list_user_ids(self) -> list[str]:
        return list(self.profiles)

    def get_profile(self, uid: str) -> dict[str, Any]:
        return self.profiles[uid]


class FakeRates:
    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return {"rate": 64.7} if pair_id == "SGD_INR" else None


@pytest.fixture(scope="module")
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture(scope="module")
def api(fib: FakeFib) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[require_cloud_scheduler] = lambda: CRON_SA
    app.dependency_overrides[get_fib_repository] = lambda: fib
    app.dependency_overrides[get_user_repository] = lambda: FakeUsers()
    app.dependency_overrides[get_rate_repository] = lambda: FakeRates()
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def run(api: TestClient, fib: FakeFib) -> dict[str, Any]:
    started = time.perf_counter()
    response = api.post(URL, json={})
    print(f"\nrecompute of 2 users took {time.perf_counter() - started:.1f}s")
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_both_profiles_are_written(run: dict[str, Any], fib: FakeFib) -> None:
    assert (run["users_seen"], run["recomputed"], run["failed"]) == (2, 2, 0)
    assert set(fib.saved) == {"priya", "rajesh"}


def test_the_six_month_profile_has_metrics_in_inr_and_a_hindi_report(
    run: dict[str, Any], fib: FakeFib
) -> None:
    profile = fib.saved["priya"]
    print("\n" + profile["narrative"]["text"])
    assert profile["reporting_currency"] == "INR"
    assert profile["months_of_data"] == 6
    assert profile["metrics"]["remittance_consistency"]["detail"]["months_with_transfer"] == 5
    assert profile["metrics"]["bill_payment_reliability"]["score"] == 83
    narrative = profile["narrative"]
    assert narrative["language"] == "hi"
    assert re.search("[ऀ-ॿ]", narrative["text"])
    assert "\\n" not in narrative["text"]
    assert len([p for p in narrative["text"].split("\n\n") if p.strip()]) >= 5
    assert EMPLOYER not in narrative["text"]


def test_the_one_month_profile_says_it_rests_on_few_records(
    run: dict[str, Any], fib: FakeFib
) -> None:
    profile = fib.saved["rajesh"]
    print("\n" + profile["narrative"]["text"])
    assert profile["months_of_data"] == 1
    assert profile["metrics"]["remittance_consistency"]["score"] is None
    text = profile["narrative"]["text"]
    assert profile["narrative"]["language"] == "en"
    assert "\\n" not in text
    assert re.search(r"(one|1|single|few|limited|short)", text, re.IGNORECASE)
