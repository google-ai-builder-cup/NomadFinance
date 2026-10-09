"""The Coach session state machine (NF-FC-008): every move of the diagram, allowed or refused."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import product
from typing import Any

import pytest

from app.schemas.coach_session import SessionStatus, Stage
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_machine import (
    ALLOWED_MOVES,
    ALLOWED_STATUS_MOVES,
    QUESTION_STAGES,
    STAGES,
    IllegalTransitionError,
    next_slot,
    pending_questions,
    settle,
    stage_of,
    status_transition,
    transition,
)

BANK = load_question_bank()
AT = datetime(2026, 10, 20, tzinfo=UTC)
STATUSES: tuple[SessionStatus, ...] = ("active", "completed", "abandoned")

# The diagram of design 4.3, written out again here so a slip in the code cannot hide.
EDGES = {
    ("intro", "income"),
    ("income", "obligations"),
    ("obligations", "debt"),
    ("debt", "savings"),
    ("savings", "review"),
    ("review", "plan"),
    ("review", "income"),
    ("review", "obligations"),
    ("review", "debt"),
    ("review", "savings"),
}

# Values that satisfy each slot, as the stored records would hold them.
VALUES: dict[str, Any] = {
    "destination_country": "AU",
    "job_type": "care_worker",
    "departure_date": "2026-12-01",
    "monthly_salary": {"amount": 4200, "currency": "AUD", "period": "month"},
    "dependents": 2,
    "remittance_target": {"amount": 900, "currency": "AUD", "period": "month"},
    "recruitment_fee_paid": {"amount": 0, "currency": "INR", "period": "once"},
    "debt_outstanding": {"amount": 0, "currency": "INR", "period": "once"},
    "debt_interest": {"rate_percent": 2, "period": "month"},
    "savings": {"amount": 1000, "currency": "INR", "period": "once"},
    "bank_or_wallet": "bank_account",
}
A_DEBT = {"amount": 5000, "currency": "INR", "period": "once"}


def records(*names: str, confirmed: bool = True, **override: Any) -> dict[str, dict[str, Any]]:
    values = {**VALUES, **override}
    return {
        name: {"value": values[name], "confirmed": confirmed, "confidence": 1.0, "source": "user"}
        for name in names
    }


@pytest.mark.parametrize(("current", "target"), list(product(STAGES, STAGES)))
def test_every_pair_of_stages_is_allowed_exactly_when_the_diagram_has_the_edge(
    current: Stage, target: Stage
) -> None:
    if (current, target) in EDGES:
        assert transition(current, target) == target
    else:
        with pytest.raises(IllegalTransitionError):
            transition(current, target)


def test_the_code_and_the_written_diagram_have_the_same_edges() -> None:
    assert {(a, b) for a, targets in ALLOWED_MOVES.items() for b in targets} == EDGES


def test_a_session_cannot_stay_where_it_is_or_leave_the_plan_stage() -> None:
    for stage in STAGES:
        with pytest.raises(IllegalTransitionError):
            transition(stage, stage)
    assert ALLOWED_MOVES["plan"] == frozenset()


@pytest.mark.parametrize(("current", "target"), list(product(STATUSES, STATUSES)))
def test_an_interview_ends_once_and_never_reopens(
    current: SessionStatus, target: SessionStatus
) -> None:
    if current == "active" and target in {"completed", "abandoned"}:
        assert status_transition(current, target) == target
    else:
        with pytest.raises(IllegalTransitionError):
            status_transition(current, target)
    assert ALLOWED_STATUS_MOVES["completed"] == ALLOWED_STATUS_MOVES["abandoned"] == frozenset()


def test_the_five_question_stages_come_first_and_review_and_plan_hold_no_question() -> None:
    assert STAGES == ("intro", "income", "obligations", "debt", "savings", "review", "plan")
    assert QUESTION_STAGES == STAGES[:5]
    assert {q.stage for q in BANK.questions} == set(QUESTION_STAGES)


def test_a_new_session_waits_at_intro_for_the_destination() -> None:
    assert settle(BANK, "intro", {}) == "intro"
    assert next_slot(BANK, "intro", {}) == "destination_country"


def test_a_stage_is_left_only_when_its_required_answers_are_in_and_confirmed() -> None:
    intro = ("destination_country", "job_type", "departure_date")
    assert settle(BANK, "intro", records(*intro[:2])) == "intro"
    assert next_slot(BANK, "intro", records(*intro[:2])) == "departure_date"
    assert settle(BANK, "intro", records(*intro)) == "income"
    unsure = records(*intro, confirmed=False)
    assert settle(BANK, "intro", unsure) == "intro"
    assert next_slot(BANK, "intro", unsure) == "destination_country"


def test_the_one_optional_question_is_done_when_the_worker_declines_it() -> None:
    answered = records("destination_country", "job_type")

    assert settle(BANK, "intro", answered) == "intro"
    assert settle(BANK, "intro", answered, declined=["departure_date"]) == "income"
    assert next_slot(BANK, "income", answered, declined=["departure_date"]) == "monthly_salary"


def test_a_worker_who_volunteers_later_facts_keeps_them_and_the_stage_is_the_earliest_gap() -> None:
    volunteered = records("destination_country", "job_type", "monthly_salary", "dependents")

    assert settle(BANK, "intro", volunteered) == "intro"
    assert next_slot(BANK, "intro", volunteered) == "departure_date"
    with_date = {**volunteered, **records("departure_date")}
    assert settle(BANK, "intro", with_date) == "obligations"
    assert next_slot(BANK, "obligations", with_date) == "remittance_target"


def test_the_interest_question_is_skipped_when_the_debt_is_zero() -> None:
    debt_stage = ("recruitment_fee_paid", "debt_outstanding")
    no_debt = records(*debt_stage)
    with_debt = records(*debt_stage, debt_outstanding=A_DEBT)

    assert [q.slot for q in pending_questions(BANK, "debt", no_debt)] == []
    assert settle(BANK, "debt", no_debt) == "savings"
    assert next_slot(BANK, "debt", with_debt) == "debt_interest"
    assert settle(BANK, "debt", with_debt) == "debt"


def test_the_whole_interview_walks_forward_to_review_and_stops_there() -> None:
    everything = records(*VALUES)

    assert settle(BANK, "intro", everything) == "review"
    assert settle(BANK, "review", everything) == "review"
    assert settle(BANK, "plan", everything) == "plan"
    assert next_slot(BANK, "review", everything) is None
    assert next_slot(BANK, "plan", everything) is None


def test_a_correction_goes_back_to_the_stage_that_holds_the_answer() -> None:
    assert {slot: stage_of(BANK, slot) for slot in VALUES} == {
        "destination_country": "intro",
        "job_type": "intro",
        "departure_date": "intro",
        "monthly_salary": "income",
        "dependents": "obligations",
        "remittance_target": "obligations",
        "recruitment_fee_paid": "debt",
        "debt_outstanding": "debt",
        "debt_interest": "debt",
        "savings": "savings",
        "bank_or_wallet": "savings",
    }
    for slot in ("monthly_salary", "dependents", "recruitment_fee_paid", "savings"):
        assert transition("review", stage_of(BANK, slot)) == stage_of(BANK, slot)
