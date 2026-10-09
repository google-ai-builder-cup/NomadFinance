"""One Coach turn: decide whether to run it, stream the reply, save it (NF-FC-009).

`start` does everything that can still become an ordinary HTTP error (a wrong state, a busy
session, a Gemini failure before the first piece) and returns a turn ready to stream. `frames`
then writes the Server-Sent Events. Nothing is saved until the reply is complete, so a stream
that breaks or is closed leaves the session as it was, with the turn marked failed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from google.api_core.exceptions import GoogleAPIError

from app.config import get_settings
from app.core.errors import error_parts
from app.core.sse import sse_event
from app.integrations.gemini import (
    GeminiClient,
    GeminiError,
    GeminiResponseError,
    GeminiStream,
    ModelTier,
    model_for,
)
from app.schemas.coach_profile import parse_slot_value
from app.schemas.coach_session import (
    MAX_TRANSCRIPT_MESSAGES,
    CoachDoneEvent,
    CoachTurnRequest,
)
from app.schemas.errors import ErrorEnvelope
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import jsonable
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import (
    NewMessage,
    SessionConflictError,
    SessionFullError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from app.services.coach.turn_prompt import (
    REPLY_PROMPT,
    SUMMARISE_PROMPT,
    history_from,
    reply_message,
    summary_message,
)
from app.services.coach.turn_replay import body_hash, replay_frames
from app.services.coach.turn_types import (
    NoExtraction,
    SlotExtractor,
    TextRequiredError,
    TurnInProgressError,
    Understanding,
)

logger = logging.getLogger(__name__)

REPLY_OPERATION = "coach.reply"
SUMMARY_OPERATION = "coach.summarise"
REPLY_TEMPERATURE = 0.3


@dataclass
class LiveTurn:
    """A turn that has started: its reply stream is open and its first piece is in."""

    uid: str
    session_id: str
    key: str
    body_hash: str
    body: CoachTurnRequest
    understanding: Understanding
    document: dict[str, Any]
    stream: GeminiStream
    started_at: datetime


@dataclass(frozen=True)
class ReplayTurn:
    """A finished turn asked for again with the same key: its events, from storage."""

    frames: tuple[str, ...]


class CoachTurns:
    def __init__(
        self,
        sessions: CoachSessions,
        gemini: GeminiClient,
        *,
        extractor: SlotExtractor | None = None,
    ) -> None:
        self._sessions = sessions
        self._gemini = gemini
        self._extractor = extractor or NoExtraction()
        self._bank = load_question_bank()
        self._settings = get_settings()

    async def start(
        self, uid: str, session_id: str, body: CoachTurnRequest, key: str, now: datetime
    ) -> LiveTurn | ReplayTurn:
        """Begin a turn, or replay the one this key already finished.

        Raises:
            SessionNotFoundError, SessionNotActiveError, SessionFullError: The session cannot
                take a turn.
            TextRequiredError: `text` was left out where the coach may not speak first.
            KeyReusedError, RequestInProgressError, TurnInProgressError: The key or the session
                is in a state that refuses a new run (conventions, section 5).
            GeminiError: Understanding or opening the reply failed before any piece arrived.
        """
        document = await self._sessions.document(uid, session_id, now)
        if document["status"] != "active":
            raise SessionNotActiveError(document["status"])
        digest = body_hash(body)
        replayed = replay_frames(session_id, document, key, digest, now, self._bank)
        if replayed is not None:
            return ReplayTurn(replayed)
        self._check_may_run(session_id, document, body)

        started = {"key": key, "body_hash": digest, "state": "running", "started_at": now}
        started["turn"] = document["turn_count"]
        try:
            await self._sessions.set_last_turn(uid, session_id, started, now, read=document)
        except SessionConflictError as exc:
            raise TurnInProgressError(session_id) from exc
        turn_document = {**document, "last_turn": started}
        try:
            understanding = Understanding()
            if body.text:
                understanding = await self._extractor.extract(
                    turn_document, body.text, body.language
                )
            stream = await self._open_reply(turn_document, understanding, body)
        except BaseException:
            await self._mark(uid, session_id, started, "failed")
            raise
        return LiveTurn(
            uid, session_id, key, digest, body, understanding, turn_document, stream, now
        )

    async def frames(self, turn: LiveTurn, request_id: str) -> AsyncIterator[str]:
        """The events of a live turn. Ends with `done` or `error`; saves only on `done`."""
        finished = False
        try:
            for update in turn.understanding.updates:
                yield sse_event(
                    "slot_update",
                    {
                        "slot": update.slot,
                        "value": jsonable(parse_slot_value(update.slot, update.value)),
                        "confirmed": update.confirmed,
                    },
                )
            async with turn.stream as stream:
                async for piece in stream:
                    yield sse_event("token", {"text": piece})
            reply = turn.stream.text.strip()
            if not reply:
                raise GeminiResponseError("the reply was empty")
            done = await self._save(turn, reply)
            finished = True
            yield sse_event("done", done.model_dump(mode="json"))
        except (
            Exception
        ) as exc:  # noqa: BLE001  the stream has started: tell the client, not the log
            yield sse_event("error", _envelope(exc, request_id))
            return
        finally:
            if not finished:
                await self._mark(turn.uid, turn.session_id, turn.document["last_turn"], "failed")
        await self._refresh_summary(turn)

    @staticmethod
    def _check_may_run(session_id: str, document: dict[str, Any], body: CoachTurnRequest) -> None:
        if body.text is None and document["messages"] and body.language == document["language"]:
            raise TextRequiredError("text")
        added = 2 if body.text else 1
        if len(document["messages"]) + added > MAX_TRANSCRIPT_MESSAGES:
            raise SessionFullError(session_id)

    async def _open_reply(
        self, document: dict[str, Any], understanding: Understanding, body: CoachTurnRequest
    ) -> GeminiStream:
        return await self._gemini.stream(
            operation=REPLY_OPERATION,
            tier=ModelTier(self._settings.gemini_coach_reply_tier),
            message=reply_message(self._bank, document, understanding, body.text, body.language),
            history=history_from(document["messages"]),
            system_instruction=REPLY_PROMPT.system,
            temperature=REPLY_TEMPERATURE,
            thinking_budget=self._settings.gemini_coach_reply_thinking_budget,
        )

    async def _save(self, turn: LiveTurn, reply: str) -> CoachDoneEvent:
        """Store the turn whole: answers, both messages, the stage, and how the turn ended."""
        body, document = turn.body, turn.document
        messages = [NewMessage("coach", reply, body.language)]
        if body.text:
            messages.insert(0, NewMessage("user", body.text, body.language))
        # The ids and the turn number follow from the stored transcript, so they can be written
        # in the same step as the turn: m001-u, m002-c, and so on (`record_turn`).
        message_id = f"m{len(document['messages']) + len(messages):03d}-c"
        last = {
            **document["last_turn"],
            "state": "done",
            "turn": document["turn_count"] + (1 if body.text else 0),
            "message_id": message_id,
            "slots": [update.slot for update in turn.understanding.updates],
        }
        tier = ModelTier(self._settings.gemini_coach_reply_tier)
        session = await self._sessions.record_turn(
            turn.uid,
            turn.session_id,
            language=body.language,
            now=datetime.now(UTC),
            updates=turn.understanding.updates,
            messages=messages,
            declined=turn.understanding.declined,
            extra={
                "last_turn": last,
                "models": {
                    **document.get("models", {}),
                    "reply": model_for(tier, self._settings),
                },
                "prompt_versions": {
                    **document.get("prompt_versions", {}),
                    REPLY_PROMPT.key: REPLY_PROMPT.version,
                },
            },
        )
        return CoachDoneEvent(
            message_id=session.messages[-1].id,
            stage=session.stage,
            next_slot=session.next_slot,
            turn_count=session.turn_count,
        )

    async def _mark(
        self,
        uid: str,
        session_id: str,
        last_turn: dict[str, Any],
        state: str | None = None,
    ) -> None:
        """Write `last_turn` (with `state` if given). A failure here is logged, not raised: the
        turn's outcome is already decided and a stale marker expires by itself."""
        value = {**last_turn, "state": state} if state else last_turn
        try:
            await self._sessions.set_last_turn(uid, session_id, value, datetime.now(UTC))
        except (SessionConflictError, SessionNotFoundError, GoogleAPIError) as exc:
            logger.warning("coach_last_turn_not_written error=%s", type(exc).__name__)

    async def _refresh_summary(self, turn: LiveTurn) -> None:
        """Summarise the turns the history window left out, once the worker has their reply.

        Best effort: a failure costs the model some older context on the next turns, not the
        turn that was just saved.
        """
        dropped = turn.stream.dropped_turns
        covered = int(turn.document.get("summarised_turns", 0))
        if len(dropped) <= covered:
            return
        try:
            reply = await self._gemini.chat(
                operation=SUMMARY_OPERATION,
                tier=ModelTier.CLASSIFICATION,
                message=summary_message(turn.document.get("summary"), dropped[covered:]),
                system_instruction=SUMMARISE_PROMPT.system,
                temperature=0.2,
                thinking_budget=0,
            )
            await self._sessions.save_summary(
                turn.uid, turn.session_id, reply.text.strip(), len(dropped), datetime.now(UTC)
            )
        except (GeminiError, SessionConflictError, SessionNotFoundError, GoogleAPIError) as exc:
            logger.warning("coach_summary_not_saved error=%s", type(exc).__name__)


def _envelope(exc: Exception, request_id: str) -> dict[str, Any]:
    if isinstance(exc, SessionConflictError):
        status_code, code, message = 409, "turn_in_progress", "Another message is being answered."
    elif isinstance(exc, SessionFullError):
        status_code, code, message = 409, "session_full", "This conversation is too long."
    elif isinstance(exc, SessionNotActiveError):
        status_code, code, message = 409, "session_not_active", "This interview has ended."
    else:
        status_code, code, message = error_parts(exc)
    logger.warning("coach_turn_failed status=%d code=%s error=%s", status_code, code, exc)
    return ErrorEnvelope(code=code, message=message, request_id=request_id).model_dump(
        mode="json", exclude_none=True
    )
