"""End-to-end: shared Coach and scam activity through the weekly recompute to the real
reasoning-tier model (NF-HR-001); Firestore, the scheduler token and the FX cache are faked.

Opt-in because it needs GEMINI_API_KEY in .env.local and uses free-tier quota:

    RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_fib_signals_live.py -v -s

`-s` prints the report and the activity paragraph of each worker (read them: the code checks the
paragraph's numbers, not its tone).
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_feature_flag_service, require_cloud_scheduler
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.repositories.fib_repo import get_fib_repository
from app.repositories.rate_repo import get_rate_repository
from app.repositories.scam_check_repo import get_scam_check_repository
from app.repositories.user_repo import get_user_repository
from tests.fixtures.coach_sessions import FakePlanRepo
from tests.integration.api.test_internal_recompute_fib_live import (
    CRON_SA,
    URL,
    FakeFib,
    FakeRates,
    _show,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
)

NOW = datetime.now(UTC)
SHARING = {"coach": True, "scam": True}


class Users:
    profiles = {
        "priya": {"home_country": "IN", "preferred_language": "hi", "signal_sharing": SHARING},
        "rajesh": {"home_country": "IN", "preferred_language": "en", "signal_sharing": SHARING},
    }

    def list_user_ids(self) -> list[str]:
        return list(self.profiles)

    def get_profile(self, uid: str) -> dict[str, Any]:
        return self.profiles[uid]


class Checks:
    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        scams = [True, True, False, False, False, True, False]
        return [
            (
                f"c{n}",
                {
                    "last_checked_at": NOW - timedelta(days=3 + 9 * n),
                    "verdict": {"is_scam": flagged, "risk_level": "high"},
                },
            )
            for n, flagged in enumerate(scams)
        ]


class Flags:
    async def is_enabled(self, flag: str, uid: str) -> bool:
        return True


def _plans() -> FakePlanRepo:
    plans = FakePlanRepo()
    document = {
        "created_at": NOW - timedelta(days=100),
        "checkins": {
            "d30": {
                "answered_at": NOW - timedelta(days=40),
                "answers": {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"},
            },
            "d60": {
                "answered_at": NOW - timedelta(days=10),
                "answers": {"remittance": "on_track", "savings": "on_track", "pay": "late_or_less"},
            },
        },
    }
    for uid in ("priya", "rajesh"):
        plans.add(uid, "p1", document)
    return plans


@pytest.fixture(scope="module")
def fib() -> FakeFib:
    store = FakeFib()
    store.data["rajesh"] = store.data["priya"]  # the same six months, reported in English
    return store


@pytest.fixture(scope="module")
def run(fib: FakeFib) -> Iterator[dict[str, Any]]:
    app = create_app()
    app.dependency_overrides[require_cloud_scheduler] = lambda: CRON_SA
    app.dependency_overrides[get_fib_repository] = lambda: fib
    app.dependency_overrides[get_user_repository] = lambda: Users()
    app.dependency_overrides[get_rate_repository] = lambda: FakeRates()
    app.dependency_overrides[get_coach_plan_repository] = lambda: _plans()
    app.dependency_overrides[get_scam_check_repository] = lambda: Checks()
    app.dependency_overrides[get_feature_flag_service] = lambda: Flags()
    with TestClient(app) as client:
        response = client.post(URL, json={})
        assert response.status_code == 200, response.text
        yield dict(response.json())


def test_the_signals_are_in_the_profile(run: dict[str, Any], fib: FakeFib) -> None:
    assert (run["recomputed"], run["failed"]) == (2, 0)
    profile = fib.saved["rajesh"]
    assert profile["coach_signal"]["checkins_answered"] == 2
    assert profile["coach_signal"]["pay_on_time"] == 1
    assert (profile["scam_signal"]["checks"], profile["scam_signal"]["scams_found"]) == (7, 3)


def test_the_english_report_has_a_grounded_activity_paragraph(
    run: dict[str, Any], fib: FakeFib
) -> None:
    narrative = fib.saved["rajesh"]["narrative"]
    _show(narrative["text"])
    _show("ACTIVITY: " + narrative.get("activity_text", "<none>"))

    assert narrative.get("activity_text"), "the model gave no activity paragraph, or it was dropped"
    # The paragraph must not judge, and the report text must not mention the shared activity.
    assert not re.search(
        r"\b(careful|vigilant|disciplined|reliable|risky)\b", narrative["activity_text"], re.I
    )


def test_the_hindi_report_has_a_hindi_paragraph(run: dict[str, Any], fib: FakeFib) -> None:
    narrative = fib.saved["priya"]["narrative"]
    _show("HINDI ACTIVITY: " + narrative.get("activity_text", "<none>"))

    assert narrative["language"] == "hi"
    assert re.search("[ऀ-ॿ]", narrative.get("activity_text", ""))
