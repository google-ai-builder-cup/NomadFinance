from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.labor_law_repo import get_labor_law_repository
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/contracts/labor-law/JP"

RULE: dict[str, Any] = {
    "coverage": "regulated",
    "title": "Working hours and breaks",
    "summary": "No more than 8 hours a day or 40 hours a week.",
    "variants": [
        {
            "applies_to": ["all"],
            "requirements": ["No more than 40 hours per week (Art. 32)."],
            "limits": {},
            "penalty": None,
            "enforced_by": "Labour inspectorate",
        }
    ],
    "references": [{"law": "Labor Standards Act", "section": "Art. 32", "url": "https://x"}],
    "confidence": "high",
    "notes": None,
}


class FakeRepo:
    def __init__(self) -> None:
        self.version: int | None = 1
        self.rules: dict[str, dict[str, Any]] = {"working_hours": RULE}

    def get_version(self, country: str) -> int | None:
        return self.version

    def get_rules(self, country: str) -> dict[str, dict[str, Any]]:
        return self.rules


@pytest.fixture
def fake_repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def app(fake_repo: FakeRepo) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_labor_law_repository] = lambda: fake_repo
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_rules_with_the_applicable_variant(api: TestClient) -> None:
    response = api.get(URL, params={"job_type": "domestic_worker"})

    assert response.status_code == 200
    body = response.json()
    assert body["country"] == "JP"
    assert body["job_type"] == "domestic_worker"
    assert body["law_version"] == 1
    assert len(body["rules"]) == 1
    rule = body["rules"][0]
    assert rule["category"] == "working_hours"
    assert rule["applicable_variant"]["applies_to"] == ["all"]


def test_missing_job_type_is_rejected(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == 422


def test_unsupported_country_is_rejected(api: TestClient) -> None:
    response = api.get("/api/v1/contracts/labor-law/AE", params={"job_type": "other"})

    assert response.status_code == 422


def test_country_with_no_curated_data_yet_is_a_404(api: TestClient, fake_repo: FakeRepo) -> None:
    fake_repo.version = None
    fake_repo.rules = {}

    response = api.get(URL, params={"job_type": "care_worker"})

    assert response.status_code == 404


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        response = client.get(URL, params={"job_type": "care_worker"})

    assert response.status_code == 401


def test_the_endpoint_is_listed_in_openapi(api: TestClient) -> None:
    schema = api.get("/openapi.json").json()

    assert "/api/v1/contracts/labor-law/{host_country}" in schema["paths"]
