"""NF-FC-008 against the Firestore emulator: the transactions the fakes can only imitate."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.base import get_firestore_client
from app.repositories.coach_session_repo import (
    CoachPlanRepository,
    CoachSessionRepository,
    RevisionConflictError,
    SessionContentionError,
    SessionMissingError,
)
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import IDLE_AFTER, new_document
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import NewMessage, SlotUpdate

# Real Firestore writes: only against the emulator (docs/runbooks/NF-P1-001-local-dev-setup.md).
pytestmark = [
    pytest.mark.skipif(
        "FIRESTORE_EMULATOR_HOST" not in os.environ,
        reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
    ),
    pytest.mark.anyio,
]

NOW = datetime.now(UTC).replace(microsecond=0)
BANK = load_question_bank()


@pytest.fixture
def uid() -> str:
    return f"test-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def repo() -> CoachSessionRepository:
    return CoachSessionRepository(get_firestore_client())


def _document(language: str = "en", now: datetime = NOW) -> dict:  # type: ignore[type-arg]
    return new_document(language, now, BANK)  # type: ignore[arg-type]


def _create(repo: CoachSessionRepository, uid: str, **options: object) -> tuple[str, dict, bool]:  # type: ignore[type-arg]
    settings = {"restart": False, "idle_before": NOW - IDLE_AFTER} | options
    return repo.create_or_resume(uid, repo.new_id(uid), _document(), **settings)  # type: ignore[arg-type]


def test_the_first_call_creates_the_session_and_the_second_resumes_it(
    repo: CoachSessionRepository, uid: str
) -> None:
    first_id, first, resumed = _create(repo, uid)
    second_id, second, resumed_again = _create(repo, uid)

    assert resumed is False and resumed_again is True
    assert second_id == first_id and second["status"] == "active"
    assert repo.get(uid, first_id)["revision"] == 1  # type: ignore[index]
    assert first["stage"] == "intro"


def test_restart_closes_the_active_session_and_creates_a_new_one(
    repo: CoachSessionRepository, uid: str
) -> None:
    old_id, _, _ = _create(repo, uid)

    new_id, _, resumed = _create(repo, uid, restart=True)

    assert resumed is False and new_id != old_id
    assert repo.get(uid, old_id)["status"] == "abandoned"  # type: ignore[index]
    assert [sid for sid, _ in repo.active(uid)] == [new_id]


def test_an_idle_session_is_closed_and_replaced(repo: CoachSessionRepository, uid: str) -> None:
    old_id, _, _ = _create(repo, uid)

    new_id, _, resumed = _create(repo, uid, idle_before=NOW + timedelta(seconds=1))

    assert resumed is False and new_id != old_id
    assert repo.get(uid, old_id)["status"] == "abandoned"  # type: ignore[index]


def test_requests_at_the_same_moment_never_make_two_active_sessions(
    repo: CoachSessionRepository, uid: str
) -> None:
    def start(_n: int) -> tuple[str, bool] | None:
        try:
            session_id, _doc, resumed = _create(CoachSessionRepository(get_firestore_client()), uid)
        except SessionContentionError:
            return None  # the transaction gave up under the burst: the caller is told to retry
        return session_id, resumed

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [r for r in pool.map(start, range(3)) if r is not None]

    assert len(repo.active(uid)) == 1
    assert len({session_id for session_id, _ in results}) == 1
    assert sum(1 for _, resumed in results if not resumed) <= 1


def test_a_write_names_the_revision_it_read_and_bumps_it(
    repo: CoachSessionRepository, uid: str
) -> None:
    session_id, _, _ = _create(repo, uid)

    stored = repo.update(uid, session_id, expected_revision=1, changes={"turn_count": 1})

    assert stored["revision"] == 2 and stored["turn_count"] == 1
    assert repo.get(uid, session_id)["turn_count"] == 1  # type: ignore[index]
    with pytest.raises(RevisionConflictError):
        repo.update(uid, session_id, expected_revision=1, changes={"turn_count": 99})
    assert repo.get(uid, session_id)["turn_count"] == 1  # type: ignore[index]


def test_a_write_to_a_missing_session_is_refused(repo: CoachSessionRepository, uid: str) -> None:
    with pytest.raises(SessionMissingError):
        repo.update(uid, "nope", expected_revision=1, changes={"turn_count": 1})


def test_another_workers_sessions_are_not_seen(repo: CoachSessionRepository, uid: str) -> None:
    session_id, _, _ = _create(repo, uid)
    other = f"{uid}-other"

    assert repo.get(other, session_id) is None
    assert repo.active(other) == []


def test_the_newest_plan_is_found_by_its_creation_time(uid: str) -> None:
    client = get_firestore_client()
    plans = client.collection("users").document(uid).collection("coach_plans")
    plans.document("a" * 20).set({"created_at": NOW - timedelta(days=3), "score": {"total": 40}})
    plans.document("b" * 20).set({"created_at": NOW, "score": {"total": 70}})

    newest = CoachPlanRepository(client).newest(uid)

    assert newest is not None and newest[0] == "b" * 20
    assert CoachPlanRepository(client).newest(f"{uid}-none") is None


async def test_a_session_survives_a_restart_with_real_storage(uid: str) -> None:
    client = get_firestore_client()
    first = CoachSessions(CoachSessionRepository(client), CoachPlanRepository(client))
    started = await first.start(uid, "tl", restart=False, now=NOW)
    await first.record_turn(
        uid,
        started.session.id,
        language="tl",
        now=NOW + timedelta(minutes=1),
        updates=[
            SlotUpdate("destination_country", "JP", 1.0, True),
            SlotUpdate("job_type", "care_worker", 0.95, True),
            SlotUpdate("departure_date", "2027-02-10", 1.0, True),
        ],
        messages=[
            NewMessage("user", "Sa Japan po, care worker po ako.", "tl"),
            NewMessage("coach", "Magkano po ang sahod ninyo?", "tl"),
        ],
    )

    # A new process: new client wrappers, nothing remembered.
    second = CoachSessions(CoachSessionRepository(client), CoachPlanRepository(client))
    resumed = await second.start(uid, "en", restart=False, now=NOW + timedelta(hours=1))

    assert resumed.resumed is True and resumed.session.id == started.session.id
    assert resumed.session.stage == "income" and resumed.session.next_slot == "monthly_salary"
    assert set(resumed.session.slots) == {"destination_country", "job_type", "departure_date"}
    assert [m.role for m in resumed.session.messages] == ["user", "coach"]
    assert resumed.session.turn_count == 1 and resumed.session.language == "tl"
