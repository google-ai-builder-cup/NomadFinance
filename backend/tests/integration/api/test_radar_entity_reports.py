from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.radar_repo import get_radar_repository
from app.schemas.radar import RadarValidation
from app.schemas.user import AuthenticatedUser

SLUG = "example-remit"
URL = f"/api/v1/radar/entities/{SLUG}/reports"


class FakeRadar:
    def __init__(self, reports: list[tuple[str, dict[str, Any]]]) -> None:
        self.reports = reports

    def list_by_entity(self, slug: str) -> list[tuple[str, dict[str, Any]]]:
        return self.reports if slug == SLUG else []


REPORT: dict[str, Any] = {
    "entity_type": "money_transfer_operator",
    "entity_name": "Example Remit",
    "entity_slug": SLUG,
    "violation_type": "hidden_fees",
    "corridor_id": "SG-IN",
    "description": "They showed one rate and charged another.",
    "language": "en",
    "cluster_id": "r1",
    "source": "user",
    "reporter_hash": "abc123",
    "validation": RadarValidation(spam_score=0.0, category_confidence=0.9, model="m"),
    "summary": "Operator charged a worse rate than shown.",
    "created_at": "2026-09-30T12:00:00Z",
}


@pytest.fixture
def radar() -> FakeRadar:
    return FakeRadar([("r1", REPORT)])


@pytest.fixture
def app(radar: FakeRadar) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_radar_repository] = lambda: radar
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_entitys_reports(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["report_id"] == "r1"
    assert body[0]["violation_type"] == "hidden_fees"
    assert "reporter_hash" not in body[0]
    assert "validation" not in body[0]


def test_an_unknown_slug_is_an_empty_list_not_a_404(api: TestClient) -> None:
    response = api.get("/api/v1/radar/entities/no-such-entity/reports")

    assert response.status_code == 200
    assert response.json() == []


def test_a_slug_of_the_wrong_shape_is_a_422(api: TestClient) -> None:
    response = api.get("/api/v1/radar/entities/Not_A_Slug!/reports")

    assert response.status_code == 422


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.get(URL).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]

    assert "get" in paths["/api/v1/radar/entities/{slug}/reports"]
