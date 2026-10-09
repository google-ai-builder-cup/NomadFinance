"""NF-FC-016: `POST /api/v1/internal/send-coach-checkins`, who may call it and what it answers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import InvalidTokenError
from app.dependencies import get_feature_flag_service
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.repositories.user_repo import get_user_repository
from app.services.coach import checkin_job
from tests.fixtures.coach_checkins import (
    PLAN_ID,
    FakeFlags,
    FakePlans,
    FakeUsers,
    Pushes,
    profile,
)

URL = "/api/v1/internal/send-coach-checkins"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"
AUDIENCE = "https://nomadfinance-api.example.run.app"
HEADERS = {"Authorization": "Bearer scheduler-token"}


def _claims(email: str = CRON_SA, verified: bool = True) -> dict[str, Any]:
    return {"email": email, "email_verified": verified, "aud": AUDIENCE}


@pytest.fixture
def plans() -> FakePlans:
    return FakePlans()


@pytest.fixture
def users() -> FakeUsers:
    return FakeUsers()


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> Pushes:
    pushes = Pushes()
    monkeypatch.setattr(checkin_job, "send_push", pushes)
    return pushes


@pytest.fixture
def app(plans: FakePlans, users: FakeUsers, pushes: Pushes) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_coach_plan_repository] = lambda: plans
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_feature_flag_service] = lambda: FakeFlags()
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"cron_service_account": CRON_SA, "cron_audience": AUDIENCE}
    )
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def _plan_due_today(plans: FakePlans, users: FakeUsers, days_ago: int = 30) -> None:
    departure = (datetime.now(UTC) - timedelta(days=days_ago)).date().isoformat()
    plans.add(departure_date=departure)
    users.profiles["u1"] = profile()


def test_a_scheduler_call_sends_the_due_reminder_and_counts_it(
    api: TestClient, plans: FakePlans, users: FakeUsers, pushes: Pushes
) -> None:
    _plan_due_today(plans, users)

    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        response = api.post(URL, headers=HEADERS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["plans_found"], body["notified"], body["failed"]) == (1, 1, 0)
    assert datetime.fromisoformat(body["completed_at"])
    assert len(users.notifications) == 1 and len(pushes.sent) == 1
    # Counts only: neither a worker nor a plan is named in the answer.
    assert set(body) == {
        "day",
        "plans_found",
        "notified",
        "already_sent",
        "skipped",
        "failed",
        "completed_at",
    }
    assert "u1" not in response.text and PLAN_ID not in response.text


def test_calling_twice_sends_one_reminder(
    api: TestClient, plans: FakePlans, users: FakeUsers, pushes: Pushes
) -> None:
    _plan_due_today(plans, users, days_ago=60)

    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        first = api.post(URL, headers=HEADERS).json()
        second = api.post(URL, headers=HEADERS).json()

    assert (first["notified"], second["notified"], second["already_sent"]) == (1, 0, 1)
    assert len(users.notifications) == 1 and len(pushes.sent) == 1


def test_a_day_with_nothing_due_is_a_plain_200(api: TestClient) -> None:
    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        response = api.post(URL, headers=HEADERS)

    assert response.status_code == 200 and response.json()["plans_found"] == 0


def test_a_failed_read_is_a_503_so_the_scheduler_retries(
    api: TestClient, plans: FakePlans, users: FakeUsers
) -> None:
    _plan_due_today(plans, users)
    plans.fail_mark = True

    with patch("app.dependencies.verify_google_oidc_token", return_value=_claims()):
        response = api.post(URL, headers=HEADERS)

    assert response.status_code == 503
    assert response.json()["failed"] == 1


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
