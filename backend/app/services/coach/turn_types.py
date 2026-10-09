"""Errors and small types of the Coach turn (NF-FC-009)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.schemas.coach_profile import SlotName
from app.schemas.coach_questions import FollowUpTrigger
from app.schemas.contract import ReportLanguage
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
