"""Errors and small types of the Coach turn (NF-FC-009, NF-FC-013)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from types import TracebackType
from typing import Any, Protocol, Self

from app.integrations.gemini import ChatTurn, GeminiStream
from app.schemas.coach_profile import SlotName
from app.schemas.coach_questions import FollowUpTrigger
from app.schemas.coach_session import CoachTurnRequest
from app.schemas.contract import ReportLanguage
from app.services.coach.guard_types import GuardDecision, GuardReason
from app.services.coach.review_reader import ReviewMove
from app.services.coach.session_types import SlotUpdate


class TurnInProgressError(RuntimeError):
    """Another turn of this session is still running, under a different key."""


class RequestInProgressError(RuntimeError):
    """The turn with this very key is still running."""


class KeyReusedError(ValueError):
    """The key was used for a different body."""


class TextRequiredError(ValueError):
    """The worker's text was left out where the coach may not speak without one."""


@dataclass(frozen=True)
class Clarification:
    """Ask `slot` again for this reason, with the bank's wording for it."""

    slot: SlotName
    trigger: FollowUpTrigger


@dataclass(frozen=True)
class Understanding:
    """What the interview took from a worker's message (NF-FC-010 fills it in).

    `updates` are answers to store, `declined` the optional slots the worker would not answer,
    and `clarify` the question to ask again instead of moving on (the bank's follow-up wording
    is then used).
    """

    updates: Sequence[SlotUpdate] = ()
    declined: Sequence[SlotName] = ()
    clarify: Clarification | None = None
    # At the review stage only: the worker confirmed every answer, or wants to change one
    # (`ReviewMove`, NF-FC-020). Nothing else is read at the review.
    review: ReviewMove | None = None


class SlotExtractor(Protocol):
    async def extract(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> Understanding:
        """Read the worker's `text` against the stored `document` of the session."""
        ...


class NoExtraction:
    """Stands in until slot extraction exists (NF-FC-010): understands nothing, so the coach asks
    the same question again and the stage never moves."""

    async def extract(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> Understanding:
        return Understanding()


class Guard(Protocol):
    async def check(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> GuardDecision:
        """What to do with the worker's `text` before anything reads it (NF-FC-013)."""
        ...

    def check_reply(self, reply: str) -> GuardReason | None:
        """A reason when the coach's finished `reply` breaks a rule, else `None`."""
        ...


class NoGuard:
    """Stands in where no guard is wired (a test of something else): lets everything through."""

    async def check(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> GuardDecision:
        return GuardDecision("allow", "not_checked")

    def check_reply(self, reply: str) -> GuardReason | None:
        return None


_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")


class FixedReply:
    """A reply that is already written, given out a sentence at a time like a model's reply, so
    the screen shows it the same way. Used for a turn the guard blocked."""

    def __init__(self, text: str) -> None:
        pieces = [f"{sentence} " for sentence in _SENTENCE_END.split(text.strip())]
        pieces[-1] = pieces[-1].rstrip()
        self._pieces = pieces
        self.text = ""
        self.dropped_turns: list[ChatTurn] = []

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        if not self._pieces:
            raise StopAsyncIteration
        piece = self._pieces.pop(0)
        self.text += piece
        return piece

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._pieces.clear()


@dataclass
class LiveTurn:
    """A turn that has started: its reply stream is open and its first piece is in.

    `stream` is a `FixedReply` when the guard blocked the turn (`decision.blocked`): nothing was
    extracted and no model wrote the reply.
    """

    uid: str
    session_id: str
    key: str
    body_hash: str
    body: CoachTurnRequest
    understanding: Understanding
    document: dict[str, Any]
    stream: GeminiStream | FixedReply
    started_at: datetime
    decision: GuardDecision | None = None


@dataclass(frozen=True)
class ReplayTurn:
    """A finished turn asked for again with the same key: its events, from storage."""

    frames: tuple[str, ...]
