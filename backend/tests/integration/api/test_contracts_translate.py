from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiResponseError, GeminiUnavailableError, get_gemini_client
from app.main import create_app
from app.schemas.contract_translate import TranslationAnswer
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/contracts/translate"

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
    "full_text": "CONTRACT ...",
    "summary": "The employer keeps the passport.",
    "clauses": [CLAUSE],
    "target_language": "hi",
}

ANSWER: dict[str, Any] = {
    "full_text": "अनुबंध ...",
    "summary": "नियोक्ता पासपोर्ट रखता है।",
    "clauses": [
        {
            "index": 1,
            "category": "passport_retention",
            "risk": "danger",
            "text": "नियोक्ता कर्मचारी का पासपोर्ट रख सकता है।",
            "explanation": "नियोक्ता आपका पासपोर्ट रखता है; नियम इसे मना करता है।",
            "recommendation": "अपना पासपोर्ट खुद रखने के लिए कहें।",
        }
    ],
}


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: TranslationAnswer | Exception = TranslationAnswer.model_validate(ANSWER)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> TranslationAnswer:
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


def test_returns_the_translated_report_with_source_fields_carried_over(api: TestClient) -> None:
    response = api.post(URL, json=BODY)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language"] == "hi"
    assert body["full_text"] == "अनुबंध ..."
    assert body["clauses"] == [
        {
            "index": 1,
            "number": "2",
            "page": 1,
            "text": "नियोक्ता कर्मचारी का पासपोर्ट रख सकता है।",
            "category": "passport_retention",
            "risk": "danger",
            "law_reference": "Passports Act, s. 47",
            "explanation": "नियोक्ता आपका पासपोर्ट रखता है; नियम इसे मना करता है।",
            "recommendation": "अपना पासपोर्ट खुद रखने के लिए कहें।",
            "block_ids": [3],
        }
    ]


def test_a_clause_left_out_of_the_answer_is_a_502(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = TranslationAnswer.model_validate(ANSWER | {"clauses": []})

    response = api.post(URL, json=BODY)

    assert response.status_code == 502


@pytest.mark.parametrize(
    "body",
    [
        BODY | {"full_text": ""},
        BODY | {"summary": "   "},
        BODY | {"clauses": []},
        BODY | {"target_language": "fr"},
        BODY | {"target_language": "FR"},
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
        (GeminiResponseError("gemini-x output did not match TranslationAnswer"), 502),
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

    assert {"401", "422", "429", "502", "503", "504"} <= set(operation["responses"])
