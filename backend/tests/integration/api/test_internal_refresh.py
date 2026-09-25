from __future__ import annotations

from collections.abc import Iterator, Sequence
from datetime import datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
from app.core.security import InvalidTokenError
from app.dependencies import require_cloud_scheduler
from app.integrations.fx import FxQuote, FxResult, ProviderAttempt, get_fx_router
from app.main import create_app
from app.repositories.rate_repo import get_rate_repository

URL = "/api/v1/internal/refresh-rates"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"
AUDIENCE = "https://nomadfinance-api.example.run.app"


class FakeFx:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxResult:
        if self.fail and base == "JPY":
            return FxResult(None, None, [ProviderAttempt("frankfurter", False, "http_500")])
        quote = FxQuote(base=base, rates={q: 1.5 for q in quotes}, rate_date="2026-09-26")
        return FxResult(quote, "frankfurter", [ProviderAttempt("frankfurter", True)])


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[str] = []

    def save_pair(self, pair: Any, *args: Any) -> None:
        self.saved.append(pair.pair_id)


@pytest.fixture
def repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def app(repo: FakeRepo) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_fx_router] = lambda: FakeFx()
    app.dependency_overrides[get_rate_repository] = lambda: repo
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"cron_service_account": CRON_SA, "cron_audience": AUDIENCE}
    )
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def claims(email: str = CRON_SA, verified: bool = True) -> dict[str, Any]:
    return {"email": email, "email_verified": verified, "aud": AUDIENCE}


def test_scheduler_call_refreshes_all_pairs(api: TestClient, repo: FakeRepo) -> None:
    with patch("app.dependencies.verify_google_oidc_token", return_value=claims()) as verify:
        response = api.post(URL, headers={"Authorization": "Bearer scheduler-token"})

    assert response.status_code == 200
    body = response.json()
    assert len(body["refreshed"]) == 6
    assert body["failed"] == []
    assert datetime.fromisoformat(body["completed_at"])
    assert len(repo.saved) == 6
    verify.assert_called_once_with("scheduler-token", AUDIENCE)


def test_partial_failure_returns_503_so_scheduler_retries(app: FastAPI, api: TestClient) -> None:
    app.dependency_overrides[get_fx_router] = lambda: FakeFx(fail=True)
    with patch("app.dependencies.verify_google_oidc_token", return_value=claims()):
        response = api.post(URL, headers={"Authorization": "Bearer scheduler-token"})

    assert response.status_code == 503
    assert [item["pair"] for item in response.json()["failed"]] == ["JPY_PHP"]
    assert len(response.json()["refreshed"]) == 5


def test_missing_token_is_401(api: TestClient) -> None:
    assert api.post(URL).status_code == 401


def test_invalid_or_user_token_is_401(api: TestClient) -> None:
    with patch(
        "app.dependencies.verify_google_oidc_token",
        side_effect=InvalidTokenError("Invalid service token"),
    ):
        response = api.post(URL, headers={"Authorization": "Bearer firebase-user-token"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "token_claims",
    [claims(email="someone@nomadfinance-prod.iam.gserviceaccount.com"), claims(verified=False)],
)
def test_other_google_identities_are_403(api: TestClient, token_claims: dict[str, Any]) -> None:
    with patch("app.dependencies.verify_google_oidc_token", return_value=token_claims):
        response = api.post(URL, headers={"Authorization": "Bearer other-token"})
    assert response.status_code == 403


def test_unconfigured_internal_auth_is_503(app: FastAPI, api: TestClient) -> None:
    app.dependency_overrides[get_settings] = get_settings  # local defaults: no cron settings
    response = api.post(URL, headers={"Authorization": "Bearer anything"})
    assert response.status_code == 503


def test_endpoint_is_hidden_from_public_api_docs(api: TestClient) -> None:
    assert URL not in api.get("/openapi.json").json()["paths"]


def test_override_hook_for_other_internal_tests(app: FastAPI, api: TestClient) -> None:
    app.dependency_overrides[require_cloud_scheduler] = lambda: CRON_SA
    assert api.post(URL).status_code == 200
