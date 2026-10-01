from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.cloud_storage import get_bill_image_store
from app.integrations.gemini import GeminiTimeoutError, get_gemini_client
from app.main import create_app
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.schemas.fib import ExtractedBill
from app.schemas.user import AuthenticatedUser

URL = "/api/v1/fib/bill/scan"
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


class FakeGemini:
    def __init__(self) -> None:
        self.outcome: ExtractedBill | Exception = ExtractedBill(
            is_bill=True,
            amount=38.5,
            currency="SGD",
            vendor="Example Telecom",
            bill_date="2026-09-20",
            paid=True,
            category="phone_internet",
            confidence=0.94,
        )
        self.calls = 0

    async def generate_structured(self, **kwargs: Any) -> ExtractedBill:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeFib:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def new_id(self, uid: str, kind: EntryKind) -> str:
        return "b_1"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


class FakeStore:
    def upload(
        self, uid: str, entry_id: str, extension: str, data: bytes, content_type: str
    ) -> str:
        return f"bills/{uid}/{entry_id}/bill.{extension}"


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
    app.dependency_overrides[get_bill_image_store] = lambda: FakeStore()
    return app


@pytest.fixture
def api(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def _upload(api: TestClient, data: bytes = JPEG) -> Any:
    return api.post(URL, files={"file": ("bill.jpg", data, "image/jpeg")})


def test_a_bill_photo_is_read_and_stored(api: TestClient, fib: FakeFib) -> None:
    response = _upload(api)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["entry_id"] == "b_1"
    assert body["amount"] == 38.5
    assert body["currency"] == "SGD"
    assert body["vendor"] == "Example Telecom"
    assert body["paid"] is True
    assert body["paid_assumed"] is False
    assert body["category"] == "phone_internet"
    assert body["category_source"] == "model"
    assert body["image_path"] == "bills/test-user/b_1/bill.jpg"
    assert body["confidence"] == 0.94
    assert fib.docs["test-user/bills/b_1"]["source"] == "bill_ocr"


def test_a_non_bill_is_422(api: TestClient, gemini: FakeGemini, fib: FakeFib) -> None:
    gemini.outcome = ExtractedBill(is_bill=False, confidence=0)

    response = _upload(api)

    assert response.status_code == 422
    assert "No bill found" in response.json()["detail"]
    assert fib.docs == {}


def test_an_unreadable_amount_is_422(api: TestClient, gemini: FakeGemini, fib: FakeFib) -> None:
    gemini.outcome = ExtractedBill(is_bill=True, amount=None, currency="SGD", confidence=0.2)

    response = _upload(api)

    assert response.status_code == 422
    assert "amount or currency" in response.json()["detail"]
    assert fib.docs == {}


def test_a_gemini_timeout_is_504_and_nothing_is_stored(
    api: TestClient, gemini: FakeGemini, fib: FakeFib
) -> None:
    gemini.outcome = GeminiTimeoutError("slow")

    response = _upload(api)

    assert response.status_code == 504
    assert fib.docs == {}


def test_an_empty_file_is_400_and_gemini_is_not_called(api: TestClient, gemini: FakeGemini) -> None:
    response = _upload(api, b"")

    assert response.status_code == 400
    assert gemini.calls == 0


def test_a_file_that_is_not_a_document_is_415(api: TestClient, gemini: FakeGemini) -> None:
    response = _upload(api, b"just some text, not a photo")

    assert response.status_code == 415
    assert gemini.calls == 0


def test_no_file_is_422(api: TestClient) -> None:
    assert api.post(URL).status_code == 422


def test_an_oversized_file_is_413(api: TestClient, gemini: FakeGemini) -> None:
    response = _upload(api, JPEG + b"0" * (10 * 1024 * 1024))

    assert response.status_code == 413
    assert gemini.calls == 0


def test_auth_is_required(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user)
    with TestClient(app, raise_server_exceptions=False) as client:
        assert _upload(client).status_code == 401


def test_the_endpoint_is_in_the_openapi_docs(api: TestClient) -> None:
    assert "post" in api.get("/openapi.json").json()["paths"][URL]
