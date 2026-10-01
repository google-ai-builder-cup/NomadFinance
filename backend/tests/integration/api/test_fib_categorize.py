from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import GeminiTimeoutError, get_gemini_client
from app.main import create_app
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.schemas.fib import CategorizeAnswer, CategorizeResult
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/fib/categorize"


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: CategorizeAnswer | Exception = CategorizeAnswer(
            results=[CategorizeResult(id="b1", category="phone_internet", confidence=0.97)]
        )
        self.calls = 0

    async def generate_structured(self, **kwargs: Any) -> CategorizeAnswer:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeFib:
    def __init__(self) -> None:
        self.bills: dict[str, dict[str, Any]] = {
            "b1": {"entry_date": "2026-09-20", "amount": 38.5, "currency": "SGD", "vendor": "Telco"}
        }

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        return list(self.bills.items()) if kind == "bills" else []

    def update_entry(
        self, uid: str, kind: EntryKind, entry_id: str, fields: dict[str, Any]
    ) -> None:
        self.bills[entry_id] |= fields


@pytest.fixture
def gemini() -> FakeGemini:
    return FakeGemini()


@pytest.fixture
def fib() -> FakeFib:
    return FakeFib()


@pytest.fixture
def app(gemini: FakeGemini, fib: FakeFib) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="test-user")
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    app.dependency_overrides[get_fib_repository] = lambda: fib
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_pending_entries_are_categorized(api: TestClient, fib: FakeFib) -> None:
    response = api.post(URL)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "categorized": [
            {
                "entry_id": "b1",
                "entry_type": "bill",
                "category": "phone_internet",
                "confidence": 0.97,
            }
        ],
        "skipped": 0,
        "remaining": 0,
    }
    assert fib.bills["b1"]["category_source"] == "model"
    assert fib.bills["b1"]["category_confidence"] == 0.97


def test_a_second_call_makes_no_gemini_call(api: TestClient, gemini: FakeGemini) -> None:
    api.post(URL)
    assert gemini.calls == 1

    response = api.post(URL)

    assert response.status_code == 200
    assert response.json() == {"categorized": [], "skipped": 0, "remaining": 0}
    assert gemini.calls == 1


def test_a_gemini_timeout_is_504_and_nothing_is_written(
    api: TestClient, gemini: FakeGemini, fib: FakeFib
) -> None:
    gemini.outcome = GeminiTimeoutError("slow")

    response = api.post(URL)

    assert response.status_code == 504
    assert "category" not in fib.bills["b1"]


def test_auth_is_required(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post(URL).status_code == 401


def test_the_endpoint_is_in_the_openapi_docs(api: TestClient) -> None:
    assert "post" in api.get("/openapi.json").json()["paths"][URL]
