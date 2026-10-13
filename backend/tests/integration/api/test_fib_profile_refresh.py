from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_feature_flag_service
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.repositories.rate_repo import get_rate_repository
from app.repositories.scam_check_repo import get_scam_check_repository
from app.repositories.user_repo import get_user_repository
from app.schemas.fib_profile import NarrativeAnswer
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/fib/profile/refresh"


class FakeFib:
    def __init__(self) -> None:
        self.income: list[tuple[str, dict[str, Any]]] = []
        self.profile: dict[str, Any] | None = None

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        today = datetime.now(UTC).date().isoformat()
        return [(i, d | {"entry_date": today}) for i, d in self.income] if kind == "income" else []

    def get_profile(self, uid: str) -> dict[str, Any] | None:
        return self.profile

    def save_profile(self, uid: str, profile: dict[str, Any]) -> None:
        self.profile = profile


class FakeUsers:
    def get_profile(self, uid: str) -> dict[str, Any]:
        return {"home_country": "PH", "preferred_language": "en"}


class FakeRates:
    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return {"rate": 40.0}


class FakeGemini:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_structured(self, **kwargs: Any) -> NarrativeAnswer:
        self.calls += 1
        return NarrativeAnswer(text="A short report.")


class NoPlans:
    def newest(self, uid: str) -> None:
        return None


class NoChecks:
    def activity_since(self, uid: str, since: datetime, limit: int) -> list[Any]:
        return []


class FlagsOff:
    async def is_enabled(self, flag: str, uid: str) -> bool:
        return False


@pytest.fixture
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture
def gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def api(fib: FakeFib, gemini: FakeGemini) -> Iterator[TestClient]:
    app: FastAPI = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="worker")
    app.dependency_overrides[get_fib_repository] = lambda: fib
    app.dependency_overrides[get_user_repository] = lambda: FakeUsers()
    app.dependency_overrides[get_rate_repository] = lambda: FakeRates()
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    app.dependency_overrides[get_coach_plan_repository] = lambda: NoPlans()
    app.dependency_overrides[get_scam_check_repository] = lambda: NoChecks()
    app.dependency_overrides[get_feature_flag_service] = lambda: FlagsOff()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_a_worker_with_income_gets_a_score_now(api: TestClient, fib: FakeFib) -> None:
    fib.income = [("i1", {"amount": 1000, "currency": "PHP", "category": "salary"})]

    response = api.post(URL)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "recomputed"
    assert fib.profile is not None and "overall_score" in fib.profile


def test_pressing_it_again_does_not_pay_for_a_second_report(
    api: TestClient, fib: FakeFib, gemini: FakeGemini
) -> None:
    fib.income = [("i1", {"amount": 1000, "currency": "PHP", "category": "salary"})]
    api.post(URL)
    assert fib.profile is not None
    fib.profile["computed_at"] = datetime.now(UTC)

    response = api.post(URL)

    assert response.json()["status"] == "fresh"
    assert gemini.calls == 1


def test_nothing_logged_yet_is_said_plainly(api: TestClient) -> None:
    response = api.post(URL)

    assert response.status_code == 200
    assert response.json() == {"status": "no_data", "computed_at": None}


def test_it_needs_a_signed_in_worker() -> None:
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post(URL).status_code == 401
