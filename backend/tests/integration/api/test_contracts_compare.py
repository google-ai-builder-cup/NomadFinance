from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiResponseError, GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.repositories.labor_law_repo import get_labor_law_repository
from app.schemas.contract_compare import ComparisonAnswer, TermAssessment
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/contracts/compare"

RULE: dict[str, Any] = {
    "coverage": "regulated",
    "title": "Keeping the passport",
    "summary": "The employer must not keep the worker's passport.",
    "variants": [{"applies_to": ["all"], "requirements": ["Must not keep the passport."]}],
    "references": [{"law": "Passports Act", "section": "s. 47", "url": "https://x"}],
    "confidence": "high",
}

BODY: dict[str, Any] = {
    "blocks": [
        {"page": 1, "kind": "heading", "number": None, "text": "CONTRACT"},
        {"page": 1, "kind": "clause", "number": "1", "text": "The employer keeps the passport."},
    ],
    "host_country": "SG",
    "job_type": "domestic_worker",
    "document_kind": "employment_contract",
}


class FakeRepo:
    def __init__(self) -> None:
        self.version: int | None = 2
        self.countries: list[str] = []

    def get_version(self, country: str) -> int | None:
        self.countries.append(country)
        return self.version

    def get_rules(self, country: str) -> dict[str, dict[str, Any]]:
        return {"passport_retention": RULE}


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: ComparisonAnswer | Exception = ComparisonAnswer(
            terms=[
                TermAssessment(
                    block_ids=[2],
                    category="passport_retention",
                    risk="danger",
                    explanation="The employer keeps your passport; the rule forbids it.",
                    recommendation="Ask to keep your own passport.",
                )
            ],
            summary="The employer keeps the passport.",
        )
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ComparisonAnswer:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def fake_repo() -> FakeRepo:
    return FakeRepo()


@pytest.fixture
def app(fake_gemini: FakeGemini, fake_repo: FakeRepo) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini
    app.dependency_overrides[get_labor_law_repository] = lambda: fake_repo
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_scored_clauses_with_the_rules_reference(
    api: TestClient, fake_repo: FakeRepo
) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["health_score"] == 49
    assert body["risk_level"] == "danger"
    assert body["clause_counts"] == {"safe": 0, "caution": 0, "danger": 1}
    assert body["law_version"] == 2
    assert body["unassessed_block_ids"] == []
    assert body["clauses"] == [
        {
            "index": 1,
            "number": "1",
            "page": 1,
            "text": "1 The employer keeps the passport.",
            "category": "passport_retention",
            "risk": "danger",
            "law_reference": "Passports Act, s. 47",
            "explanation": "The employer keeps your passport; the rule forbids it.",
            "recommendation": "Ask to keep your own passport.",
            "block_ids": [2],
        }
    ]
    assert fake_repo.countries == ["SG"]


def test_rules_sent_in_the_body_are_ignored(api: TestClient, fake_gemini: FakeGemini) -> None:
    api.post(URL, json=BODY | {"law": {"rules": []}, "rules": "anything goes"})

    assert "Must not keep the passport." in fake_gemini.calls[0]["contents"]


def test_loan_agreement_is_refused_without_calling_gemini(
    api: TestClient, fake_gemini: FakeGemini
) -> None:
    response = api.post(URL, json=BODY | {"document_kind": "loan_agreement"})

    assert response.status_code == 422
    assert "employment contracts" in response.json()["detail"]
    assert fake_gemini.calls == []


def test_country_without_labor_law_data_is_a_404(api: TestClient, fake_repo: FakeRepo) -> None:
    fake_repo.version = None

    response = api.post(URL, json=BODY)

    assert response.status_code == 404


def test_answer_without_any_usable_term_is_a_422(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = ComparisonAnswer(terms=[], summary="")

    response = api.post(URL, json=BODY)

    assert response.status_code == 422
    assert "No contract terms" in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        BODY | {"blocks": []},
        BODY | {"host_country": "US"},
        BODY | {"job_type": "pilot"},
        BODY | {"blocks": [{"page": 1, "kind": "clause", "number": None, "text": "x" * 200_001}]},
    ],
)
def test_invalid_body_is_rejected(api: TestClient, fake_gemini: FakeGemini, body: Any) -> None:
    assert api.post(URL, json=body).status_code == 422
    assert fake_gemini.calls == []


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiUnavailableError("gemini-x: 503 UNAVAILABLE"), 503),
        (GeminiResponseError("gemini-x output did not match ComparisonAnswer"), 502),
    ],
)
def test_gemini_failures_map_to_clean_errors(
    api: TestClient, fake_gemini: FakeGemini, error: Exception, status_code: int
) -> None:
    fake_gemini.outcome = error

    response = api.post(URL, json=BODY)

    assert response.status_code == status_code
    assert "gemini-x" not in response.text


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        assert client.post(URL, json=BODY).status_code == 401


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    operation = api.get("/openapi.json").json()["paths"][URL]["post"]

    assert {"401", "404", "422", "429", "503"} <= set(operation["responses"])
