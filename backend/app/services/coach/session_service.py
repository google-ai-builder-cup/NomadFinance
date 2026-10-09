"""The Coach session: start or resume, read, move through the stages (NF-FC-008).

The turn endpoint (NF-FC-009, -010) calls `record_turn` to save a turn; the plan endpoint
(NF-FC-012) calls `complete`. Every method reads the stored session, applies the rules of
`session_machine`, and writes with the revision it read, so a restart loses nothing that was
saved and two writers cannot overwrite each other.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.core.redact import redact_text
from app.repositories.coach_session_repo import (
    CoachPlanRepository,
    CoachSessionRepository,
    RevisionConflictError,
    SessionContentionError,
    SessionMissingError,
)
from app.schemas.coach_profile import SlotName, parse_slot_value
from app.schemas.coach_questions import QuestionBank
from app.schemas.coach_session import (
    MAX_TRANSCRIPT_MESSAGES,
    CoachOverview,
    CoachSession,
)
from app.schemas.contract import ReportLanguage
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import (
    IDLE_AFTER,
    KEEP_FOR,
    Scorer,
    expired,
    idle,
    jsonable,
    new_document,
    scorable_profile,
    to_session,
)
from app.services.coach.session_machine import (
    IllegalTransitionError,
    settle,
    stage_of,
    status_transition,
    transition,
)
from app.services.coach.session_overview import build_overview
from app.services.coach.session_types import (
    NewMessage,
    SessionConflictError,
    SessionFullError,
    SessionNotActiveError,
    SessionNotFoundError,
    SlotUpdate,
    StartResult,
)


class CoachSessions:
    def __init__(
        self,
        sessions: CoachSessionRepository,
        plans: CoachPlanRepository,
        *,
        bank: QuestionBank | None = None,
        scorer: Scorer | None = None,
    ) -> None:
        self._sessions = sessions
        self._plans = plans
        self._bank = bank or load_question_bank()
        self._scorer = scorer

    async def start(
        self, uid: str, language: ReportLanguage, *, restart: bool, now: datetime
    ) -> StartResult:
        """The worker's active session, or a new one. `restart` closes the active one first."""
        document = new_document(language, now, self._bank)
        try:
            session_id, stored, resumed = await run_in_threadpool(
                self._sessions.create_or_resume,
                uid,
                self._sessions.new_id(uid),
                document,
                restart=restart,
                idle_before=now - IDLE_AFTER,
            )
        except SessionContentionError as exc:
            raise SessionConflictError(uid) from exc
        return StartResult(await self._view(session_id, stored), resumed)

    async def get(self, uid: str, session_id: str, now: datetime) -> CoachSession:
        """One session. An active one idle for 14 days is closed here, as `abandoned`."""
        document = await self._load(uid, session_id, now)
        return await self._view(session_id, document)

    async def overview(self, uid: str, now: datetime) -> CoachOverview:
        """The open session and the newest plan, without creating or changing anything."""
        return await build_overview(self._sessions, self._plans, self._bank, uid, now)

    async def record_turn(
        self,
        uid: str,
        session_id: str,
        *,
        language: ReportLanguage,
        now: datetime,
        updates: Sequence[SlotUpdate] = (),
        messages: Sequence[NewMessage] = (),
        declined: Sequence[SlotName] = (),
        extra: dict[str, Any] | None = None,
    ) -> CoachSession:
        """Save one turn: the answers understood, the messages, the language, the new stage.

        `declined` names optional slots the worker chose not to answer. `extra` carries fields
        only the turn endpoint knows (`last_turn`, `models`, `prompt_versions`, `summary`).
        Everything is written in one step, so a turn is either saved whole or not at all.

        Raises:
            SessionNotFoundError, SessionNotActiveError: The session cannot take a turn.
            SessionFullError: The messages would pass the transcript limit.
            SessionConflictError: The session changed meanwhile; read it again.
            KeyError, pydantic.ValidationError: An update names no slot, or holds a value the
                slot cannot (a bug of the caller, not of the worker).
        """
        document = await self._load(uid, session_id, now)
        self._require_active(document)
        stored_messages = list(document["messages"])
        if len(stored_messages) + len(messages) > MAX_TRANSCRIPT_MESSAGES:
            raise SessionFullError(session_id)
        turn = document["turn_count"] + (1 if any(m.role == "user" for m in messages) else 0)

        slots = dict(document["slots"])
        for update in updates:
            value = parse_slot_value(update.slot, update.value)
            slots[update.slot] = {
                "value": jsonable(value),
                "confidence": update.confidence,
                "source": update.source,
                "confirmed": update.confirmed,
                "updated_at": now,
                "turn": turn,
            }
        declined_slots = self._declined(document, declined, slots)
        for message in messages:
            stored_messages.append(
                {
                    "id": f"m{len(stored_messages) + 1:03d}-{message.role[0]}",
                    "role": message.role,
                    "text": redact_text(message.text),
                    "language": message.language,
                    "at": now,
                }
            )
        changes = {
            **(extra or {}),
            "slots": slots,
            "declined_slots": declined_slots,
            "messages": stored_messages,
            "turn_count": turn,
            "language": language,
            "stage": settle(self._bank, document["stage"], slots, declined_slots),
            "last_active": now,
            "expires_at": now + KEEP_FOR,
        }
        return await self._write(uid, session_id, document, changes)

    async def request_correction(
        self, uid: str, session_id: str, slot: SlotName, now: datetime
    ) -> CoachSession:
        """At `review` the worker corrects an answer: back to the stage that holds it.

        Raises:
            IllegalTransitionError: The session is not at `review`.
            ValueError: The slot was never answered, so there is nothing to correct.
        """
        document = await self._load(uid, session_id, now)
        self._require_active(document)
        if document["stage"] != "review":
            raise IllegalTransitionError("Answers are corrected at the review stage.")
        target = transition("review", stage_of(self._bank, slot))
        slots = {name: dict(record) for name, record in document["slots"].items()}
        declined = [name for name in document.get("declined_slots", []) if name != slot]
        if slot not in slots and len(declined) == len(document.get("declined_slots", [])):
            raise ValueError(f"{slot} has not been answered, so it cannot be corrected.")
        if slot in slots:
            slots[slot]["confirmed"] = False
        changes = {"stage": target, "slots": slots, "declined_slots": declined}
        return await self._write(uid, session_id, document, changes)

    async def confirm_review(self, uid: str, session_id: str, now: datetime) -> CoachSession:
        """The worker says the list is right: every answer is confirmed, stage `plan`.

        Raises:
            IllegalTransitionError: The session is not at `review`.
        """
        document = await self._load(uid, session_id, now)
        self._require_active(document)
        target = transition(document["stage"], "plan")
        slots = {
            name: {**record, "confirmed": True, "updated_at": now}
            for name, record in document["slots"].items()
        }
        return await self._write(uid, session_id, document, {"stage": target, "slots": slots})

    async def complete(
        self, uid: str, session_id: str, plan_id: str, now: datetime
    ) -> CoachSession:
        """A plan was made: the session is `completed` and kept 30 days from now.

        Raises:
            IllegalTransitionError: The session is not at `plan`, or already finished.
        """
        document = await self._load(uid, session_id, now)
        if document["stage"] != "plan":
            raise IllegalTransitionError(
                f"A plan is made at the plan stage, not at {document['stage']}."
            )
        status = status_transition(document["status"], "completed")
        changes = {
            "status": status,
            "plan_id": plan_id,
            "completed_at": now,
            "expires_at": now + KEEP_FOR,
        }
        return await self._write(uid, session_id, document, changes)

    async def document(self, uid: str, session_id: str, now: datetime) -> dict[str, Any]:
        """The stored session as the turn endpoint needs it (messages, `last_turn`, `summary`).

        Raises:
            SessionNotFoundError: No such session, or it has expired.
        """
        return await self._load(uid, session_id, now)

    async def set_last_turn(
        self,
        uid: str,
        session_id: str,
        last_turn: dict[str, Any],
        now: datetime,
        *,
        read: dict[str, Any] | None = None,
    ) -> None:
        """Record the turn in progress (or how it ended), apart from the turn itself.

        Pass the `read` document the decision to start was made on, and the write is refused if
        the session has changed since: that is what stops two turns starting at once.

        Raises:
            SessionConflictError: The session changed since it was read.
        """
        document = read if read is not None else await self._load(uid, session_id, now)
        await self._write_document(uid, session_id, document, {"last_turn": last_turn})

    async def save_summary(
        self, uid: str, session_id: str, summary: str, turns: int, now: datetime
    ) -> None:
        """Store the summary of the turns older than the history window, and how many it covers."""
        document = await self._load(uid, session_id, now)
        changes = {"summary": summary, "summarised_turns": turns}
        await self._write_document(uid, session_id, document, changes)

    def _declined(
        self, document: dict[str, Any], declined: Sequence[SlotName], slots: dict[str, Any]
    ) -> list[str]:
        """The declined slots after this turn. Only the optional slot can be declined."""
        for name in declined:
            if self._bank.question(name).required:
                raise ValueError(f"{name} is required: it cannot be declined.")
        merged = {*document.get("declined_slots", []), *declined}
        return sorted(name for name in merged if name not in slots)

    @staticmethod
    def _require_active(document: dict[str, Any]) -> None:
        if document["status"] != "active":
            raise SessionNotActiveError(document["status"])

    async def _load(self, uid: str, session_id: str, now: datetime) -> dict[str, Any]:
        document = await run_in_threadpool(self._sessions.get, uid, session_id)
        if document is None or expired(document, now):
            raise SessionNotFoundError(session_id)
        if document["status"] == "active" and idle(document, now):
            status = status_transition("active", "abandoned")
            return await self._write_document(uid, session_id, document, {"status": status})
        return document

    async def _write_document(
        self, uid: str, session_id: str, document: dict[str, Any], changes: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return await run_in_threadpool(
                self._sessions.update,
                uid,
                session_id,
                expected_revision=document["revision"],
                changes=changes,
            )
        except SessionMissingError as exc:
            raise SessionNotFoundError(session_id) from exc
        except (RevisionConflictError, SessionContentionError) as exc:
            raise SessionConflictError(session_id) from exc

    async def _write(
        self, uid: str, session_id: str, document: dict[str, Any], changes: dict[str, Any]
    ) -> CoachSession:
        stored = await self._write_document(uid, session_id, document, changes)
        return await self._view(session_id, stored)

    async def _view(self, session_id: str, document: dict[str, Any]) -> CoachSession:
        """The contract's view of a stored session, with its score from `review` on."""
        profile = scorable_profile(document, self._bank)
        score = None
        if self._scorer is not None and profile is not None:
            score = await self._scorer(profile)
        return to_session(session_id, document, self._bank, score)
