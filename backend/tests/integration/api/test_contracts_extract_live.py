"""End-to-end: real HTTP request through the app to real Gemini; only auth is faked.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contracts_extract_live.py -v -s

`-s` prints each call's duration (NF-P2-001 latency record).
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


def _text_pdf(pages: list[list[str]]) -> bytes:
    """A plain text PDF (Helvetica, one line per entry), so no binary fixture is needed."""
    count = len(pages)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>"
        % (b" ".join(b"%d 0 R" % (4 + 2 * i) for i in range(count)), count),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, lines in enumerate(pages):
        escaped = [
            line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines
        ]
        body = " T* ".join(f"({line}) Tj" for line in escaped)
        stream = f"BT /F1 11 Tf 15 TL 60 760 Td {body} ET".encode()
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
            b"/Resources << /Font << /F1 3 0 R >> >> >>" % (5 + 2 * i)
        )
        objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, obj)
    xref_at = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref_at,
    )
    return bytes(pdf)


def _long_contract() -> bytes:
    """Six pages, 24 numbered clauses with sub-items, and a fee table printed as columns."""
    pages: list[list[str]] = []
    clause = 0
    for page in range(1, 7):
        lines = ["EMPLOYMENT CONTRACT - FOREIGN DOMESTIC WORKER"] if page == 1 else []
        for _ in range(4):
            clause += 1
            lines.append(
                f"{clause}. Term {clause}: the Employer and the Worker agree to this term."
            )
            lines.append(f"   (a) First condition of term {clause}.")
            lines.append(f"   (b) Second condition of term {clause}.")
        if page == 4:
            lines += [
                "Schedule of fees",
                "Item                         Amount        Paid by",
                "Placement fee                SGD 2,400     Worker",
                "Medical examination          SGD 120       Employer",
                "Work permit                  SGD 35        Employer",
            ]
        if page == 6:
            lines += ["Signed by the Employer: ____________   Date: 1 October 2026"]
        pages.append(lines)
    return _text_pdf(pages)


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    app = create_app()
    # No Firebase Auth emulator or frontend sign-in yet, so the token check is the one fake.
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="live-test")
    with TestClient(app) as client:
        yield client


def post_file(api: TestClient, name: str, data: bytes) -> tuple[int, dict[str, Any]]:
    started = time.perf_counter()
    response = api.post(URL, files={"file": (name, data, "application/octet-stream")})
    print(f"\n[{name}] {response.status_code} in {time.perf_counter() - started:.1f}s")
    return response.status_code, response.json()


def post_fixture(api: TestClient, name: str) -> tuple[int, dict[str, Any]]:
    return post_file(api, name, (FIXTURES / name).read_bytes())


def numbers(body: dict[str, Any]) -> list[str]:
    return [str(block["number"]).strip(" .") for block in body["blocks"] if block["number"]]


def test_extracts_english_pdf(api: TestClient) -> None:
    status_code, body = post_fixture(api, "sample_contract_sg.pdf")

    assert status_code == 200, body
    assert body["mime_type"] == "application/pdf"
    assert body["page_count"] == 2
    assert body["legibility"] == "good"
    text = str(body["text"])
    assert "Tan Wei Ming" in text
    assert "SGD 650" in text
    assert "passport" in text.lower()
    assert any(block["kind"] == "clause" for block in body["blocks"])
    assert {block["page"] for block in body["blocks"]} == {1, 2}


def test_extracts_photo_in_original_language(api: TestClient) -> None:
    status_code, body = post_fixture(api, "sample_contract_my_id_photo.jpg")

    assert status_code == 200, body
    assert body["mime_type"] == "image/jpeg"
    assert body["legibility"] in {"good", "partial"}
    text = str(body["text"])
    # Kept in the original language, not translated.
    assert "Gaji bulanan" in text
    assert "1.500" in text
    assert "Budi Santoso" in text
    assert all(block["page"] == 1 for block in body["blocks"])


def test_keeps_structure_of_a_long_contract(api: TestClient) -> None:
    status_code, body = post_file(api, "long_contract.pdf", _long_contract())

    assert status_code == 200, body
    assert body["page_count"] == 6
    assert max(block["page"] for block in body["blocks"]) == 6
    clause_numbers = numbers(body)
    # Every numbered term, in reading order.
    main_terms = [n for n in clause_numbers if n.isdigit()]
    assert main_terms == [str(n) for n in range(1, 25)]
    assert "(a)" in clause_numbers or "a" in clause_numbers
    tables = [block for block in body["blocks"] if block["kind"] == "table"]
    assert tables, body["blocks"]
    table = tables[0]["text"]
    assert "|" in table
    assert "Placement fee" in table and "SGD 2,400" in table
    assert tables[0]["page"] == 4
    assert "1 October 2026" in body["text"]


def test_rejects_photo_that_is_not_a_document(api: TestClient) -> None:
    status_code, body = post_fixture(api, "not_a_document.jpg")

    assert status_code == 422, body
