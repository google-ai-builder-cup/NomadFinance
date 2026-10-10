from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.cloud_storage import get_export_store
from app.main import create_app
from app.repositories.fib_repo import get_fib_repository
from app.repositories.user_repo import get_user_repository
from app.schemas.user import AuthenticatedUser
from app.services.fib import exporter

URL = "/api/v1/fib/report/export"
CREATED = datetime(2026, 9, 20, 2, tzinfo=UTC)


class FakeFib:
    def __init__(self) -> None:
        self.profile: dict[str, Any] | None = {
            "reporting_currency": "INR",
            "period_start": "2026-05-01",
            "period_end": "2026-10-01",
            "months_of_data": 6,
            "entry_counts": {},
            "metrics": {},
            "narrative": {"language": "tl", "text": "Teksto", "model": "m"},
            "computed_at": CREATED,
        }
        self.exports: list[dict[str, Any]] = []

    def get_profile(self, uid: str) -> dict[str, Any] | None:
        return self.profile

    def set_latest_export(self, uid: str, export: dict[str, Any]) -> None:
        self.exports.append(export)
        assert self.profile is not None
        self.profile["latest_export"] = export


class FakeStore:
    def __init__(self) -> None:
        self.expires: list[timedelta] = []

    def upload(self, uid: str, filename: str, data: bytes) -> str:
        return f"exports/{uid}/{filename}"

    def delete(self, uid: str, path: str) -> None:
        return None

    def signed_url(self, uid: str, path: str, expires: timedelta, download_name: str) -> str:
        self.expires.append(expires)
        return f"https://signed.example/{path}?name={download_name}"


class FakeUsers:
    def __init__(self) -> None:
        self.profile: dict[str, Any] = {}

    def get_profile(self, uid: str) -> dict[str, Any]:
        return self.profile


@pytest.fixture
def users() -> FakeUsers:
    return FakeUsers()


@pytest.fixture
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def html_seen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    seen: list[str] = []
    monkeypatch.setattr(exporter, "render_pdf", lambda html: seen.append(html) or b"%PDF-fake")
    return seen


@pytest.fixture
def app(fib: FakeFib, store: FakeStore, users: FakeUsers, html_seen: list[str]) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_fib_repository] = lambda: fib
    app.dependency_overrides[get_user_repository] = lambda: users
    app.dependency_overrides[get_export_store] = lambda: store
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_export_returns_a_link_and_records_the_pdf(
    api: TestClient, fib: FakeFib, store: FakeStore
) -> None:
    response = api.post(URL)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["download_url"].startswith("https://signed.example/exports/test-user/financial-")
    assert body["language"] == "tl"
    assert body["filename"] == "financial-identity-report.pdf"
    assert fib.exports[0]["storage_path"].startswith("exports/test-user/financial-identity-")
    # The default lifetime is 24 hours.
    assert store.expires == [timedelta(hours=24)]


def test_the_holder_name_goes_on_the_pdf(api: TestClient, html_seen: list[str]) -> None:
    api.post(URL, json={"holder_name": "  Priya Sharma  "})
    api.post(URL, json={"holder_name": "   "})
    api.post(URL, json={})

    assert "Priya Sharma" in html_seen[0]
    assert "Prepared for" not in html_seen[1]
    assert "Prepared for" not in html_seen[2]


def test_a_holder_name_over_100_characters_is_422(api: TestClient) -> None:
    assert api.post(URL, json={"holder_name": "x" * 101}).status_code == 422


def test_export_without_a_profile_is_404(api: TestClient, fib: FakeFib) -> None:
    fib.profile = None

    response = api.post(URL)

    assert response.status_code == 404
    assert "No Financial Identity profile yet" in response.json()["detail"]


def test_get_gives_a_fresh_link_to_the_latest_export(api: TestClient, fib: FakeFib) -> None:
    fib.profile = fib.profile or {}
    fib.profile["latest_export"] = {
        "storage_path": "exports/test-user/financial-identity-20260920T020000Z.pdf",
        "created_at": CREATED,
    }

    response = api.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["download_url"].startswith("https://signed.example/exports/test-user/")
    assert body["created_at"].startswith("2026-09-20T02:00:00")


def test_get_before_any_export_is_404(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == 404
    assert response.json()["detail"] == "No report has been exported yet."


def test_the_link_lifetime_follows_the_setting(
    api: TestClient, store: FakeStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import get_settings

    monkeypatch.setenv("EXPORT_URL_EXPIRY_MINUTES", "60")
    get_settings.cache_clear()
    try:
        api.post(URL)
    finally:
        get_settings.cache_clear()

    assert store.expires == [timedelta(minutes=60)]


def test_auth_is_required_on_both(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post(URL).status_code == 401
        assert client.get(URL).status_code == 401


def test_both_are_in_the_openapi_docs(api: TestClient) -> None:
    methods = api.get("/openapi.json").json()["paths"][URL]

    assert {"post", "get"} <= set(methods)


# --- NF-HR-001: the choice is read when the report is made --------------------------------------


def _with_signal(fib: FakeFib) -> None:
    assert fib.profile is not None
    fib.profile["coach_signal"] = {
        "plan_id": "p1",
        "checkins_answered": 1,
        "remittance_on_track": 1,
        "savings_on_track": 1,
        "pay_on_time": 1,
        "last_checkin_at": CREATED,
    }


def test_the_export_prints_the_activity_while_the_worker_shares_it(
    api: TestClient, fib: FakeFib, users: FakeUsers, html_seen: list[str]
) -> None:
    _with_signal(fib)
    users.profile = {"signal_sharing": {"coach": True}}

    response = api.post(URL)

    assert response.status_code == 201
    assert "Plan check-ins answered" not in html_seen[0]  # Filipino report: its own wording
    assert "Mga check-in ng plano" in html_seen[0]
    assert fib.exports[0]["signals"] == ["coach"]


def test_the_export_leaves_it_out_once_the_worker_stopped_sharing(
    api: TestClient, fib: FakeFib, users: FakeUsers, html_seen: list[str]
) -> None:
    _with_signal(fib)
    users.profile = {"signal_sharing": {"coach": False}}

    api.post(URL)

    assert "Mga check-in ng plano" not in html_seen[0]
    assert "signals" not in fib.exports[0]


def test_the_link_to_an_older_pdf_with_activity_is_withdrawn_after_opt_out(
    api: TestClient, fib: FakeFib, users: FakeUsers
) -> None:
    fib.profile = fib.profile or {}
    fib.profile["latest_export"] = {
        "storage_path": "exports/test-user/financial-identity-20260920T020000Z.pdf",
        "created_at": CREATED,
        "signals": ["coach"],
    }
    users.profile = {"signal_sharing": {"coach": True}}
    assert api.get(URL).status_code == 200

    users.profile = {"signal_sharing": {"coach": False}}

    assert api.get(URL).status_code == 404
