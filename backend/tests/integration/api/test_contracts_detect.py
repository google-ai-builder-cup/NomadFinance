from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import (
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
    get_gemini_client,
)
from app.main import create_app
from app.schemas.contract import MAX_CONTRACT_TEXT_CHARS, DetectedContract
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/contracts/detect"

SAMPLE = DetectedContract(
    language="ms",
    host_country="MY",
    host_country_evidence="employer address: Johor, Malaysia",
    document_kind="employment_contract",
    job_type="plantation_worker",
    employer_name="Ladang Sawit Sri Jaya Sdn Bhd",
    agency_name=None,
    salary_amount=1500,
    salary_currency="MYR",
    salary_period="month",
)


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: DetectedContract | Exception = SAMPLE
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> DetectedContract:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def fake_gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def app(fake_gemini: FakeGemini) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_detected_facts(api: TestClient, fake_gemini: FakeGemini) -> None:
    response = api.post(URL, json={"text": "PERJANJIAN KERJA\n\n2 Gaji bulanan: RM 1.500"})

    assert response.status_code == 200
    assert response.json() == {
        "language": "ms",
        "host_country": "MY",
        "host_country_evidence": "employer address: Johor, Malaysia",
        "document_kind": "employment_contract",
        "job_type": "plantation_worker",
        "employer_name": "Ladang Sawit Sri Jaya Sdn Bhd",
        "agency_name": None,
        "salary_amount": 1500.0,
        "salary_currency": "MYR",
        "salary_period": "month",
    }
    assert "Gaji bulanan: RM 1.500" in fake_gemini.calls[0]["contents"]


def test_unknown_country_comes_back_as_null(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = SAMPLE.model_copy(
        update={"host_country": None, "host_country_evidence": ""}
    )

    response = api.post(URL, json={"text": "A loan of 500."})

    assert response.status_code == 200
    assert response.json()["host_country"] is None


def test_missing_token_is_rejected(app: FastAPI, fake_gemini: FakeGemini) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        response = client.post(URL, json={"text": "x"})

    assert response.status_code == 401
    assert fake_gemini.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "   \n  "},
        {"text": 12},
        {"text": "x" * (MAX_CONTRACT_TEXT_CHARS + 1)},
    ],
)
def test_bad_text_is_rejected_before_gemini(
    api: TestClient, fake_gemini: FakeGemini, body: dict[str, Any]
) -> None:
    response = api.post(URL, json=body)

    assert response.status_code == 422
    assert fake_gemini.calls == []


def test_text_of_the_maximum_length_is_accepted(api: TestClient) -> None:
    response = api.post(URL, json={"text": "x" * MAX_CONTRACT_TEXT_CHARS})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiRateLimitError("quota"), 503),
        (GeminiUnavailableError("down"), 503),
        (GeminiTimeoutError("slow"), 504),
        (GeminiResponseError("junk"), 502),
        (GeminiRequestError("rejected"), 500),
    ],
)
def test_gemini_failures_get_short_errors_without_internals(
    api: TestClient, fake_gemini: FakeGemini, error: Exception, status_code: int
) -> None:
    fake_gemini.outcome = error

    response = api.post(URL, json={"text": "some contract"})

    assert response.status_code == status_code
    assert set(response.json()) == {"detail"}
    assert "some contract" not in response.text
    assert str(error) not in response.text


def test_the_endpoint_is_listed_in_openapi_and_uses_the_ai_rate_limit(api: TestClient) -> None:
    schema = api.get("/openapi.json").json()

    assert "/api/v1/contracts/detect" in schema["paths"]
    assert schema["paths"]["/api/v1/contracts/detect"]["post"]["responses"]["429"]
