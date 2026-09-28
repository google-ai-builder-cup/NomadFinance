from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiResponseError, GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.repositories.complaint_template_repo import get_complaint_template_repository
from app.schemas.contract_complaint import ComplaintAnswer
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/contracts/complaint"

CLAUSE: dict[str, Any] = {
    "index": 1,
    "number": "2",
    "page": 1,
    "text": "The employer may keep the worker's passport.",
    "category": "passport_retention",
    "risk": "danger",
    "law_reference": "Passports Act, s. 47",
    "explanation": "The employer keeps your passport; the rule forbids it.",
    "recommendation": "Ask to keep your own passport.",
    "block_ids": [3],
}

BODY: dict[str, Any] = {
    "host_country": "SG",
    "clauses": [CLAUSE],
    "contract_facts": {"employer_name": "Acme Pte Ltd", "salary_amount": 650},
    "worker_language": "hi",
}

TEMPLATE: dict[str, Any] = {
    "country": "SG",
    "type": "general",
    "authority_name": "Ministry of Manpower (MOM), Singapore",
    "authority_url": "https://www.mom.gov.sg/",
    "channels": [{"kind": "phone", "value": "6438 5122"}],
    "letter_language": "en",
    "template_text": "To: {{authority_name}}\n\n{{violation_summary}}\n\nYours, {{worker_name}}",
    "placeholders": ["authority_name", "violation_summary", "worker_name"],
    "reviewed_on": "2026-09-28",
}

ANSWER: dict[str, Any] = {
    "letter_text": "To: MOM\n\n1. The contract says the employer keeps the passport.",
    "worker_copy": "प्रति: MOM\n\n1. अनुबंध के अनुसार नियोक्ता पासपोर्ट रखता है।",
}


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: ComplaintAnswer | Exception = ComplaintAnswer.model_validate(ANSWER)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ComplaintAnswer:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeRepo:
    def __init__(self) -> None:
        self.templates: dict[tuple[str, str], dict[str, Any]] = {("SG", "general"): TEMPLATE}

    def get_template(self, country: str, template_type: str) -> dict[str, Any] | None:
        return self.templates.get((country, template_type))


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
    app.dependency_overrides[get_complaint_template_repository] = lambda: fake_repo
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_returns_the_letter_the_worker_copy_and_where_to_send_it(api: TestClient) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "template_type": "general",
        "authority_name": "Ministry of Manpower (MOM), Singapore",
        "authority_url": "https://www.mom.gov.sg/",
        "channels": [{"kind": "phone", "value": "6438 5122", "note": None}],
        "letter_language": "en",
        "letter_text": ANSWER["letter_text"],
        "worker_language": "hi",
        "worker_copy": ANSWER["worker_copy"],
        "violation_count": 1,
    }


def test_the_worker_copy_is_null_when_the_worker_reads_the_letter_language(
    api: TestClient,
) -> None:
    response = api.post(URL, json=BODY | {"worker_language": "en"})

    assert response.status_code == 200, response.text
    assert response.json()["worker_copy"] is None


def test_contract_facts_are_optional(api: TestClient) -> None:
    body = {k: v for k, v in BODY.items() if k != "contract_facts"}

    assert api.post(URL, json=body).status_code == 200


def test_no_danger_clause_is_a_422_without_a_gemini_call(
    api: TestClient, fake_gemini: FakeGemini
) -> None:
    body = BODY | {"clauses": [CLAUSE | {"risk": "caution"}, CLAUSE | {"index": 2, "risk": "safe"}]}

    response = api.post(URL, json=body)

    assert response.status_code == 422
    assert "nothing to report" in response.json()["detail"]
    assert fake_gemini.calls == []


def test_a_country_without_a_template_is_a_404(api: TestClient, fake_gemini: FakeGemini) -> None:
    response = api.post(URL, json=BODY | {"host_country": "JP"})

    assert response.status_code == 404
    assert "JP" in response.json()["detail"]
    assert fake_gemini.calls == []


def test_an_unfilled_placeholder_is_a_502(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = ComplaintAnswer.model_validate(
        ANSWER | {"letter_text": "To: MOM. Yours, {{worker_name}}"}
    )

    response = api.post(URL, json=BODY)

    assert response.status_code == 502
    assert "worker_name" not in response.text


@pytest.mark.parametrize(
    "body",
    [
        BODY | {"clauses": []},
        BODY | {"host_country": "AE"},
        BODY | {"host_country": "sg"},
        BODY | {"worker_language": "fr"},
        {k: v for k, v in BODY.items() if k != "worker_language"},
        BODY | {"contract_facts": {"salary_period": "year"}},
    ],
)
def test_invalid_body_is_rejected_before_gemini(
    api: TestClient, fake_gemini: FakeGemini, body: dict[str, Any]
) -> None:
    response = api.post(URL, json=body)

    assert response.status_code == 422
    assert fake_gemini.calls == []


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiUnavailableError("gemini-x: 503 UNAVAILABLE"), 503),
        (GeminiResponseError("gemini-x output did not match ComplaintAnswer"), 502),
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

    assert {"401", "404", "422", "429", "502", "503", "504"} <= set(operation["responses"])
