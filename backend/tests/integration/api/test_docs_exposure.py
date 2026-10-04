from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

DOC_PATHS = ["/docs", "/redoc", "/openapi.json"]


def _app_for(monkeypatch: pytest.MonkeyPatch, app_env: str) -> TestClient:
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("CRON_SERVICE_ACCOUNT", "scheduler@p.iam.gserviceaccount.com")
    monkeypatch.setenv("CRON_AUDIENCE", "https://api.example.test")
    for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    yield  # type: ignore[misc]
    get_settings.cache_clear()


@pytest.mark.parametrize("path", DOC_PATHS)
def test_the_interactive_docs_are_available_locally(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    assert _app_for(monkeypatch, "local").get(path).status_code == 200


@pytest.mark.parametrize("app_env", ["staging", "prod"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_a_deployed_api_does_not_publish_its_endpoint_list(
    monkeypatch: pytest.MonkeyPatch, app_env: str, path: str
) -> None:
    # The page lists every endpoint and field to anyone, signed in or not (NF-P4-004).
    assert _app_for(monkeypatch, app_env).get(path).status_code == 404


def test_the_health_check_stays_public(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _app_for(monkeypatch, "prod").get("/health").status_code == 200
