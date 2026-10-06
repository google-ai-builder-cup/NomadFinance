"""NF-P2-008: Contract Shield E2E for all 5 target countries, real pipeline, scripted Gemini.

Runs the real upload + analyze + report-switch endpoints against the real Firestore-backed
repositories (Emulator only) and the real curated labor-law and complaint-template data for
SG, AU, KR, MY and JP. Only the raw Gemini answers are scripted (tests/fixtures/
contract_e2e_scenarios.py), so this exercises the real extractor/detector/comparator/
translator/complaint code and the real per-country data end to end, at zero Gemini-quota cost
(D-58). The real-Gemini counterpart lives in test_contract_analysis_live.py (SG, in depth) and
test_contract_e2e_countries.py (AU, KR, MY, JP), both opt-in and gated on quota being available.

Needs only the Firestore Emulator. The `seeded_reference_data` fixture (tests/integration/
conftest.py) loads the 5 countries' labor law and complaint templates itself when they are
missing, so there is nothing to load by hand:

    firebase emulators:start --only firestore --project demo-nomadfinance      (frontend/)
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        pytest tests/integration/api/test_contract_e2e_mocked.py -v -s
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.base import get_firestore_client
from app.schemas.user import AuthenticatedUser
from tests.fixtures.contract_e2e_scenarios import SCENARIOS, ScriptedGemini

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)


@pytest.mark.parametrize("country", list(SCENARIOS), ids=list(SCENARIOS))
def test_full_pipeline_per_country(country: str, seeded_reference_data: tuple[str, ...]) -> None:
    assert country in seeded_reference_data
    scenario = SCENARIOS[country]
    gemini = ScriptedGemini(scenario)
    uid = f"e2e-{country.lower()}-{uuid.uuid4().hex[:8]}"
    db = get_firestore_client()
    db.document(f"users/{uid}").set(
        {
            "host_country": country,
            "job_type": scenario.job_type,
            "preferred_language": scenario.preferred_language,
        }
    )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    with TestClient(app) as api:
        files = {"file": (scenario.file, scenario.data, scenario.content_type)}

        uploaded = api.post("/api/v1/contracts", files=files)
        assert uploaded.status_code == 201, uploaded.text
        assert uploaded.json()["reused"] is False
        contract_id = uploaded.json()["contract_id"]

        analysis = api.post(f"/api/v1/contracts/{contract_id}/analyze")
        assert analysis.status_code == 200, analysis.text
        result = analysis.json()
        print(
            f"\n[{country}] score={result['health_score']} level={result['risk_level']} "
            f"counts={result['clause_counts']} languages={result['report_languages']} "
            f"complaint_pending={result['complaint_pending']}"
        )
        assert result["cached"] is False
        assert result["host_country"] == country
        assert result["job_type"] == scenario.job_type
        assert result["risk_level"] == "danger"  # every scenario scripts at least one danger term
        assert result["complaint_pending"] is False, "the scripted complaint answer always fills in"
        # Alphabetically sorted by report_store.py, not source-language-first (D-60: found here
        # because "bn" sorts before "en", unlike hi/tl/id/ne used by the other scenarios).
        assert result["report_languages"] == sorted(["en", scenario.preferred_language])

        contract = db.document(f"users/{uid}/contracts/{contract_id}").get().to_dict() or {}
        assert contract["status"] == "completed" and "error" not in contract

        english = db.document(f"users/{uid}/contracts/{contract_id}/reports/en").get().to_dict()
        translated = (
            db.document(
                f"users/{uid}/contracts/{contract_id}/reports/{scenario.preferred_language}"
            )
            .get()
            .to_dict()
        )
        assert english is not None and translated is not None
        assert english["is_source"] is True and translated["is_source"] is False
        assert [c["risk"] for c in translated["clauses"]] == [c["risk"] for c in english["clauses"]]
        assert [c["law_reference"] for c in translated["clauses"]] == [
            c["law_reference"] for c in english["clauses"]
        ]
        assert english["complaint"] is not None
        assert translated["full_text"].startswith("[T] ")

        # Re-uploading the same file and re-analyzing must not call Gemini again (the cache).
        gemini.calls.clear()
        again = api.post("/api/v1/contracts", files=files)
        assert again.json()["reused"] is True and again.json()["contract_id"] == contract_id
        cached = api.post(f"/api/v1/contracts/{contract_id}/analyze")
        assert cached.status_code == 200 and cached.json()["cached"] is True
        assert gemini.calls == [], "a cached analysis must not call Gemini again"


def test_a_loan_agreement_is_not_compared(
    monkeypatch: pytest.MonkeyPatch, seeded_reference_data: tuple[str, ...]
) -> None:
    """One real edge case found worth a dedicated check: document_kind bypasses compare/law."""
    scenario = SCENARIOS["SG"]
    loan_detected = scenario.detected.model_copy(update={"document_kind": "loan_agreement"})
    gemini = ScriptedGemini(scenario)
    monkeypatch.setattr(gemini.scenario, "detected", loan_detected)
    uid = f"e2e-loan-{uuid.uuid4().hex[:8]}"
    db = get_firestore_client()
    db.document(f"users/{uid}").set(
        {"host_country": "SG", "job_type": scenario.job_type, "preferred_language": "hi"}
    )

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    with TestClient(app) as api:
        files: dict[str, Any] = {"file": (scenario.file, scenario.data, scenario.content_type)}
        contract_id = api.post("/api/v1/contracts", files=files).json()["contract_id"]

        analysis = api.post(f"/api/v1/contracts/{contract_id}/analyze")

        assert analysis.status_code == 422
        assert "employment contracts" in analysis.json()["detail"]
        contract = db.document(f"users/{uid}/contracts/{contract_id}").get().to_dict() or {}
        assert contract["status"] == "failed"
        assert contract["error"] == {"step": "compare", "code": "not_employment_contract"}
