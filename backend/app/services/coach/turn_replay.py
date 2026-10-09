"""Which turn runs, which is replayed, which is refused (NF-FC-009, conventions section 5).

The rules live here, away from the streaming, because they are the part a retry depends on:
the same key and body after a finished turn gives the stored events again, nothing runs twice.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from app.core.sse import sse_event
from app.schemas.coach_questions import QuestionBank
from app.schemas.coach_session import CoachDoneEvent, CoachTurnRequest
from app.services.coach.session_document import to_session
from app.services.coach.turn_types import (
    KeyReusedError,
    RequestInProgressError,
    TurnInProgressError,
)

# A turn still "running" after this long is treated as failed, so a crashed server never locks a
# session; a key is forgotten after a day (docs/api/v2-coach.md, "How the key is kept").
STALE_AFTER = timedelta(seconds=90)
KEY_MEMORY = timedelta(hours=24)


def body_hash(body: CoachTurnRequest) -> str:
    """SHA-256 of the request body as JSON with sorted keys (conventions, section 5)."""
    canonical = json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def replay_frames(
    session_id: str,
    document: dict[str, Any],
    key: str,
    digest: str,
    now: datetime,
    bank: QuestionBank,
) -> tuple[str, ...] | None:
    """The stored events of the turn this key finished, or `None` when a new turn should run.

    Raises:
        KeyReusedError: The key was used for a different body.
        RequestInProgressError: The turn with this key is still running.
        TurnInProgressError: A turn with another key is still running.
    """
    last = document.get("last_turn")
    if not last:
        return None
    age = now - last["started_at"]
    running = last["state"] == "running" and age < STALE_AFTER
    if last["key"] != key:
        if running:
            raise TurnInProgressError(session_id)
        return None
    if age >= KEY_MEMORY:
        return None
    if last["body_hash"] != digest:
        raise KeyReusedError(key)
    if running:
        raise RequestInProgressError(key)
    return _frames_of(session_id, document, last, bank) if last["state"] == "done" else None


def _frames_of(
    session_id: str, document: dict[str, Any], last: dict[str, Any], bank: QuestionBank
) -> tuple[str, ...] | None:
    """The turn rebuilt from the transcript and the answers it stored. The text may arrive in
    fewer `token` events than it was streamed in."""
    message = next((m for m in document["messages"] if m["id"] == last.get("message_id")), None)
    if message is None:
        return None
    view = to_session(session_id, document, bank)
    frames = [
        sse_event(
            "slot_update",
            {
                "slot": name,
                "value": document["slots"][name]["value"],
                "confirmed": document["slots"][name]["confirmed"],
            },
        )
        for name in last.get("slots", [])
        if name in document["slots"]
    ]
    frames.append(sse_event("token", {"text": message["text"]}))
    done = CoachDoneEvent(
        message_id=message["id"],
        stage=view.stage,
        next_slot=view.next_slot,
        turn_count=view.turn_count,
    )
    frames.append(sse_event("done", done.model_dump(mode="json")))
    return tuple(frames)
