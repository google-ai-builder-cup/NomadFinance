"""The Coach session service (NF-FC-008): start or resume, read, save turns, move, restart."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.schemas.coach_session import MAX_TRANSCRIPT_MESSAGES
from app.services.coach.session_document import IDLE_AFTER, KEEP_FOR
from app.services.coach.session_machine import IllegalTransitionError
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import (
    NewMessage,
    SessionConflictError,
    SessionFullError,
    SessionNotActiveError,
    SessionNotFoundError,
    SlotUpdate,
)
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_sessions import NOW, FakePlanRepo, FakeSessionRepo, make_sessions

pytestmark = pytest.mark.anyio

UID = "worker-1"


def _persona(persona_id: str) -> Persona:
    return next(p for p in load_personas().personas if p.id == persona_id)


def _updates(persona: Persona, *names: str) -> list[SlotUpdate]:
    values = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    return [SlotUpdate(name, values[name], 0.95, True) for name in names]  # type: ignore[arg-type]


async def _answer_everything(
    service: CoachSessions, session_id: str, persona: Persona, now: Any = NOW
) -> Any:
    """Save the persona's answers turn by turn, in the order its script gives them."""
    session = None
    for number, turn in enumerate(persona.script, start=1):
        last = number == len(persona.script)
        # A message that fills nothing and is not a follow-up or the last one is "I do not know".
        declined = (
            persona.declined_slots if not (turn.fills or last or turn.coach_follow_up) else []
        )
        if not (turn.fills or last or declined):
            continue
        messages = [NewMessage("user", turn.say, turn.language), NewMessage("coach", "Ok.", "en")]  # type: ignore[arg-type]
        session = await service.record_turn(
            UID,
            session_id,
            language=persona.language,  # type: ignore[arg-type]
            now=now + timedelta(minutes=number),
            updates=_updates(persona, *turn.fills),
            messages=messages,
            declined=declined,  # type: ignore[arg-type]
        )
    return session


async def test_a_new_worker_gets_a_new_session_at_intro() -> None:
    service, repo, _ = make_sessions()

    result = await service.start(UID, "hi", restart=False, now=NOW)

    session = result.session
    assert result.resumed is False
    assert (session.status, session.stage, session.language) == ("active", "intro", "hi")
    assert session.next_slot == "destination_country"
    assert session.messages == [] and session.slots == {} and session.turn_count == 0
    assert session.score is None and session.plan_id is None
    stored = repo.docs[(UID, session.id)]
    assert stored["revision"] == 1 and stored["expires_at"] == NOW + KEEP_FOR
    assert stored["question_bank_version"] >= 1 and stored["schema_version"] == 1


async def test_asking_again_resumes_the_same_session_and_keeps_its_language() -> None:
    service, repo, _ = make_sessions()
    first = (await service.start(UID, "hi", restart=False, now=NOW)).session

    again = await service.start(UID, "en", restart=False, now=NOW + timedelta(hours=2))

    assert again.resumed is True and again.session.id == first.id
    assert again.session.language == "hi"
    assert len(repo.active(UID)) == 1


async def test_restart_closes_the_open_session_and_starts_another() -> None:
    service, repo, _ = make_sessions()
    first = (await service.start(UID, "hi", restart=False, now=NOW)).session

    second = await service.start(UID, "en", restart=True, now=NOW + timedelta(minutes=5))

    assert second.resumed is False and second.session.id != first.id
    assert second.session.language == "en"
    assert repo.docs[(UID, first.id)]["status"] == "abandoned"
    assert [sid for sid, _ in repo.active(UID)] == [second.session.id]


async def test_each_worker_has_a_session_of_their_own() -> None:
    service, _, _ = make_sessions()
    mine = (await service.start(UID, "en", restart=False, now=NOW)).session
    theirs = (await service.start("worker-2", "en", restart=False, now=NOW)).session

    assert mine.id != theirs.id
    with pytest.raises(SessionNotFoundError):
        await service.get("worker-2", mine.id, NOW)


async def test_a_session_idle_for_fourteen_days_is_closed_when_read_and_a_new_one_can_start() -> (
    None
):
    service, repo, _ = make_sessions()
    old = (await service.start(UID, "en", restart=False, now=NOW)).session
    later = NOW + IDLE_AFTER

    read = await service.get(UID, old.id, later)
    fresh = await service.start(UID, "tl", restart=False, now=later)

    assert read.status == "abandoned"
    assert repo.docs[(UID, old.id)]["status"] == "abandoned"
    assert fresh.resumed is False and fresh.session.id != old.id


async def test_starting_after_the_idle_limit_closes_the_old_session_in_the_same_step() -> None:
    service, repo, _ = make_sessions()
    old = (await service.start(UID, "en", restart=False, now=NOW)).session

    fresh = await service.start(UID, "en", restart=False, now=NOW + IDLE_AFTER + timedelta(hours=1))

    assert fresh.session.id != old.id
    assert repo.docs[(UID, old.id)]["status"] == "abandoned"


async def test_a_session_past_its_expiry_is_gone() -> None:
    service, _, _ = make_sessions()
    old = (await service.start(UID, "en", restart=False, now=NOW)).session

    with pytest.raises(SessionNotFoundError):
        await service.get(UID, old.id, NOW + KEEP_FOR + timedelta(seconds=1))


async def test_an_unknown_session_is_not_found() -> None:
    service, _, _ = make_sessions()

    with pytest.raises(SessionNotFoundError):
        await service.get(UID, "nope", NOW)


async def test_a_turn_is_saved_whole_with_the_answer_the_message_and_the_stage() -> None:
    service, repo, _ = make_sessions()
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session
    persona = _persona("p10_jp_ph_miguel")

    saved = await service.record_turn(
        UID,
        session.id,
        language="tl",
        now=NOW + timedelta(minutes=1),
        updates=_updates(persona, "destination_country", "job_type"),
        messages=[
            NewMessage("user", "Sa Japan po, care worker po ako. Tawag 91234567 po.", "tl"),
            NewMessage("coach", "Kailan po kayo aalis?", "tl"),
        ],
    )

    assert saved.stage == "intro" and saved.next_slot == "departure_date"
    assert set(saved.slots) == {"destination_country", "job_type"}
    assert saved.turn_count == 1 and [m.id for m in saved.messages] == ["m001-u", "m002-c"]
    assert "91234567" not in saved.messages[0].text
    assert repo.docs[(UID, session.id)]["revision"] == 2


async def test_a_coach_only_message_is_not_a_turn() -> None:
    service, _, _ = make_sessions()
    session = (await service.start(UID, "en", restart=False, now=NOW)).session

    saved = await service.record_turn(
        UID, session.id, language="en", now=NOW, messages=[NewMessage("coach", "Hello!", "en")]
    )

    assert saved.turn_count == 0 and len(saved.messages) == 1


async def test_the_whole_interview_reaches_review_then_plan_then_completed() -> None:
    service, _, _ = make_sessions()
    persona = _persona("p10_jp_ph_miguel")
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session

    reviewed = await _answer_everything(service, session.id, persona)

    assert reviewed.stage == "review" and reviewed.next_slot is None
    assert set(reviewed.slots) == set(persona.expected_slots.model_dump(exclude_none=True))
    assert all(slot.confirmed for slot in reviewed.slots.values())

    confirmed = await service.confirm_review(UID, session.id, NOW + timedelta(hours=1))
    assert confirmed.stage == "plan" and confirmed.status == "active"

    done = await service.complete(UID, session.id, "9f3a1c5e7b2d4a60c8e1", NOW + timedelta(hours=2))
    assert (done.status, done.stage, done.plan_id) == ("completed", "plan", "9f3a1c5e7b2d4a60c8e1")


async def test_a_worker_who_does_not_know_the_leaving_date_still_gets_past_intro() -> None:
    service, _, _ = make_sessions()
    persona = _persona("p06_au_in_anil")
    session = (await service.start(UID, "en", restart=False, now=NOW)).session

    reviewed = await _answer_everything(service, session.id, persona)

    assert reviewed.stage == "review" and "departure_date" not in reviewed.slots


async def test_a_correction_returns_to_the_stage_that_holds_the_answer_and_back_to_review() -> None:
    service, _, _ = make_sessions()
    persona = _persona("p10_jp_ph_miguel")
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session
    await _answer_everything(service, session.id, persona)

    corrected = await service.request_correction(UID, session.id, "monthly_salary", NOW)
    assert corrected.stage == "income" and corrected.next_slot == "monthly_salary"
    assert corrected.slots["monthly_salary"].confirmed is False

    again = await service.record_turn(
        UID,
        session.id,
        language="tl",
        now=NOW + timedelta(days=1),
        updates=[
            SlotUpdate(
                "monthly_salary",
                {"amount": 160000, "currency": "JPY", "period": "month"},
                0.9,
                True,
            )
        ],
        messages=[NewMessage("user", "160,000 yen po pala.", "tl")],
    )
    assert again.stage == "review" and again.slots["monthly_salary"].value["amount"] == 160000


async def test_a_correction_is_refused_before_review_and_for_an_unanswered_slot() -> None:
    service, _, _ = make_sessions()
    persona = _persona("p10_jp_ph_miguel")
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session
    with pytest.raises(IllegalTransitionError):
        await service.request_correction(UID, session.id, "monthly_salary", NOW)

    await _answer_everything(service, session.id, persona)
    with pytest.raises(ValueError, match="debt_interest"):
        await service.request_correction(UID, session.id, "debt_interest", NOW)


async def test_confirming_and_completing_are_refused_out_of_turn() -> None:
    service, _, _ = make_sessions()
    persona = _persona("p10_jp_ph_miguel")
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session

    with pytest.raises(IllegalTransitionError):
        await service.confirm_review(UID, session.id, NOW)
    with pytest.raises(IllegalTransitionError):
        await service.complete(UID, session.id, "9f3a1c5e7b2d4a60c8e1", NOW)

    await _answer_everything(service, session.id, persona)
    with pytest.raises(IllegalTransitionError):
        await service.complete(UID, session.id, "9f3a1c5e7b2d4a60c8e1", NOW)
    await service.confirm_review(UID, session.id, NOW)
    await service.complete(UID, session.id, "9f3a1c5e7b2d4a60c8e1", NOW)
    with pytest.raises(IllegalTransitionError):
        await service.complete(UID, session.id, "9f3a1c5e7b2d4a60c8e1", NOW)


async def test_a_finished_session_takes_no_more_turns() -> None:
    service, _, _ = make_sessions()
    session = (await service.start(UID, "en", restart=True, now=NOW)).session
    await service.start(UID, "en", restart=True, now=NOW)  # closes the first as abandoned

    with pytest.raises(SessionNotActiveError):
        await service.record_turn(UID, session.id, language="en", now=NOW)


async def test_only_the_optional_slot_can_be_declined() -> None:
    service, _, _ = make_sessions()
    session = (await service.start(UID, "en", restart=False, now=NOW)).session

    with pytest.raises(ValueError, match="required"):
        await service.record_turn(
            UID, session.id, language="en", now=NOW, declined=["monthly_salary"]
        )


async def test_a_value_the_slot_cannot_hold_is_refused_and_nothing_is_written() -> None:
    service, repo, _ = make_sessions()
    session = (await service.start(UID, "en", restart=False, now=NOW)).session

    with pytest.raises(ValueError):
        await service.record_turn(
            UID,
            session.id,
            language="en",
            now=NOW,
            updates=[SlotUpdate("dependents", -3, 0.9, True)],
        )
    assert repo.docs[(UID, session.id)]["revision"] == 1


async def test_the_transcript_stops_at_the_limit() -> None:
    service, repo, _ = make_sessions()
    session = (await service.start(UID, "en", restart=False, now=NOW)).session
    repo.docs[(UID, session.id)]["messages"] = [
        {"id": f"m{i:03d}-u", "role": "user", "text": "x", "language": "en", "at": NOW}
        for i in range(MAX_TRANSCRIPT_MESSAGES)
    ]

    with pytest.raises(SessionFullError):
        await service.record_turn(
            UID, session.id, language="en", now=NOW, messages=[NewMessage("user", "one more", "en")]
        )


async def test_a_write_that_lost_a_race_is_a_conflict_and_changes_nothing() -> None:
    service, repo, _ = make_sessions()
    session = (await service.start(UID, "en", restart=False, now=NOW)).session
    repo.stale_next_write = True

    with pytest.raises(SessionConflictError):
        await service.record_turn(
            UID, session.id, language="en", now=NOW, messages=[NewMessage("coach", "Hi", "en")]
        )
    assert repo.docs[(UID, session.id)]["messages"] == []


async def test_a_new_service_over_the_same_storage_continues_where_the_old_one_stopped() -> None:
    first, repo, plans = make_sessions()
    persona = _persona("p10_jp_ph_miguel")
    session = (await first.start(UID, "tl", restart=False, now=NOW)).session
    await first.record_turn(
        UID,
        session.id,
        language="tl",
        now=NOW + timedelta(minutes=1),
        updates=_updates(
            persona, "destination_country", "job_type", "departure_date", "monthly_salary"
        ),
        messages=[NewMessage("user", "Sa Japan po.", "tl"), NewMessage("coach", "Ilan po?", "tl")],
    )

    # The process is gone; only what was stored is left.
    restarted, _, _ = make_sessions(repo, plans)
    resumed = await restarted.start(UID, "en", restart=False, now=NOW + timedelta(hours=1))

    assert resumed.resumed is True and resumed.session.id == session.id
    assert resumed.session.stage == "obligations" and resumed.session.next_slot == "dependents"
    assert len(resumed.session.messages) == 2 and resumed.session.turn_count == 1
    again = await restarted.get(UID, session.id, NOW + timedelta(hours=1))
    assert again.slots.keys() == {
        "destination_country",
        "job_type",
        "departure_date",
        "monthly_salary",
    }


async def test_the_overview_shows_the_open_session_and_the_newest_plan_and_creates_nothing() -> (
    None
):
    service, repo, plans = make_sessions()
    empty = await service.overview(UID, NOW)
    assert empty.session is None and empty.plan is None and repo.docs == {}

    session = (await service.start(UID, "hi", restart=False, now=NOW)).session
    plans.add(
        UID,
        "a" * 20,
        {"created_at": NOW - timedelta(days=9), "score": {"total": 40, "band": "getting_ready"}},
    )
    plans.add(
        UID,
        "b" * 20,
        {
            "created_at": NOW - timedelta(days=1),
            "score": {"total": 72, "band": "well_prepared"},
            "departure_date": "2026-12-01",
        },
    )

    overview = await service.overview(UID, NOW + timedelta(minutes=1))

    assert overview.session is not None and overview.session.id == session.id
    assert overview.session.stage == "intro" and overview.session.language == "hi"
    assert overview.plan is not None
    assert (overview.plan.id, overview.plan.score_total, overview.plan.band) == (
        "b" * 20,
        72,
        "well_prepared",
    )
    assert overview.plan.departure_date == "2026-12-01"


async def test_the_overview_leaves_out_a_session_that_has_gone_idle() -> None:
    service, repo, _ = make_sessions()
    await service.start(UID, "en", restart=False, now=NOW)

    overview = await service.overview(UID, NOW + IDLE_AFTER)

    assert overview.session is None
    assert all(doc["status"] == "active" for doc in repo.docs.values())  # a read changes nothing


async def test_the_score_appears_from_review_when_an_engine_is_wired_in() -> None:
    from app.schemas.coach_plan import CoachScore, ScoreFactor

    factors = [
        ScoreFactor(id=name, value=None, score=50, weight=0.2)
        for name in (
            "debt_to_income",
            "emergency_buffer",
            "remittance_ratio",
            "recruitment_fee_vs_cap",
            "banked_status",
        )
    ]
    score = CoachScore(total=50, band="getting_ready", factors=factors, rubric_version=1)
    repo, plans = FakeSessionRepo(), FakePlanRepo()
    service = CoachSessions(repo, plans, scorer=lambda profile: score)  # type: ignore[arg-type]
    persona = _persona("p10_jp_ph_miguel")
    session = (await service.start(UID, "tl", restart=False, now=NOW)).session
    assert session.score is None

    reviewed = await _answer_everything(service, session.id, persona)

    assert reviewed.score == score
