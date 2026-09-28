"""NF-P2-008: Contract Shield E2E across host countries, real Gemini + Firestore emulator.

Complements test_contract_analysis_live.py (which covers SG in depth: cache reuse, letter
retry, language switch). This file runs the upload + analyze flow once per remaining
country with a real sample contract, and prints per-step timing for latency profiling.

Opt-in, same setup as the SG live test:

    firebase emulators:start --only firestore --project demo-nomadfinance      (frontend/)
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        python -m src.loaders.ilo_natlex --only AU KR MY JP                     (data-scripts/)
    ... python -m src.loaders.complaint_templates --only AU KR MY JP
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contract_e2e_countries.py -v -s
"""

from __future__ import annotations

import os
import time
import uuid
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

# One sample per remaining host country (SG is covered in depth by the sibling live test).
# Each contract mixes compliant and violating clauses (passport retention, recruitment
# fees, and one more) so the reasoning step has real terms of both risks to assess.
CASES: list[dict[str, Any]] = [
    {
        "country": "AU",
        "file": "sample_contract_au.pdf",
        "job_type": "construction_worker",
        "preferred_language": "tl",
    },
    {
        "country": "KR",
        "file": "sample_contract_kr.pdf",
        "job_type": "manufacturing_worker",
        "preferred_language": "bn",
    },
    {
        "country": "MY",
        "file": "sample_contract_my_id_photo.jpg",
        "job_type": "plantation_worker",
        "preferred_language": "id",
    },
    {
        "country": "JP",
        "file": "sample_contract_jp.pdf",
        "job_type": "care_worker",
        "preferred_language": "ne",
    },
]


def _content_type(filename: str) -> str:
    return "application/pdf" if filename.endswith(".pdf") else "image/jpeg"


def timed(label: str, call: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    response = call()
    elapsed = time.perf_counter() - started
    print(f"\n[{label}] {response.status_code} in {elapsed:.1f}s")
    return response, elapsed


@pytest.fixture
def api_for(request: pytest.FixtureRequest) -> Any:
    """A TestClient signed in as a fresh worker with the given onboarding profile."""

    def _make(host_country: str, job_type: str, preferred_language: str) -> tuple[TestClient, str]:
        uid = f"live-{host_country.lower()}-{uuid.uuid4().hex[:8]}"
        db = get_firestore_client()
        db.document(f"users/{uid}").set(
            {
                "host_country": host_country,
                "job_type": job_type,
                "preferred_language": preferred_language,
            }
        )
        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)
        client = TestClient(app)
        request.addfinalizer(client.close)
        return client, uid

    return _make


@pytest.mark.parametrize("case", CASES, ids=[c["country"] for c in CASES])
def test_upload_and_analyze_a_real_contract(api_for: Any, case: dict[str, Any]) -> None:
    country = case["country"]
    db = get_firestore_client()
    if not db.document(f"labor_laws/{country}/_meta/current").get().exists:
        pytest.skip(f"load the {country} labor law into the emulator first (see module docstring)")

    api, uid = api_for(country, case["job_type"], case["preferred_language"])
    data = (FIXTURES / case["file"]).read_bytes()
    files = {"file": (case["file"], data, _content_type(case["file"]))}

    uploaded, upload_s = timed(
        f"{country} upload", lambda: api.post("/api/v1/contracts", files=files)
    )
    assert uploaded.status_code == 201, uploaded.text
    contract_id = uploaded.json()["contract_id"]
    assert uploaded.json()["legibility"] in {"good", "partial"}

    analysis, analyze_s = timed(
        f"{country} analyze", lambda: api.post(f"/api/v1/contracts/{contract_id}/analyze")
    )
    assert analysis.status_code == 200, analysis.text
    result = analysis.json()
    print(
        f"  {country}: score={result['health_score']} level={result['risk_level']} "
        f"counts={result['clause_counts']} languages={result['report_languages']} "
        f"complaint_pending={result['complaint_pending']}"
    )
    assert 0 <= result["health_score"] <= 100
    assert result["risk_level"] in {"safe", "caution", "danger"}
    assert sum(result["clause_counts"].values()) > 0, "no term was assessed"
    # Alphabetically sorted (report_store.py), not source-language-first — see D-60.
    assert result["report_languages"] == sorted(["en", case["preferred_language"]])

    contract = db.document(f"users/{uid}/contracts/{contract_id}").get().to_dict() or {}
    assert contract["status"] == "completed" and "error" not in contract
    assert contract["detected"]["host_country"] == country

    english = db.document(f"users/{uid}/contracts/{contract_id}/reports/en").get().to_dict()
    translated = (
        db.document(f"users/{uid}/contracts/{contract_id}/reports/{case['preferred_language']}")
        .get()
        .to_dict()
    )
    assert english is not None and translated is not None
    assert english["is_source"] is True and translated["is_source"] is False
    assert [c["risk"] for c in translated["clauses"]] == [c["risk"] for c in english["clauses"]]

    if result["risk_level"] == "danger" and not result["complaint_pending"]:
        assert english["complaint"] is not None, "danger clauses should produce a letter"

    total_s = upload_s + analyze_s
    print(
        f"  {country} TOTAL: upload={upload_s:.1f}s analyze={analyze_s:.1f}s total={total_s:.1f}s"
    )
