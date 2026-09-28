from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.rate_repo import get_rate_repository
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/remittance/trends"


def daily(weeks: int) -> dict[str, Any]:
    """Market days up to yesterday, Wednesday 0.3% above the rest."""
    today = datetime.now(UTC).date()
    days = [today - timedelta(days=n) for n in range(1, weeks * 7 + 1)]
    return {
        d.isoformat(): {
            "rate": 43.0 * (1.003 if d.weekday() == 2 else 1.0),
            "provider": "frankfurter",
            "source": "backfill",
        }
        for d in days
        if d.weekday() < 5
    }


class FakeRates:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {
            "SGD_PHP": {"base_currency": "SGD", "quote_currency": "PHP", "daily": daily(52)}
        }
        self.reads: list[str] = []

    def get_history(self, pair_id: str) -> dict[str, Any] | None:
        self.reads.append(pair_id)
        return self.docs.get(pair_id)


@pytest.fixture
def rates() -> FakeRates:
    return FakeRates()


@pytest.fixture
def app(rates: FakeRates) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_rate_repository] = lambda: rates
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_series_summary_and_best_day(api: TestClient, rates: FakeRates) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["corridor_id"], body["pair"], body["days"]) == ("SG-PH", "SGD_PHP", 90)
    oldest = date.fromisoformat(body["points"][0]["date"])
    assert oldest > datetime.now(UTC).date() - timedelta(days=90)
    assert set(body["summary"]) == {"first", "latest", "change_pct", "low", "high", "average"}
    assert body["best_day"]["weekday"] == "wednesday"
    assert body["best_day_reason"] is None
    assert len(body["weekdays"]) == 5
    assert body["providers"] == ["frankfurter"]
    assert rates.reads == ["SGD_PHP"]  # one Firestore read per request


@pytest.mark.parametrize("days", [30, 90, 180, 365])
def test_each_period_is_accepted(api: TestClient, days: int) -> None:
    response = api.get(URL, params={"corridor_id": "SG-PH", "days": days})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["days"] == days
    assert date.fromisoformat(body["points"][0]["date"]) > datetime.now(UTC).date() - timedelta(
        days=days
    )


@pytest.mark.parametrize(
    "params",
    [
        {"corridor_id": "SG-XX"},
        {"corridor_id": "sg-ph"},
        {},
        {"corridor_id": "SG-PH", "days": 60},
        {"corridor_id": "SG-PH", "days": "a year"},
    ],
)
def test_an_invalid_query_is_a_422_before_anything_is_read(
    api: TestClient, rates: FakeRates, params: dict[str, Any]
) -> None:
    assert api.get(URL, params=params).status_code == 422
    assert rates.reads == []


def test_a_corridor_without_history_is_a_404(api: TestClient) -> None:
    response = api.get(URL, params={"corridor_id": "MY-ID"})

    assert response.status_code == 404
    assert response.json()["detail"] == "No rate history is available yet for MY-ID."


def test_short_history_answers_without_a_best_day(api: TestClient, rates: FakeRates) -> None:
    rates.docs["SGD_PHP"]["daily"] = daily(3)

    body = api.get(URL, params={"corridor_id": "SG-PH"}).json()

    assert body["best_day"] is None
    assert body["best_day_reason"] == "not_enough_history"
    assert body["weekdays"] == []


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.get(URL, params={"corridor_id": "SG-PH"}).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["get"]

    assert {"200", "401", "404", "422", "429"} <= set(operation["responses"])
    assert "remittance" in operation["tags"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert params["corridor_id"]["required"] is True
    assert params["days"]["schema"]["default"] == 90
