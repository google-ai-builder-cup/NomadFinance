from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import require_cloud_scheduler
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.radar_repo import get_radar_repository
from app.repositories.user_repo import get_user_repository

URL = "/api/v1/internal/aggregate-radar"
CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"


class FakeRadar:
    def reports_since(self, corridor_id: str, since: Any) -> list[dict[str, Any]]:
        return []

    def get_active_alert(self, corridor_id: str, entity_slug: str) -> None:
        return None

    def list_active_alerts(self, corridor_id: str) -> list[Any]:
        return []


class FakeUsers:
    def by_host_and_home(self, host_country: str, home_country: str) -> list[Any]:
        return []

    def subscribed_to_corridor(self, corridor_id: str) -> list[Any]:
        return []


class FakeGemini:
    async def generate_structured(self, **kwargs: Any) -> Any:
        raise AssertionError("no reports were seeded; nothing should be classified")


@pytest.fixture
def app() -> FastAPI:
    app = create_app()
    app.dependency_overrides[require_cloud_scheduler] = lambda: CRON_SA
    app.dependency_overrides[get_radar_repository] = lambda: FakeRadar()
    app.dependency_overrides[get_user_repository] = lambda: FakeUsers()
    app.dependency_overrides[get_gemini_client] = lambda: FakeGemini()
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_a_quiet_run_scans_every_corridor_and_creates_nothing(api: TestClient) -> None:
    response = api.post(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["corridors_scanned"] == 6
    assert (body["alerts_created"], body["alerts_expired"], body["notifications_sent"]) == (0, 0, 0)


def test_endpoint_is_hidden_from_public_api_docs(api: TestClient) -> None:
    assert URL not in api.get("/openapi.json").json()["paths"]


# Cloud Scheduler auth itself (missing/invalid/wrong-identity token, unconfigured cron
# settings) is the shared `require_cloud_scheduler` dependency, already covered end to end
# by test_internal_refresh.py; this file only overrides it (like that file's own
# test_override_hook_for_other_internal_tests) and tests what's specific to this endpoint.
