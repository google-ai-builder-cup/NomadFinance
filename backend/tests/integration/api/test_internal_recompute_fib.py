from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_feature_flag_service, require_cloud_scheduler
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.repositories.rate_repo import get_rate_repository
from app.repositories.scam_check_repo import get_scam_check_repository
from app.repositories.user_repo import get_user_repository
from app.schemas.fib_profile import NarrativeAnswer
from tests.fixtures.coach_mocks import MOCKS
from tests.fixtures.coach_sessions import FakePlanRepo

URL = "/api/v1/internal/recompute-fib-profiles"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"


class FakeGemini:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, **kwargs: Any) -> NarrativeAnswer:
        self.calls += 1
        return NarrativeAnswer(text="The report.")


class FakeFib:
    def __init__(self) -> None:
        self.saved: dict[str, dict[str, Any]] = {}

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        if uid == "active" and kind == "bills":
            return [
                ("b1", {"entry_date": "2026-10-01", "amount": 5, "currency": "SGD", "paid": True})
            ]
        return []

    def save_profile(self, uid: str, profile: dict[str, Any]) -> None:
        self.saved[uid] = profile


class FakeUsers:
    def __init__(self) -> None:
        self.sharing: dict[str, bool] | None = None

    def list_user_ids(self) -> list[str]:
        return ["active", "quiet"]

    def get_profile(self, uid: str) -> dict[str, Any]:
        profile: dict[str, Any] = {"home_country": "IN", "preferred_language": "hi"}
        if self.sharing is not None:
            profile["signal_sharing"] = self.sharing
        return profile


class FakeChecks:
    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                "c1",
                {"last_checked_at": datetime.now(UTC), "verdict": {"is_scam": True}},
            )
        ]


class FakeFlags:
    async def is_enabled(self, flag: str, uid: str) -> bool:
        return True


class FakeRates:
    def get_rate(self, pair_id: str) -> None:
        return None


@pytest.fixture
def users() -> FakeUsers:
    return FakeUsers()


@pytest.fixture
def plans() -> FakePlanRepo:
    return FakePlanRepo()


@pytest.fixture
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture
def gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def app(fib: FakeFib, gemini: FakeGemini, plans: FakePlanRepo, users: FakeUsers) -> FastAPI:
    app = create_app()
    app.dependency_overrides[require_cloud_scheduler] = lambda: CRON_SA
    app.dependency_overrides[get_fib_repository] = lambda: fib
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_rate_repository] = lambda: FakeRates()
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    # The Coach plans the recompute reads goals from (NF-FC-015): never the real Firestore.
    app.dependency_overrides[get_coach_plan_repository] = lambda: plans
    # What a worker shares from the Scam Analyzer and the flags that gate it (NF-HR-001).
    app.dependency_overrides[get_scam_check_repository] = lambda: FakeChecks()
    app.dependency_overrides[get_feature_flag_service] = lambda: FakeFlags()
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_the_run_writes_a_profile_for_users_with_activity(
    api: TestClient, fib: FakeFib, gemini: FakeGemini
) -> None:
    response = api.post(URL, json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["users_seen"], body["recomputed"], body["skipped_no_data"], body["failed"]) == (
        2,
        1,
        1,
        0,
    )
    assert list(fib.saved) == ["active"]
    assert fib.saved["active"]["narrative"]["language"] == "hi"
    assert gemini.calls == 1


def test_a_worker_with_a_coach_plan_gets_its_goals_in_the_new_profile(
    api: TestClient, fib: FakeFib, plans: FakePlanRepo
) -> None:
    body = json.loads((MOCKS / "plan-01-created.json").read_text(encoding="utf-8"))["body"]
    when = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    plans.add("active", "p1", {"plan": body["plan"], "created_at": when})

    assert api.post(URL, json={}).status_code == 200

    goals = fib.saved["active"]["goals"]
    assert goals["plan_id"] == "p1" and goals["remittance"]["cadence"] == "monthly"
    assert goals["emergency_fund_target"] == {"amount": 6465.0, "currency": "AUD"}


def test_a_worker_with_no_coach_plan_gets_no_goals(api: TestClient, fib: FakeFib) -> None:
    assert api.post(URL, json={}).status_code == 200

    assert "goals" not in fib.saved["active"]


def test_a_worker_who_shares_gets_the_signals_in_the_new_profile(
    api: TestClient, fib: FakeFib, plans: FakePlanRepo, users: FakeUsers
) -> None:
    users.sharing = {"coach": True, "scam": True}
    plans.add(
        "active",
        "p1",
        {
            "created_at": datetime(2026, 10, 1, tzinfo=UTC),
            "checkins": {
                "d30": {
                    "answered_at": datetime(2026, 10, 9, tzinfo=UTC),
                    "answers": {
                        "remittance": "on_track",
                        "savings": "on_track",
                        "pay": "full_on_time",
                    },
                }
            },
        },
    )

    assert api.post(URL, json={}).status_code == 200

    profile = fib.saved["active"]
    assert profile["coach_signal"]["checkins_answered"] == 1
    assert profile["scam_signal"]["scams_found"] == 1


def test_a_worker_who_does_not_share_gets_none(api: TestClient, fib: FakeFib) -> None:
    assert api.post(URL, json={}).status_code == 200

    assert "coach_signal" not in fib.saved["active"]
    assert "scam_signal" not in fib.saved["active"]


def test_a_caller_that_is_not_the_scheduler_is_refused(app: FastAPI) -> None:
    app.dependency_overrides.pop(require_cloud_scheduler)
    with TestClient(app) as client:
        assert client.post(URL, json={}).status_code in {401, 503}


def test_the_endpoint_is_not_in_the_public_docs(api: TestClient) -> None:
    assert URL not in api.get("/openapi.json").json()["paths"]
