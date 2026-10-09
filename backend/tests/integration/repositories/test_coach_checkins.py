"""NF-FC-016 against the Firestore emulator: the collection-group query, the atomic notification
id and the time-travel run that the in-memory stand-ins can only imitate."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import Aborted
from google.cloud.firestore import Client

from app.config import get_settings
from app.dependencies import get_feature_flag_service
from app.main import create_app
from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.config_repo import ConfigRepository
from app.repositories.user_repo import UserRepository
from app.services.coach import checkin_job
from app.services.coach.checkin_job import send_checkins
from app.services.feature_flag_service import FeatureFlagService
from tests.fixtures.coach_checkins import (
    DEPARTURE,
    DUE,
    NEWER_PLAN_ID,
    PLAN_ID,
    FakeFlags,
    Pushes,
    at,
    profile,
)

# Real Firestore writes: only against the emulator (docs/runbooks/NF-P1-001-local-dev-setup.md).
pytestmark = [
    pytest.mark.skipif(
        "FIRESTORE_EMULATOR_HOST" not in os.environ,
        reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
    ),
    pytest.mark.anyio,
]

Seed = Callable[[Mapping[str, dict[str, Any]]], None]
DEPARTED = date.fromisoformat(DEPARTURE)
OLD_PLAN_ID = "0f0f0f0f0f0f0f0f0f0f"


def day(after_departure: int) -> str:
    return (DEPARTED + timedelta(days=after_departure)).isoformat()


def plan_doc(departure: str | None, created: str = "2026-10-20", **extra: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "created_at": at(created),
        "plan": {"summary": "kept as it is", "weeks": []},
    } | extra
    if departure is not None:
        document["departure_date"] = departure
    return document


@pytest.fixture
def plans(clean_firestore: Client) -> CoachPlanRepository:
    return CoachPlanRepository(clean_firestore)


@pytest.fixture
def users(clean_firestore: Client) -> UserRepository:
    return UserRepository(clean_firestore)


# --- the repository methods --------------------------------------------------------------


def test_the_query_finds_every_workers_plans_in_the_range_and_nothing_else(
    plans: CoachPlanRepository, seed_documents: Seed
) -> None:
    seed_documents(
        {
            f"users/a/coach_plans/{PLAN_ID}": plan_doc("2026-12-01"),
            f"users/b/coach_plans/{PLAN_ID}": plan_doc("2026-12-04", checkins={"d30": {"x": 1}}),
            f"users/c/coach_plans/{PLAN_ID}": plan_doc("2026-11-30"),
            f"users/d/coach_plans/{PLAN_ID}": plan_doc("2026-12-05"),
            f"users/e/coach_plans/{PLAN_ID}": plan_doc(None),
            # The same collection name under another parent is not a worker's plan.
            f"elsewhere/x/coach_plans/{PLAN_ID}": plan_doc("2026-12-02"),
        }
    )

    found = plans.departing_between("2026-12-01", "2026-12-04")

    assert sorted((uid, plan_id) for uid, plan_id, _ in found) == [
        ("a", PLAN_ID),
        ("b", PLAN_ID),
    ]
    by_uid = {uid: document for uid, _, document in found}
    # Only what the job reads: the plan itself is large and stays in storage.
    assert by_uid["a"] == {"departure_date": "2026-12-01"}
    assert by_uid["b"] == {"departure_date": "2026-12-04", "checkins": {"d30": {"x": 1}}}


def test_a_marker_keeps_what_sits_beside_it(
    plans: CoachPlanRepository, clean_firestore: Client, seed_documents: Seed
) -> None:
    answered = {"answered_at": at("2027-01-02"), "answers": {"q1": "yes"}}
    seed_documents(
        {f"users/a/coach_plans/{PLAN_ID}": plan_doc(DEPARTURE, checkins={"d30": answered})}
    )

    plans.mark_checkin("a", PLAN_ID, "d60", DUE["d60"], at(day(60)))
    plans.mark_checkin("a", PLAN_ID, "d30", DUE["d30"], at(day(30)))

    stored = clean_firestore.document(f"users/a/coach_plans/{PLAN_ID}").get().to_dict() or {}
    assert stored["checkins"]["d30"] == answered | {
        "due_on": DUE["d30"],
        "notified_at": at(day(30)),
    }
    assert stored["checkins"]["d60"] == {"due_on": DUE["d60"], "notified_at": at(day(60))}
    assert stored["plan"] == {"summary": "kept as it is", "weeks": []}


def test_a_marker_can_start_the_checkins_map(
    plans: CoachPlanRepository, clean_firestore: Client, seed_documents: Seed
) -> None:
    seed_documents({f"users/a/coach_plans/{PLAN_ID}": plan_doc(DEPARTURE)})

    plans.mark_checkin("a", PLAN_ID, "d90", DUE["d90"], at(day(90)))

    stored = clean_firestore.document(f"users/a/coach_plans/{PLAN_ID}").get().to_dict() or {}
    assert stored["checkins"] == {"d90": {"due_on": DUE["d90"], "notified_at": at(day(90))}}


def test_a_notification_id_is_taken_once(users: UserRepository, clean_firestore: Client) -> None:
    assert users.create_notification_once("a", "n1", {"title": "first"}) is True
    assert users.create_notification_once("a", "n1", {"title": "second"}) is False

    stored = clean_firestore.document("users/a/notifications/n1").get().to_dict()
    assert stored == {"title": "first"}


def test_of_many_runs_at_once_only_one_creates_the_notification(
    users: UserRepository, clean_firestore: Client
) -> None:
    def create(run: int) -> bool | Aborted:
        try:
            return users.create_notification_once("a", "n1", {"run": run})
        except Aborted as exc:
            # The emulator answers a lock timeout, not "exists", to a create that waited on
            # another. The job counts it as failed, the run is a 503 and the retry finds the
            # notification there: no second push either way.
            return exc

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(create, range(8)))

    assert results.count(True) == 1
    assert all(r is True or r is False or isinstance(r, Aborted) for r in results)
    assert (clean_firestore.document("users/a/notifications/n1").get().to_dict() or {}).keys() == {
        "run"
    }


# --- the time-travel run -----------------------------------------------------------------


async def test_the_job_run_every_day_for_110_days_sends_each_milestone_once(
    plans: CoachPlanRepository,
    users: UserRepository,
    clean_firestore: Client,
    seed_documents: Seed,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pushes = Pushes()
    monkeypatch.setattr(checkin_job, "send_push", pushes)
    seed_documents(
        {
            # u1: the plain case. u2: reminders off. u3: moved the date, so the first plan is old.
            "users/u1": profile(),
            f"users/u1/coach_plans/{PLAN_ID}": plan_doc(DEPARTURE),
            "users/u2": profile(notification_prefs={"reminders": False}),
            f"users/u2/coach_plans/{PLAN_ID}": plan_doc(DEPARTURE),
            "users/u3": profile(preferred_language="id", fcm_tokens=["token-3"]),
            f"users/u3/coach_plans/{OLD_PLAN_ID}": plan_doc(DEPARTURE, created="2026-10-01"),
            f"users/u3/coach_plans/{NEWER_PLAN_ID}": plan_doc(day(15), created="2026-11-20"),
            # u4: no date, u5: leaves long after the run, u6: the coach flag is off for them.
            "users/u4": profile(),
            f"users/u4/coach_plans/{PLAN_ID}": plan_doc(None),
            "users/u5": profile(),
            f"users/u5/coach_plans/{PLAN_ID}": plan_doc("2030-01-01"),
            "users/u6": profile(),
            f"users/u6/coach_plans/{PLAN_ID}": plan_doc(DEPARTURE),
        }
    )
    flags = cast(FeatureFlagService, FakeFlags({"u1", "u2", "u3", "u4", "u5"}))

    notified_on: list[int] = []
    for after_departure in range(-3, 108):
        for _ in range(2):  # the scheduler's retry, or a second "run now"
            result, complete = await send_checkins(plans, users, flags, at(day(after_departure)))
            assert complete and result.failed == 0
            notified_on += [after_departure] * result.notified

    # u1's three, then u3's three (its newer plan left 15 days later).
    assert notified_on == [30, 45, 60, 75, 90, 105]
    assert len(pushes.sent) == 6

    def notifications(uid: str) -> dict[str, dict[str, Any]]:
        collection = clean_firestore.collection(f"users/{uid}/notifications")
        return {doc.id: doc.to_dict() or {} for doc in collection.stream()}

    first = notifications("u1")
    assert sorted(first) == [f"coach_checkin_{PLAN_ID}_{m}" for m in ("d30", "d60", "d90")]
    for milestone, days in (("d30", 30), ("d60", 60), ("d90", 90)):
        n = first[f"coach_checkin_{PLAN_ID}_{milestone}"]
        assert n["type"] == "coach_checkin" and n["read"] is False and n["language"] == "hi"
        assert n["deep_link"] == f"/coach/checkin/{PLAN_ID}?m={days}"
        assert n["created_at"] == at(day(days))
    assert {n["language"] for n in notifications("u3").values()} == {"id"}
    assert sorted(notifications("u3")) == [
        f"coach_checkin_{NEWER_PLAN_ID}_{m}" for m in ("d30", "d60", "d90")
    ]
    for silent in ("u2", "u4", "u5", "u6"):
        assert notifications(silent) == {}

    stored = clean_firestore.document(f"users/u1/coach_plans/{PLAN_ID}").get().to_dict() or {}
    assert {m: stored["checkins"][m]["due_on"] for m in ("d30", "d60", "d90")} == DUE
    assert stored["checkins"]["d30"]["notified_at"] == at(day(30))
    assert stored["plan"] == {"summary": "kept as it is", "weeks": []}
    assert "checkins" not in (
        clean_firestore.document(f"users/u3/coach_plans/{OLD_PLAN_ID}").get().to_dict() or {}
    )


# --- the route, with every store real ----------------------------------------------------

CRON_SA = "nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com"
AUDIENCE = "https://nomadfinance-api.example.run.app"


def _call_the_route(clean_firestore: Client) -> Any:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"cron_service_account": CRON_SA, "cron_audience": AUDIENCE}
    )
    # A fresh reader, so a flag document seeded by this test is not hidden by a copy cached
    # earlier in the process.
    app.dependency_overrides[get_feature_flag_service] = lambda: FeatureFlagService(
        ConfigRepository(clean_firestore)
    )
    claims = {"email": CRON_SA, "email_verified": True, "aud": AUDIENCE}
    with (
        patch("app.dependencies.verify_google_oidc_token", return_value=claims),
        TestClient(app) as api,
    ):
        return api.post(
            "/api/v1/internal/send-coach-checkins", headers={"Authorization": "Bearer scheduler"}
        )


def test_the_route_reads_the_flag_and_the_plans_and_writes_the_reminder(
    clean_firestore: Client, seed_documents: Seed, monkeypatch: pytest.MonkeyPatch
) -> None:
    pushes = Pushes()
    monkeypatch.setattr(checkin_job, "send_push", pushes)
    departure = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
    seed_documents(
        {
            "config/feature_flags": {"flags": {"coach": {"enabled": False, "allow_uids": ["u1"]}}},
            "users/u1": profile(),
            f"users/u1/coach_plans/{PLAN_ID}": plan_doc(departure),
            "users/u2": profile(),
            f"users/u2/coach_plans/{PLAN_ID}": plan_doc(departure),
        }
    )

    response = _call_the_route(clean_firestore)

    # u1 is on the flag's allow-list; u2 is not, so u2's plan is found and left alone.
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["plans_found"], body["notified"], body["skipped"], body["failed"]) == (2, 1, 1, 0)
    assert len(pushes.sent) == 1
    ids = [d.id for d in clean_firestore.collection("users/u1/notifications").stream()]
    assert ids == [f"coach_checkin_{PLAN_ID}_d30"]
    assert list(clean_firestore.collection("users/u2/notifications").stream()) == []

    again = _call_the_route(clean_firestore).json()
    assert (again["notified"], again["already_sent"]) == (0, 1)
    assert len(pushes.sent) == 1
