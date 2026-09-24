from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import get_settings
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
from app.schemas.contract import ExtractedText
from app.schemas.user import AuthenticatedUser

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
URL = "/api/v1/contracts/extract"


class FakeGemini:
    """Replaces the Gemini client: returns one preset result or raises one preset error."""

    def __init__(self) -> None:
        self.outcome: ExtractedText | Exception = ExtractedText(
            is_document=True, page_count=2, text="Monthly salary: SGD 650"
        )
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ExtractedText:
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


def upload(api: TestClient, name: str, data: bytes | None = None, content_type: str = "") -> Any:
    body = data if data is not None else (FIXTURES / name).read_bytes()
    return api.post(URL, files={"file": (name, body, content_type or "application/octet-stream")})


def test_pdf_upload_returns_extracted_text(api: TestClient, fake_gemini: FakeGemini) -> None:
    response = upload(api, "sample_contract_sg.pdf", content_type="application/pdf")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "filename": "sample_contract_sg.pdf",
        "mime_type": "application/pdf",
        "size_bytes": (FIXTURES / "sample_contract_sg.pdf").stat().st_size,
        "page_count": 2,
        "text": "Monthly salary: SGD 650",
    }
    assert fake_gemini.calls[0]["contents"][0].inline_data.mime_type == "application/pdf"


def test_type_comes_from_bytes_not_client_header(api: TestClient, fake_gemini: FakeGemini) -> None:
    response = upload(api, "photo.pdf", (FIXTURES / "sample_contract_my_id_photo.jpg").read_bytes())

    assert response.status_code == 200
    assert response.json()["mime_type"] == "image/jpeg"
    assert fake_gemini.calls[0]["contents"][0].inline_data.mime_type == "image/jpeg"


def test_missing_token_is_rejected(app: FastAPI) -> None:
    del app.dependency_overrides[get_current_user]
    with TestClient(app) as client:
        response = client.post(URL, files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")})

    assert response.status_code == 401


def test_missing_file_is_rejected(api: TestClient) -> None:
    assert api.post(URL).status_code == 422


def test_empty_file_is_rejected(api: TestClient) -> None:
    response = upload(api, "empty.pdf", b"")

    assert response.status_code == 400


def test_file_over_limit_is_rejected_before_gemini(
    app: FastAPI, api: TestClient, fake_gemini: FakeGemini
) -> None:
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"upload_max_bytes": 1000}
    )

    response = upload(api, "big.pdf", b"%PDF-1.4" + b"x" * 1000)

    assert response.status_code == 413
    assert fake_gemini.calls == []


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("contract.txt", b"Employer: ACME\nSalary: 100"),
        ("contract.docx", b"PK\x03\x04 word document"),
        ("fake.pdf", b"this is not really a pdf"),
    ],
)
def test_unsupported_file_type_is_rejected(
    api: TestClient, fake_gemini: FakeGemini, name: str, data: bytes
) -> None:
    response = upload(api, name, data, "application/pdf")

    assert response.status_code == 415
    assert fake_gemini.calls == []


def test_file_without_document_returns_422(api: TestClient, fake_gemini: FakeGemini) -> None:
    fake_gemini.outcome = ExtractedText(is_document=False, page_count=1, text="")

    response = upload(api, "not_a_document.jpg")

    assert response.status_code == 422
    assert "No readable document" in response.json()["detail"]


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (GeminiRateLimitError("gemini-x: 429 RESOURCE_EXHAUSTED quota"), 503),
        (GeminiUnavailableError("gemini-x: 503 UNAVAILABLE high demand"), 503),
        (GeminiTimeoutError("gemini-x did not respond within 30s"), 504),
        (GeminiResponseError("gemini-x output did not match ExtractedText"), 502),
        (GeminiRequestError("gemini-x: 400 INVALID_ARGUMENT bad"), 500),
    ],
)
def test_gemini_failures_map_to_clean_http_errors(
    api: TestClient, fake_gemini: FakeGemini, error: Exception, status_code: int
) -> None:
    fake_gemini.outcome = error

    response = upload(api, "sample_contract_sg.pdf")

    assert response.status_code == status_code
    detail = response.json()["detail"]
    assert "gemini-x" not in detail
    assert "Traceback" not in response.text
    if status_code == 503:
        assert response.headers["Retry-After"] == "30"


def test_endpoint_is_documented_in_openapi(api: TestClient) -> None:
    spec = api.get("/openapi.json").json()

    operation = spec["paths"][URL]["post"]
    assert {"401", "413", "415", "422", "503"} <= set(operation["responses"])
