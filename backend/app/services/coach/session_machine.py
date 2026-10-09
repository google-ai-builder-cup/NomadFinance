"""The Coach session's state machine (NF-FC-008, design 4.3): pure rules, no storage.

A session is at one stage of `intro → income → obligations → debt → savings → review → plan`.
Stages are left only through the moves of the diagram; every move goes through `transition`, so
a path that skips one cannot be written by accident. The stage is not a counter: it is where the
answers stand. A worker who volunteers a later fact keeps it, and the stage is the earliest one
that is still incomplete (`settle`).

A stage is complete when every question it applies has a **confirmed** answer. A question
the bank does not apply (no interest on a debt of 0) is not asked. The one optional question
(the departure date) is complete once it was answered or the worker declined to say; that is
how "not sure" is told apart from "not asked yet" (D-171).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, get_args

from app.schemas.coach_profile import CoachProfile, SlotName
from app.schemas.coach_questions import Question, QuestionBank
from app.schemas.coach_session import SessionStatus, Stage
from app.services.coach.question_bank import is_applicable

STAGES: tuple[Stage, ...] = get_args(Stage)
QUESTION_STAGES: tuple[Stage, ...] = STAGES[:5]

# The diagram of design 4.3. After `review` the worker may confirm (`plan`) or correct, which
# goes back to the stage that holds the answer.
ALLOWED_MOVES: dict[Stage, frozenset[Stage]] = {
    "intro": frozenset({"income"}),
    "income": frozenset({"obligations"}),
    "obligations": frozenset({"debt"}),
    "debt": frozenset({"savings"}),
    "savings": frozenset({"review"}),
    "review": frozenset({"plan", "income", "obligations", "debt", "savings"}),
    "plan": frozenset(),
}
# An interview ends one way or the other; a finished session never reopens.
ALLOWED_STATUS_MOVES: dict[SessionStatus, frozenset[SessionStatus]] = {
    "active": frozenset({"completed", "abandoned"}),
    "completed": frozenset(),
    "abandoned": frozenset(),
}


class IllegalTransitionError(ValueError):
    """A move the state machine does not allow. Nothing is written when it is raised."""


def transition(current: Stage, target: Stage) -> Stage:
    """`target` when the diagram allows the move from `current`.

    Raises:
        IllegalTransitionError: The move is not in the diagram (including staying where you are).
    """
    if target not in ALLOWED_MOVES[current]:
        raise IllegalTransitionError(f"A session cannot go from {current} to {target}.")
    return target


def status_transition(current: SessionStatus, target: SessionStatus) -> SessionStatus:
    """`target` when an interview in `current` may end that way.

    Raises:
        IllegalTransitionError: The session is already completed or abandoned.
    """
    if target not in ALLOWED_STATUS_MOVES[current]:
        raise IllegalTransitionError(f"A {current} session cannot become {target}.")
    return target


def _profile(slots: Mapping[str, Any]) -> CoachProfile:
    """The answers as a profile, for the bank's skip rules. A stored value is always valid."""
    return CoachProfile.model_validate(dict(slots))


def _unfinished(question: Question, slots: Mapping[str, Mapping[str, Any]], declined: bool) -> bool:
    record = slots.get(question.slot)
    if record is None:
        return not declined
    return not record["confirmed"]


def pending_questions(
    bank: QuestionBank,
    stage: Stage,
    slots: Mapping[str, Mapping[str, Any]],
    declined: Collection[str] = (),
) -> list[Question]:
    """The questions of `stage` still to ask, in the bank's order.

    `slots` are the stored records (`{"value", "confirmed", ...}`), `declined` the optional
    slots the worker chose not to answer.
    """
    profile = _profile({name: record["value"] for name, record in slots.items()})
    return [
        question
        for question in bank.questions
        if question.stage == stage
        and is_applicable(question, profile)
        and _unfinished(question, slots, question.slot in declined and not question.required)
    ]


def settle(
    bank: QuestionBank,
    current: Stage,
    slots: Mapping[str, Mapping[str, Any]],
    declined: Collection[str] = (),
) -> Stage:
    """Where the session stands now: the earliest incomplete stage, or `review` when all are done.

    From `review` and `plan` the answers do not move the stage (confirming and correcting are
    explicit moves). Each step forward is checked against the diagram.
    """
    stage = current
    while stage in QUESTION_STAGES and not pending_questions(bank, stage, slots, declined):
        stage = transition(stage, STAGES[STAGES.index(stage) + 1])
    return stage


def next_slot(
    bank: QuestionBank,
    stage: Stage,
    slots: Mapping[str, Mapping[str, Any]],
    declined: Collection[str] = (),
) -> SlotName | None:
    """The slot to ask for next; `None` exactly in `review` and `plan` (the contract)."""
    if stage not in QUESTION_STAGES:
        return None
    pending = pending_questions(bank, stage, slots, declined)
    return pending[0].slot if pending else None


def stage_of(bank: QuestionBank, slot: str) -> Stage:
    """The stage whose questions include `slot` (where a correction goes back to)."""
    return bank.question(slot).stage
