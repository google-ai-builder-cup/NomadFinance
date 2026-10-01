"""End-to-end: real HTTP request through the app to real Gemini Vision; auth, Firestore and
Cloud Storage are faked.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_fib_bill_scan_live.py -v -s

The bills are generated text PDFs, so no real worker's bill is kept in the repository.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.cloud_storage import get_bill_image_store
from app.main import create_app
from app.repositories.fib_repo import EntryKind, get_fib_repository
from app.schemas.user import AuthenticatedUser
from tests.integration.api.test_contracts_extract_live import _text_pdf

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

NOT_A_DOCUMENT = (
    Path(__file__).resolve().parents[2] / "fixtures" / "contracts" / "not_a_document.jpg"
)
URL = "/api/v1/fib/bill/scan"


class FakeFib:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def new_id(self, uid: str, kind: EntryKind) -> str:
        return f"live_{len(self.docs) + 1}"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


class FakeStore:
    def upload(
        self, uid: str, entry_id: str, extension: str, data: bytes, content_type: str
    ) -> str:
        return f"bills/{uid}/{entry_id}/bill.{extension}"


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    app.dependency_overrides[get_fib_repository] = lambda: FakeFib()
    app.dependency_overrides[get_bill_image_store] = lambda: FakeStore()
    with TestClient(app) as client:
        yield client


def _scan(api: TestClient, data: bytes) -> Any:
    return api.post(URL, files={"file": ("bill", data, "application/octet-stream")})


def test_unpaid_english_utility_bill(api: TestClient) -> None:
    pdf = _text_pdf(
        [
            [
                "EXAMPLE POWER PTE LTD - ELECTRICITY BILL",
                "Account no: 123-456-789      Bill date: 20 Sep 2026",
                "Usage charges                 SGD 61.20",
                "GST 9%                        SGD 5.51",
                "Total amount due              SGD 66.71",
                "Pay by 05 Oct 2026",
            ]
        ]
    )

    response = _scan(api, pdf)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == 66.71
    assert body["currency"] == "SGD"
    assert body["paid"] is False
    assert body["bill_date"] == "2026-09-20"
    assert body["category"] == "utilities"


def test_paid_indonesian_receipt_with_day_first_date_and_dot_separators(api: TestClient) -> None:
    pdf = _text_pdf(
        [
            [
                "KWITANSI PEMBAYARAN SEWA KAMAR",
                "Tanggal: 05/09/2026",
                "Diterima dari: Siti",
                "Sewa kamar bulan September     Rp 1.250.000",
                "LUNAS",
            ]
        ]
    )

    response = _scan(api, pdf)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["amount"] == 1250000
    assert body["currency"] == "IDR"
    assert body["paid"] is True
    assert body["bill_date"] == "2026-09-05"
    assert body["category"] == "rent"


def test_a_photo_that_is_not_a_bill_is_refused(api: TestClient) -> None:
    response = _scan(api, NOT_A_DOCUMENT.read_bytes())

    assert response.status_code == 422, response.text
    assert "No bill found" in response.json()["detail"]
