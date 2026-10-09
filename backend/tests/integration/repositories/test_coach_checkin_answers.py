"""NF-FC-022 against the Firestore emulator: the transaction that keeps the first answers, and the
field-path write that leaves the reminder's markers alone, which the in-memory stand-in imitates."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from google.cloud.firestore import Client

from app.repositories.coach_session_repo import CoachPlanRepository, SessionContentionError
from tests.fixtures.coach_checkins import DEPARTURE, DUE, PLAN_ID, at

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)

Seed = Callable[[Mapping[str, dict[str, Any]]], None]
PATH = f"users/a/coach_plans/{PLAN_ID}"
ANSWERS = {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"}
OTHER = {"remittance": "not_yet", "savings": "not_yet", "pay": "not_paid"}


def plan_doc(**extra: Any) -> dict[str, Any]:
    return {
        "departure_date": DEPARTURE,
        "created_at": at("2026-10-20"),
        "plan": {"summary": "kept as it is", "weeks": []},
    } | extra


@pytest.fixture
def plans(clean_firestore: Client) -> CoachPlanRepository:
    return CoachPlanRepository(clean_firestore)


def test_the_state_is_only_the_departure_date_and_the_markers(
    plans: CoachPlanRepository, seed_documents: Seed
) -> None:
    markers = {"d30": {"due_on": DUE["d30"], "notified_at": at(DUE["d30"])}}
    seed_documents({PATH: plan_doc(checkins=markers)})

    assert plans.checkin_state("a", PLAN_ID) == {"departure_date": DEPARTURE, "checkins": markers}
    assert plans.checkin_state("a", "0" * 20) is None
    assert plans.checkin_state("someone-else", PLAN_ID) is None


def test_answers_are_stored_beside_the_reminders_markers(
    plans: CoachPlanRepository, clean_firestore: Client, seed_documents: Seed
) -> None:
    markers = {"d30": {"due_on": DUE["d30"], "notified_at": at(DUE["d30"])}}
    seed_documents({PATH: plan_doc(checkins=markers)})

    stored = plans.answer_checkin("a", PLAN_ID, "d30", ANSWERS, at(DUE["d30"], 9))

    assert stored == (ANSWERS, at(DUE["d30"], 9), True)
    document = clean_firestore.document(PATH).get().to_dict() or {}
    assert document["checkins"]["d30"] == markers["d30"] | {
        "answers": ANSWERS,
        "answered_at": at(DUE["d30"], 9),
    }
    assert document["plan"] == {"summary": "kept as it is", "weeks": []}


def test_the_first_answers_are_kept(plans: CoachPlanRepository, seed_documents: Seed) -> None:
    seed_documents({PATH: plan_doc()})
    plans.answer_checkin("a", PLAN_ID, "d30", ANSWERS, at(DUE["d30"], 9))

    again = plans.answer_checkin("a", PLAN_ID, "d30", OTHER, at(DUE["d30"], 20))

    assert again == (ANSWERS, at(DUE["d30"], 9), False)


def test_a_milestone_can_be_answered_before_any_reminder_marker_exists(
    plans: CoachPlanRepository, clean_firestore: Client, seed_documents: Seed
) -> None:
    seed_documents({PATH: plan_doc()})

    plans.answer_checkin("a", PLAN_ID, "d60", OTHER, at(DUE["d60"]))

    document = clean_firestore.document(PATH).get().to_dict() or {}
    assert document["checkins"] == {"d60": {"answers": OTHER, "answered_at": at(DUE["d60"])}}


def test_a_missing_plan_is_none_and_nothing_is_created(
    plans: CoachPlanRepository, clean_firestore: Client
) -> None:
    assert plans.answer_checkin("a", PLAN_ID, "d30", ANSWERS, at(DUE["d30"])) is None
    assert not clean_firestore.document(PATH).get().exists


def test_of_many_taps_at_once_one_set_of_answers_is_stored(
    plans: CoachPlanRepository, clean_firestore: Client, seed_documents: Seed
) -> None:
    seed_documents({PATH: plan_doc()})

    def tap(run: int) -> bool | SessionContentionError:
        try:
            stored = plans.answer_checkin(
                "a", PLAN_ID, "d30", {**ANSWERS, "savings": "not_yet"}, at(DUE["d30"], run)
            )
        except SessionContentionError as exc:
            # The emulator locks the document for each transaction and gives up on the ones
            # that wait too long. The route answers that with a 409 and the app taps again.
            return exc
        assert stored is not None
        return stored[2]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(tap, range(4)))

    assert results.count(True) == 1
    assert all(r is True or r is False or isinstance(r, SessionContentionError) for r in results)
    document = clean_firestore.document(PATH).get().to_dict() or {}
    assert document["checkins"]["d30"]["answers"] == {**ANSWERS, "savings": "not_yet"}
