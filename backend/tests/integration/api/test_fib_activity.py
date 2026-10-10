"""`GET /api/v1/fib/activity` (NF-HR-001)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_feature_flag_service
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.repositories.fib_repo import get_fib_repository
from app.repositories.scam_check_repo import get_scam_check_repository
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/fib/activity"


class FakeFib:
    def __init__(self) -> None:
        today = datetime.now(UTC).date()
        self.income = [
            (
                "i1",
                {
                    "entry_date": (today - timedelta(days=2)).isoformat(),
                    "amount": 650,
                    "currency": "SGD",
                    "category": "salary",
                    "verified": False,
                },
            )
        ]

    def list_entries(self, uid: str, kind: str) -> list[tuple[str, dict[str, Any]]]:
        return self.income if kind == "income" else []


class FakePlans:
    def activity(self, uid: str, limit: int) -> list[tuple[str, dict[str, Any]]]:
        return [
            ("p1", {"created_at": datetime.now(UTC) - timedelta(days=1), "corridor_id": "SG-PH"})
        ]


class FakeChecks:
    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        return [
            (
                "c1",
                {
                    "last_checked_at": datetime.now(UTC),
                    "verdict": {"is_scam": True, "risk_level": "high", "scam_type": "loan_app"},
                },
            )
        ]


class FakeFlags:
    def __init__(self) -> None:
        self.on = {"coach", "scam"}

    async def is_enabled(self, flag: str, uid: str) -> bool:
        return flag in self.on


@pytest.fixture
def flags() -> FakeFlags:
    return FakeFlags()


@pytest.fixture
def app(flags: FakeFlags) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_fib_repository] = lambda: FakeFib()
    app.dependency_overrides[get_coach_plan_repository] = lambda: FakePlans()
    app.dependency_overrides[get_scam_check_repository] = lambda: FakeChecks()
    app.dependency_overrides[get_feature_flag_service] = lambda: flags
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_the_feed_lists_the_three_sources_newest_first(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["kind"] for item in body["items"]] == ["scam_check", "coach_plan", "income"]
    assert body["days"] == 90 and body["truncated"] is False
    assert body["items"][0] == {
        "id": "c1",
        "on": datetime.now(UTC).date().isoformat(),
        "kind": "scam_check",
        "is_scam": True,
        "risk_level": "high",
        "scam_type": "loan_app",
    }


def test_a_module_that_is_off_is_not_in_the_feed(api: TestClient, flags: FakeFlags) -> None:
    flags.on = {"coach"}

    kinds = [item["kind"] for item in api.get(URL).json()["items"]]

    assert kinds == ["coach_plan", "income"]


@pytest.mark.parametrize("query", ["days=0", "days=366", "limit=0", "limit=201", "days=x"])
def test_out_of_range_parameters_are_422(api: TestClient, query: str) -> None:
    assert api.get(f"{URL}?{query}").status_code == 422


def test_limit_and_days_are_honoured(api: TestClient) -> None:
    body = api.get(f"{URL}?limit=1&days=7").json()

    assert len(body["items"]) == 1 and body["days"] == 7 and body["truncated"] is True


def test_auth_is_required(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get(URL).status_code == 401


def test_the_route_is_in_the_openapi_docs(api: TestClient) -> None:
    spec = api.get("/openapi.json").json()

    assert "get" in spec["paths"][URL]
    assert "ScamCheckItem" in spec["components"]["schemas"]
