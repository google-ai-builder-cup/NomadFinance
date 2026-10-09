"""What the Coach reply is asked to say, and the history it sees (NF-FC-009).

The reply model is told which question comes next and which figures it may repeat; it is never
asked to decide where the interview stands. The stage and the next question come from the state
machine, so the model cannot skip a question or invent one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.integrations.gemini import ChatTurn
from app.prompts.loader import load_prompt
from app.schemas.coach_profile import parse_slot_value
from app.schemas.coach_questions import QuestionBank
from app.schemas.contract import ReportLanguage
from app.services.coach.guard_rules import fence, visible_to_model
from app.services.coach.prefill import PREFILL_SLOT, apply_prefill, prefill_question
from app.services.coach.session_document import jsonable
from app.services.coach.session_machine import next_slot, settle, stage_of
from app.services.coach.turn_types import Understanding

REPLY_PROMPT = load_prompt("coach", "reply", 2)
SUMMARISE_PROMPT = load_prompt("coach", "summarise", 1)

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "tl": "Tagalog (Filipino)",
    "id": "Indonesian",
    "ne": "Nepali",
    "bn": "Bengali",
}
# What the coach asks when the worker wants to change something and does not say what (the review).
WHICH_ANSWER = (
    "Ask which answer they want to change, and say they can name it, for example the pay or the "
    "money they send home."
)
# Shown to the model in place of a message the worker did not type (the coach speaks first).
NO_MESSAGE = "(none)"


def history_from(messages: Sequence[dict[str, Any]]) -> list[ChatTurn]:
    """The stored transcript as chat turns: the worker is `user`, the coach is `model`. A worker
    message that gave the coach orders is replaced, so it cannot keep working from the history."""
    return [
        ChatTurn(
            "user" if message["role"] == "user" else "model",
            visible_to_model(message["role"], message["text"]),
        )
        for message in messages
    ]


def projected(
    bank: QuestionBank,
    document: dict[str, Any],
    understanding: Understanding,
    *,
    worker_spoke: bool = True,
) -> tuple[dict[str, dict[str, Any]], list[str], str, str | None]:
    """The answers, declined slots, stage and next slot as they will stand after this turn,
    including the salary offered from the worker's contract (`prefill.apply_prefill`, the same
    rule the stored turn follows)."""
    slots = dict(document["slots"])
    for update in understanding.updates:
        value = parse_slot_value(update.slot, update.value)
        slots[update.slot] = {
            "value": jsonable(value),
            "confirmed": update.confirmed,
            "source": update.source,
        }
    declined = sorted({*document.get("declined_slots", []), *understanding.declined} - set(slots))
    stage = settle(bank, document["stage"], slots, declined)
    slots, _ = apply_prefill(
        document, slots, stage, now=datetime.now(UTC), turn=0, worker_spoke=worker_spoke
    )
    stage = settle(bank, document["stage"], slots, declined)
    move = understanding.review
    if document["stage"] == "review" and move is not None:
        # The worker's reply at the review (the same rule `record_turn` follows): a yes goes on to
        # the plan; naming an answer to change goes back to the question that holds it.
        if move.kind == "confirm":
            stage = "plan"
        elif move.slot is not None and move.slot in slots:
            slots = {**slots, move.slot: {**slots[move.slot], "confirmed": False}}
            stage = stage_of(bank, move.slot)
    return slots, declined, stage, next_slot(bank, stage, slots, declined)


def question_to_ask(
    bank: QuestionBank, understanding: Understanding, ask_slot: str | None
) -> tuple[str, str]:
    """`(ask_next, follow_up)`: the bank's own wording, in English; the model puts it in words."""
    review = understanding.review
    if review is not None and review.kind == "change" and review.slot is None:
        return "", WHICH_ANSWER
    if understanding.clarify is not None:
        clarify = understanding.clarify
        return "", bank.follow_up(clarify.slot, clarify.trigger).prompt_en
    if ask_slot is None:
        return "", ""
    return bank.question(ask_slot).prompt_en, ""


def reply_message(
    bank: QuestionBank,
    document: dict[str, Any],
    understanding: Understanding,
    text: str | None,
    language: ReportLanguage,
) -> str:
    """The user message of the reply call, filled from `coach/reply.v2`."""
    slots, _, stage, ask_slot = projected(bank, document, understanding, worker_spoke=bool(text))
    ask_next, follow_up = question_to_ask(bank, understanding, ask_slot)
    offer = document.get("prefill")
    record = slots.get(PREFILL_SLOT)
    if (  # the salary from the contract is asked about, in the offer's own words
        offer
        and ask_slot == PREFILL_SLOT
        and not follow_up
        and record is not None
        and record.get("source") == "contract_prefill"
        and not record.get("confirmed")
    ):
        ask_next = prefill_question(offer)
    understood = {u.slot: parse_slot_value(u.slot, u.value) for u in understanding.updates}
    return REPLY_PROMPT.render_user(
        language=LANGUAGE_NAMES[language],
        stage=stage,
        first_message="yes" if not document["messages"] else "no",
        ask_next=ask_next,
        follow_up=follow_up,
        understood_json=_json({k: jsonable(v) for k, v in understood.items()}),
        slots_json=_json({name: record["value"] for name, record in slots.items()}),
        summary=fence(document.get("summary") or "(none)"),
        worker_message=fence(text) if text else NO_MESSAGE,
    )


def summary_message(earlier: str | None, turns: Sequence[ChatTurn]) -> str:
    """The user message that asks for a summary of `turns`, after any `earlier` summary."""
    lines = "\n".join(
        f"{'Worker' if turn.role == 'user' else 'Coach'}: {turn.text}" for turn in turns
    )
    return SUMMARISE_PROMPT.render_user(earlier_summary=earlier or "(none)", turns=lines)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
