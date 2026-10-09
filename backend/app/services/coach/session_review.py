"""What the worker's reply at the review does to the session (NF-FC-020).

The same moves as `confirm_review` and `request_correction` (NF-FC-008), applied inside the turn's
own write so a turn is saved whole or not at all.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.coach_questions import QuestionBank
from app.schemas.coach_session import Stage
from app.services.coach.review_reader import ReviewMove
from app.services.coach.session_machine import stage_of, transition


def apply_review_move(
    bank: QuestionBank,
    slots: dict[str, dict[str, Any]],
    declined: list[str],
    move: ReviewMove,
    now: datetime,
) -> tuple[dict[str, dict[str, Any]], list[str], Stage]:
    """The slots, declined slots and stage after the move.

    A yes confirms every answer and goes to `plan`. A change that names an answer reopens it
    (unconfirmed) and goes back to the stage that holds it. A change that names none moves
    nothing: the coach asks which.
    """
    if move.kind == "confirm":
        confirmed = {
            name: {**record, "confirmed": True, "updated_at": now} for name, record in slots.items()
        }
        return confirmed, declined, transition("review", "plan")
    slot = move.slot
    if slot is None or slot not in slots:
        return slots, declined, "review"
    reopened = {**slots, slot: {**slots[slot], "confirmed": False}}
    return (
        reopened,
        [name for name in declined if name != slot],
        transition("review", stage_of(bank, slot)),
    )
