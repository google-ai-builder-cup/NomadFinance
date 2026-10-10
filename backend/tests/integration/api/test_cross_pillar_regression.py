"""NF-HR-004: one worker through Contract Shield, Financial Identity and the Coach, end to end.

The three pillars share data: a checked contract becomes verified income in the Financial Identity,
the Coach offers that salary as an answer it already knows, the weekly profile prints it as
verified employment, and deleting the account removes all of it. Each seam has its own unit tests;
this one runs the real routes, services and repositories against the Firestore emulator, with only
Gemini scripted, so a change on one side of a seam that the other side was not told about fails
here (NF-HR-001 added more of them: the shared-activity signals and their opt-out).

    firebase emulators:start --only firestore --project demo-nomadfinance      (frontend/)
    FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \\
        pytest tests/integration/api/test_cross_pillar_regression.py -v
"""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    get_account_service,
    get_current_user,
    get_feature_flag_service,
    require_cloud_scheduler,
)
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.base import get_firestore_client
from app.schemas.fib_profile import NarrativeAnswer
from app.schemas.user import AuthenticatedUser
from app.services.auth_service import AccountService
from tests.fixtures.contract_e2e_scenarios import SCENARIOS, ScriptedGemini

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)

SESSIONS = "/api/v2/coach/sessions"
RECOMPUTE = "/api/v1/internal/recompute-fib-profiles"


class _Gemini(ScriptedGemini):
    """The contract answers of the scenario, plus the one the Financial Identity report asks for."""

    async def generate_structured(self, **kwargs: Any) -> Any:
        if kwargs["response_model"] is NarrativeAnswer:
            return NarrativeAnswer(text="Income is steady.", activity_text="")
        return await super().generate_structured(**kwargs)


class _NoFiles:
    """Cloud Storage for the deletion: this emulator is Firestore only, and there are no files."""

    def delete_user_files(self, uid: str) -> int:
        return 0


@pytest.fixture
def worker(seeded_reference_data: tuple[str, ...]) -> Iterator[tuple[TestClient, str]]:
    uid = f"hr004-{uuid.uuid4().hex[:10]}"
    db = get_firestore_client()
    db.document(f"users/{uid}").set(
        {
            "host_country": "SG",
            "home_country": "IN",
            "job_type": "domestic_worker",
            "preferred_language": "hi",
            "signal_sharing": {"coach": True, "scam": True},
        }
    )
    # The Coach is behind a flag that is on for this worker only; the service keeps a copy for a
    # minute, so it is asked again. The document is shared with every other test (and, on a
    # long-lived emulator, with whoever is using it), so what was there is put back afterwards.
    flags = db.document("config/feature_flags")
    previous = flags.get()
    flags.set({"flags": {"coach": {"enabled": False, "allow_uids": [uid]}}}, merge=True)
    get_feature_flag_service.cache_clear()

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid=uid, auth_time=int(time.time()) - 30
    )
    app.dependency_overrides[get_gemini_client] = lambda: _Gemini(SCENARIOS["SG"])
    app.dependency_overrides[require_cloud_scheduler] = lambda: "scheduler"
    app.dependency_overrides[get_account_service] = lambda: AccountService(
        get_firestore_client(), _NoFiles(), lambda _uid: True
    )
    with TestClient(app) as api:
        yield api, uid
    db.recursive_delete(db.document(f"users/{uid}"))
    if previous.exists:
        flags.set(previous.to_dict() or {})
    else:
        flags.delete()
    get_feature_flag_service.cache_clear()


def _income(uid: str) -> list[dict[str, Any]]:
    return [
        d.to_dict() or {} for d in get_firestore_client().collection(f"users/{uid}/income").stream()
    ]


def test_a_contract_becomes_verified_income_the_coach_knows_and_the_profile_prints(
    worker: tuple[TestClient, str],
) -> None:
    api, uid = worker
    scenario = SCENARIOS["SG"]
    files = {"file": (scenario.file, scenario.data, scenario.content_type)}

    # Contract Shield: upload and check the Singapore sample, in Hindi.
    uploaded = api.post("/api/v1/contracts", files=files)
    assert uploaded.status_code == 201, uploaded.text
    contract_id = uploaded.json()["contract_id"]
    analysis = api.post(f"/api/v1/contracts/{contract_id}/analyze")
    assert analysis.status_code == 200, analysis.text
    assert analysis.json()["report_language"] == "hi"

    # -> Financial Identity: the contract's salary is one verified income entry, made once.
    entries = _income(uid)
    assert len(entries) == 1
    assert entries[0]["source"] == "contract" and entries[0]["verified"] is True
    assert entries[0]["contract_ref"] == contract_id
    assert (entries[0]["amount"], entries[0]["currency"]) == (650, "SGD")
    assert api.post(f"/api/v1/contracts/{contract_id}/analyze").json()["cached"] is True
    assert len(_income(uid)) == 1, "checking the same contract again must not log the salary twice"

    # -> Coach: the salary is offered as an answer already known, with the contract as its source.
    session = api.post(SESSIONS, json={"language": "hi"})
    assert session.status_code == 201, session.text
    offered = {item["slot"]: item for item in session.json()["known"]["items"]}
    assert offered["monthly_salary"]["source"] == "contract"
    assert offered["monthly_salary"]["value"]["amount"] == 650

    # -> the weekly profile: verified employment names the employer and points at the contract.
    recomputed = api.post(RECOMPUTE, json={})
    assert recomputed.status_code == 200, recomputed.text
    profile = (
        get_firestore_client().document(f"users/{uid}/financial_profile/current").get().to_dict()
    )
    assert profile is not None
    employment = profile["verified_employment"]
    assert employment[0]["contract_ref"] == contract_id
    assert employment[0]["salary_amount"] == 650

    # -> the worker's own activity feed lists the logged salary, newest first.
    feed = api.get("/api/v1/fib/activity", params={"days": 90})
    assert feed.status_code == 200, feed.text
    assert [item["kind"] for item in feed.json()["items"]].count("income") == 1


def test_deleting_the_account_removes_what_every_pillar_stored(
    worker: tuple[TestClient, str],
) -> None:
    api, uid = worker
    scenario = SCENARIOS["SG"]
    db = get_firestore_client()
    contract_id = api.post(
        "/api/v1/contracts", files={"file": (scenario.file, scenario.data, scenario.content_type)}
    ).json()["contract_id"]
    assert api.post(f"/api/v1/contracts/{contract_id}/analyze").status_code == 200
    assert api.post(SESSIONS, json={"language": "en"}).status_code == 201
    assert api.post(RECOMPUTE, json={}).status_code == 200
    # A scam check and a Coach plan are stored under the same user, so they go with it.
    db.document(f"users/{uid}/scam_checks/check-1").set({"created_at": datetime.now(UTC)})
    db.document(f"users/{uid}/coach_plans/plan-1").set({"created_at": datetime.now(UTC)})
    before = {c.id for c in db.document(f"users/{uid}").collections()}
    assert {"contracts", "income", "financial_profile", "coach_sessions", "scam_checks"} <= before

    assert api.delete("/api/v1/users/me").status_code == 204

    assert not db.document(f"users/{uid}").get().exists
    assert list(db.document(f"users/{uid}").collections()) == []
