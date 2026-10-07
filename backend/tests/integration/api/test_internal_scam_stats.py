from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable

from app.config import get_settings
from app.core.security import InvalidTokenError
from app.main import create_app
from app.repositories.scam_stats_repo import get_scam_stats_repository

URL = "/api/v1/internal/aggregate-scam-stats"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"
AUDIENCE = "https://nomadfinance-api.example.run.app"
HEADERS = {"Authorization": "Bearer scheduler-token"}


class FakeStats:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.written: list[tuple[str, int]] = []

    def checks_created_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        if self.fail:
            raise ServiceUnavailable("down")
        return [{"verdict": {"is_scam": True, "scam_type": "lottery"}, "corridor_id": "SG-IN"}]

    def write_weeks(self, corridors: dict[str, dict[str, Any]], week: str, now: datetime) -> int:
        self.written.append((week, len(corridors)))
        return len(corridors)


def _claims(email: str = CRON_SA, verified: bool = True) -> dict[str, Any]:
    return {"email": email, "email_verified": verified, "aud": AUDIENCE}


@pytest.fixture
def stats() -> FakeStats:
    return FakeStats()


@pytest.fixture
def app(stats: FakeStats) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_scam_stats_repository] = lambda: stats
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"cron_service_account": CRON_SA, "cron_audience": AUDIENCE}
    )
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_a_scheduler_call_writes_two_weeks_for_every_corridor(
    api: TestClient, stats: FakeStats
) -> None:
    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        response = api.post(URL, headers=HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["weeks"]) == 2 and body["weeks"][0] < body["weeks"][1]
    assert body["documents_written"] == 14 and body["checks_counted"] == 2
    assert [count for _, count in stats.written] == [7, 7]
    assert datetime.fromisoformat(body["completed_at"])
    # Counts and labels: nothing of a worker's check is in the answer.
    assert set(body) == {"weeks", "checks_counted", "documents_written", "completed_at"}


def test_a_failed_week_is_a_503_so_the_scheduler_retries(app: FastAPI, api: TestClient) -> None:
    app.dependency_overrides[get_scam_stats_repository] = lambda: FakeStats(fail=True)

    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        response = api.post(URL, headers=HEADERS)

    assert response.status_code == 503
    assert response.json()["weeks"] == []


def test_a_call_with_no_token_is_401(api: TestClient) -> None:
    assert api.post(URL).status_code == 401


def test_a_token_that_does_not_verify_is_401(api: TestClient) -> None:
    with patch(
        "app.dependencies.verify_google_oidc_token",
        side_effect=InvalidTokenError("Invalid service token"),
    ):
        assert api.post(URL, headers={"Authorization": "Bearer firebase-user"}).status_code == 401


@pytest.mark.parametrize(
    "token_claims",
    [_claims(email="someone@nomadfinance-prod.iam.gserviceaccount.com"), _claims(verified=False)],
)
def test_another_google_identity_is_403(api: TestClient, token_claims: dict[str, Any]) -> None:
    with patch("app.dependencies.verify_google_oidc_token", return_value=token_claims):
        assert api.post(URL, headers=HEADERS).status_code == 403


def test_the_route_is_hidden_from_the_public_api_docs(api: TestClient) -> None:
    assert URL not in api.get("/openapi.json").json()["paths"]
