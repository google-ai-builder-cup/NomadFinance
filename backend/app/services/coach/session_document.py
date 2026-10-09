"""The stored Coach session and the contract's view of it (NF-FC-008, `coach.md`)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel

from app.config import get_settings
from app.integrations.gemini import ModelTier, model_for
from app.schemas.coach_plan import CoachScore
from app.schemas.coach_profile import CoachProfile
from app.schemas.coach_questions import QuestionBank
from app.schemas.coach_session import (
    SCORED_STAGES,
    CoachKnown,
    CoachKnownItem,
    CoachMessage,
    CoachSession,
    CoachSlot,
)
from app.schemas.contract import ReportLanguage
from app.services.coach.known_details import OFFER_ORDER
from app.services.coach.session_machine import next_slot, settle

SCHEMA_VERSION = 1
# A session with no turn for this long is closed when it is next read, so a new one can start.
IDLE_AFTER = timedelta(days=14)
# How long a session stays after its last turn (TTL field `expires_at`); the plan outlives it.
KEEP_FOR = timedelta(days=30)

# Computes the preparedness score of the answers (`coach_scorer.CoachScorer`, NF-FC-011). It reads
# stored costs, law and rates, so it is awaited. None means "cannot be worked out now": the
# session then shows `score: null`, which the contract allows.
Scorer = Callable[[CoachProfile], Awaitable[CoachScore | None]]


def new_document(
    language: ReportLanguage,
    now: datetime,
    bank: QuestionBank,
    prefill: dict[str, Any] | None = None,
    known: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A session that has just been created: stage `intro`, nothing answered, no messages.

    `prefill` is the salary offered from the worker's contract (`prefill.py`, NF-FC-015); `known`
    is everything else the Coach could already fill in (`known_details.py`, NF-FC-023).
    """
    settings = get_settings()
    document: dict[str, Any] = {
        "status": "active",
        "stage": "intro",
        "language": language,
        "slots": {},
        # Optional slots the worker chose not to answer, so "not sure" differs from "not asked".
        "declined_slots": [],
        "messages": [],
        "turn_count": 0,
        "revision": 1,
        "last_active": now,
        "expires_at": now + KEEP_FOR,
        # Filled with the real values by the turn endpoint (NF-FC-009, -010) on every turn.
        "models": {
            "extraction": model_for(ModelTier.CLASSIFICATION, settings),
            "reply": model_for(ModelTier.REASONING, settings),
        },
        "prompt_versions": {},
        "question_bank_version": bank.version,
        "created_at": now,
        "schema_version": SCHEMA_VERSION,
    }
    if prefill is not None:
        document["prefill"] = prefill
    if known is not None:
        document["known"] = known
    return document


def known_view(document: dict[str, Any]) -> CoachKnown | None:
    """What is offered and waiting for the worker, in the interview's order; None once they have
    answered (or when nothing was offered). Firestore does not keep a map's order, so the order is
    set here."""
    known = document.get("known")
    if not known or known.get("state") != "offered":
        return None
    items = known["items"]
    return CoachKnown(
        items=[CoachKnownItem(slot=slot, **items[slot]) for slot in OFFER_ORDER if slot in items]
    )


def jsonable(value: object) -> object:
    """A slot value as stored: models become plain maps, plain values stay."""
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def idle(document: dict[str, Any], now: datetime) -> bool:
    last = document.get("last_active")
    return not isinstance(last, datetime) or now - last >= IDLE_AFTER


def expired(document: dict[str, Any], now: datetime) -> bool:
    """Past `expires_at` counts as gone: the TTL policy deletes within a day or so, not at once."""
    until = document.get("expires_at")
    return not isinstance(until, datetime) or until <= now


def scorable_profile(document: dict[str, Any], bank: QuestionBank) -> CoachProfile | None:
    """The answers as a profile when the session has reached the stages that show a score."""
    slots: dict[str, dict[str, Any]] = document["slots"]
    stage = settle(bank, document["stage"], slots, document.get("declined_slots", []))
    if stage not in SCORED_STAGES:
        return None
    return CoachProfile.model_validate({n: r["value"] for n, r in slots.items()})


def to_session(
    session_id: str,
    document: dict[str, Any],
    bank: QuestionBank,
    score: CoachScore | None = None,
) -> CoachSession:
    """The contract's view of a stored session (`GET /coach/sessions/{id}`).

    The stage is settled again from the answers, so a session stored under an older question
    bank still shows a stage and a next question that agree.
    """
    slots: dict[str, dict[str, Any]] = document["slots"]
    declined = document.get("declined_slots", [])
    stage = settle(bank, document["stage"], slots, declined)
    return CoachSession(
        id=session_id,
        status=document["status"],
        stage=stage,
        language=document["language"],
        slots={
            name: CoachSlot(value=r["value"], confirmed=r["confirmed"], source=r["source"])
            for name, r in slots.items()
        },
        messages=[CoachMessage.model_validate(m) for m in document["messages"]],
        next_slot=next_slot(bank, stage, slots, declined),
        turn_count=document["turn_count"],
        score=score,
        plan_id=document.get("plan_id"),
        known=known_view(document),
        created_at=document["created_at"],
        last_active=document["last_active"],
    )
