"""End-to-end: real HTTP request through the app to real Gemini; only auth is faked.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contracts_extract_live.py -v
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.schemas.user import AuthenticatedUser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
URL = "/api/v1/contracts/extract"


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    # No Firebase Auth emulator or frontend sign-in yet, so the token check is the one fake.
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    with TestClient(app) as client:
        yield client


def post_fixture(api: TestClient, name: str) -> tuple[int, dict[str, object]]:
    data = (FIXTURES / name).read_bytes()
    response = api.post(URL, files={"file": (name, data, "application/octet-stream")})
    return response.status_code, response.json()


def test_extracts_english_pdf(api: TestClient) -> None:
    status_code, body = post_fixture(api, "sample_contract_sg.pdf")

    assert status_code == 200, body
    assert body["mime_type"] == "application/pdf"
    assert body["page_count"] == 2
    text = str(body["text"])
    assert "Tan Wei Ming" in text
    assert "SGD 650" in text
    assert "passport" in text.lower()


def test_extracts_photo_in_original_language(api: TestClient) -> None:
    status_code, body = post_fixture(api, "sample_contract_my_id_photo.jpg")

    assert status_code == 200, body
    assert body["mime_type"] == "image/jpeg"
    text = str(body["text"])
    # Kept in the original language, not translated.
    assert "Gaji bulanan" in text
    assert "1.500" in text
    assert "Budi Santoso" in text


def test_rejects_photo_that_is_not_a_document(api: TestClient) -> None:
    status_code, body = post_fixture(api, "not_a_document.jpg")

    assert status_code == 422, body
