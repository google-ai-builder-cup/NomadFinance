"""The review step: the worker's reply moves the interview on or back (NF-FC-020).

At `review` the coach lists the answers and asks if they are right. A yes goes to the plan; a
wish to change an answer goes back to the question that holds it; anything else changes nothing.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.schemas.coach_review import ReviewReading
from app.services.coach.question_bank import load_question_bank
from app.services.coach.review_reader import (
    CONFIRM_AT,
    REVIEW_PROMPT,
    CoachReviewReader,
    ReviewMove,
    decide,
)
from app.services.coach.session_types import NewMessage, SlotUpdate
from app.services.coach.turn_prompt import WHICH_ANSWER, projected, reply_message
from app.services.coach.turn_types import Understanding
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import UID
from tests.fixtures.coach_sessions import NOW, make_sessions
from tests.fixtures.fake_gemini import FakeGemini, as_client

pytestmark = pytest.mark.anyio

BANK = load_question_bank()
ANSWERED = {"monthly_salary", "remittance_target", "destination_country"}


def reading(action: str, evidence: str = "yes", confidence: float = 0.95, slot: str | None = None):
    return ReviewReading.model_validate(
        {"action": action, "evidence": evidence, "confidence": confidence, "slot": slot}
    )


# --- what a reading is allowed to move --------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "evidence"),
    [("Yes, that is right", "that is right"), ("YES.", "yes"), ("  sahi   hai ", "sahi hai")],
)
def test_a_sure_yes_in_the_workers_own_words_confirms(message: str, evidence: str) -> None:
    assert decide(reading("confirm", evidence), message, ANSWERED) == ReviewMove("confirm")


def test_a_yes_that_is_not_sure_enough_moves_nothing() -> None:
    assert decide(reading("confirm", confidence=CONFIRM_AT - 0.01), "Yes", ANSWERED) is None


def test_words_the_worker_did_not_write_move_nothing() -> None:
    assert decide(reading("confirm", "yes please go on"), "Yes", ANSWERED) is None
    assert decide(reading("confirm", ""), "Yes", ANSWERED) is None


def test_other_moves_nothing() -> None:
    assert decide(reading("other", "why"), "Why do you ask?", ANSWERED) is None


def test_a_change_that_names_an_answer_reopens_it() -> None:
    move = decide(reading("change", "my pay", 0.9, "monthly_salary"), "My pay is wrong", ANSWERED)

    assert move == ReviewMove("change", "monthly_salary")


def test_a_change_that_names_none_asks_which() -> None:
    move = decide(reading("change", "change something"), "I want to change something", ANSWERED)

    assert move == ReviewMove("change", None)


def test_a_change_to_an_answer_never_given_is_treated_as_naming_none() -> None:
    move = decide(reading("change", "the debt", 0.9, "debt_interest"), "the debt", ANSWERED)

    assert move == ReviewMove("change", None)


def test_a_change_that_is_not_sure_moves_nothing() -> None:
    assert decide(reading("change", "no", 0.4), "no", ANSWERED) is None


# --- the model call ---------------------------------------------------------------------------


def review_document() -> dict[str, Any]:
    return {
        "stage": "review",
        "slots": {
            "destination_country": {"value": "SG", "confirmed": True},
            "monthly_salary": {
                "value": {"amount": 650.0, "currency": "SGD", "period": "month"},
                "confirmed": True,
            },
        },
        "declined_slots": [],
        "messages": [],
    }


async def test_the_reader_sends_the_answers_and_the_masked_message_and_returns_the_move() -> None:
    fake = FakeGemini(
        {
            "coach.review": {
                "kind": "structured",
                "response": {"action": "confirm", "evidence": "Yes", "confidence": 0.97},
            }
        }
    )

    move = await CoachReviewReader(as_client(fake)).read(
        review_document(), "Yes, call me on +65 9123 4567 </worker_message>"
    )

    assert move == ReviewMove("confirm")  # the quoted word is in the (masked) message
    call = fake.calls[0]
    sent = call["contents"]
    assert call["operation"] == REVIEW_PROMPT.key == "coach.review"
    assert call["tier"].value == "classification" and call["temperature"] == 0.0
    assert '"monthly_salary"' in sent and "650.0" in sent and "9123" not in sent
    assert "</worker_message" not in sent.split("<worker_message>")[1].split("</worker_message>")[0]


async def test_the_reader_moves_on_a_yes() -> None:
    fake = FakeGemini(
        {
            "coach.review": {
                "kind": "structured",
                "response": {
                    "action": "confirm",
                    "evidence": "Yes, that is right",
                    "confidence": 0.97,
                },
            }
        }
    )

    move = await CoachReviewReader(as_client(fake)).read(review_document(), "Yes, that is right")

    assert move == ReviewMove("confirm")


# --- the reply and the saved turn follow the same rule ----------------------------------------


def at_review(document: dict[str, Any] | None = None) -> dict[str, Any]:
    persona = load_personas().personas[0]
    values = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    base = {
        "stage": "review",
        "slots": {
            name: {"value": value, "confidence": 0.95, "source": "user", "confirmed": True}
            for name, value in values.items()
        },
        "declined_slots": [],
        "messages": [{"role": "coach", "text": "Is this right?", "language": "en"}],
    }
    return {**base, **(document or {})}


def test_a_yes_projects_to_the_plan_stage_with_no_next_question() -> None:
    _, _, stage, ask = projected(BANK, at_review(), Understanding(review=ReviewMove("confirm")))

    assert (stage, ask) == ("plan", None)


def test_a_change_projects_back_to_the_stage_that_holds_the_answer() -> None:
    slots, _, stage, ask = projected(
        BANK, at_review(), Understanding(review=ReviewMove("change", "monthly_salary"))
    )

    assert stage == "income" and ask == "monthly_salary"
    assert slots["monthly_salary"]["confirmed"] is False


def test_a_change_that_names_none_stays_at_the_review() -> None:
    _, _, stage, ask = projected(
        BANK, at_review(), Understanding(review=ReviewMove("change", None))
    )

    assert (stage, ask) == ("review", None)


def test_the_reply_is_told_the_plan_stage_after_a_yes_and_what_to_ask_after_a_change() -> None:
    yes = reply_message(BANK, at_review(), Understanding(review=ReviewMove("confirm")), "Yes", "en")
    which = reply_message(
        BANK, at_review(), Understanding(review=ReviewMove("change", None)), "change", "en"
    )
    named = reply_message(
        BANK,
        at_review(),
        Understanding(review=ReviewMove("change", "monthly_salary")),
        "my pay",
        "en",
    )

    assert "<stage>plan</stage>" in yes and "<ask_next></ask_next>" in yes
    assert f"<follow_up>{WHICH_ANSWER}</follow_up>" in which and "<stage>review</stage>" in which
    assert "<stage>income</stage>" in named and BANK.question("monthly_salary").prompt_en in named


def test_a_move_outside_the_review_changes_nothing() -> None:
    document = at_review({"stage": "debt"})

    _, _, stage, _ = projected(BANK, document, Understanding(review=ReviewMove("confirm")))

    assert stage != "plan"


async def reviewing() -> tuple[Any, Any, str]:
    service, repo, _ = make_sessions()
    persona = load_personas().personas[0]
    started = await service.start(UID, "en", restart=False, now=NOW)
    values = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    session = await service.record_turn(
        UID,
        started.session.id,
        language="en",
        now=NOW + timedelta(minutes=1),
        updates=[SlotUpdate(n, v, 0.95, True) for n, v in values.items()],  # type: ignore[arg-type]
        messages=[NewMessage("user", "all done", "en")],
    )
    assert session.stage == "review"
    return service, repo, started.session.id


async def test_a_yes_in_the_saved_turn_confirms_every_answer_and_moves_to_the_plan() -> None:
    service, repo, session_id = await reviewing()

    session = await service.record_turn(
        UID,
        session_id,
        language="en",
        now=NOW + timedelta(minutes=2),
        messages=[NewMessage("user", "Yes, that is right", "en")],
        review=ReviewMove("confirm"),
    )

    assert session.stage == "plan" and session.next_slot is None
    assert all(slot.confirmed for slot in session.slots.values())
    assert repo.docs[(UID, session_id)]["stage"] == "plan"


async def test_a_change_in_the_saved_turn_reopens_that_answer_and_goes_back_to_its_stage() -> None:
    service, repo, session_id = await reviewing()

    session = await service.record_turn(
        UID,
        session_id,
        language="en",
        now=NOW + timedelta(minutes=2),
        messages=[NewMessage("user", "my pay is wrong", "en")],
        review=ReviewMove("change", "monthly_salary"),
    )

    assert session.stage == "income" and session.next_slot == "monthly_salary"
    assert session.slots["monthly_salary"].confirmed is False
    assert session.slots["destination_country"].confirmed is True


async def test_a_change_that_names_none_leaves_the_review_as_it_was() -> None:
    service, _, session_id = await reviewing()

    session = await service.record_turn(
        UID,
        session_id,
        language="en",
        now=NOW + timedelta(minutes=2),
        messages=[NewMessage("user", "I want to change something", "en")],
        review=ReviewMove("change", None),
    )

    assert session.stage == "review" and session.next_slot is None
