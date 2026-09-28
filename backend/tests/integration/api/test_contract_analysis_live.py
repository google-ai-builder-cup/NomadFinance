"""End-to-end Contract Shield (NF-P2-007): upload, analyze, cache, language switch.

Real Gemini and real Firestore code, against the Firestore emulator only (never production).
Opt-in: it needs GEMINI_API_KEY in .env.local, the emulator with the curated SG labor law and
complaint template loaded, and about 6 Gemini calls:

    firebase emulators:start --only firestore --project demo-nomadfinance      (frontend/)
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        python -m src.loaders.ilo_natlex --only SG                              (data-scripts/)
    ... python -m src.loaders.complaint_templates --only SG
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contract_analysis_live.py -v -s
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import create_app
from app.repositories.base import get_firestore_client
from app.schemas.user import AuthenticatedUser

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1" or "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="live test; needs RUN_LIVE_GEMINI=1 and the Firestore emulator",
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "contracts"
UID = f"live-{uuid.uuid4().hex[:10]}"


@pytest.fixture(scope="module")
def api() -> Iterator[TestClient]:
    db = get_firestore_client()
    if not db.document("labor_laws/SG/_meta/current").get().exists:
        pytest.skip("load the SG labor law into the emulator first (see module docstring)")
    # The worker's onboarding profile: reads Hindi, works in Singapore.
    db.document(f"users/{UID}").set(
        {"host_country": "SG", "job_type": "domestic_worker", "preferred_language": "hi"}
    )
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=UID)
    with TestClient(app) as client:
        yield client


def timed(label: str, call: Any) -> Any:
    started = time.perf_counter()
    response = call()
    print(f"\n[{label}] {response.status_code} in {time.perf_counter() - started:.1f}s")
    return response


def test_upload_analyze_reuse_and_switch_language(api: TestClient) -> None:
    pdf = (FIXTURES / "sample_contract_sg.pdf").read_bytes()
    files = {"file": ("sg.pdf", pdf, "application/pdf")}

    uploaded = timed("upload", lambda: api.post("/api/v1/contracts", files=files))
    assert uploaded.status_code == 201, uploaded.text
    contract_id = uploaded.json()["contract_id"]

    analysis = timed("analyze", lambda: api.post(f"/api/v1/contracts/{contract_id}/analyze"))
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    print(
        f"  score={result['health_score']} level={result['risk_level']} "
        f"counts={result['clause_counts']} languages={result['report_languages']}"
    )
    assert result["risk_level"] == "danger"
    assert result["report_languages"] == ["en", "hi"]
    if result["complaint_pending"]:
        # Gemini failed the letter for a passing reason: what the app does, analyze again.
        retry = timed("letter retry", lambda: api.post(f"/api/v1/contracts/{contract_id}/analyze"))
        assert retry.json()["complaint_pending"] is False, retry.text

    db = get_firestore_client()
    contract = db.document(f"users/{UID}/contracts/{contract_id}").get().to_dict() or {}
    assert contract["status"] == "completed" and "error" not in contract
    assert contract["detected"]["host_country"] == "SG"
    english = db.document(f"users/{UID}/contracts/{contract_id}/reports/en").get().to_dict()
    hindi = db.document(f"users/{UID}/contracts/{contract_id}/reports/hi").get().to_dict()
    assert english is not None and hindi is not None
    assert english["is_source"] is True and hindi["is_source"] is False
    assert english["complaint"] is not None, "danger clauses should produce a letter"
    print(f"  complaint to: {english['complaint']['authority_name']}")
    assert [c["risk"] for c in hindi["clauses"]] == [c["risk"] for c in english["clauses"]]

    again = timed("upload again", lambda: api.post("/api/v1/contracts", files=files))
    assert again.json() | {"reused": True} == again.json()
    assert again.json()["contract_id"] == contract_id
    cached = timed("analyze again", lambda: api.post(f"/api/v1/contracts/{contract_id}/analyze"))
    assert cached.json()["cached"] is True

    tagalog = timed("report in tl", lambda: api.post(f"/api/v1/contracts/{contract_id}/reports/tl"))
    assert tagalog.status_code == 200, tagalog.text
    assert tagalog.json()["language"] == "tl"
