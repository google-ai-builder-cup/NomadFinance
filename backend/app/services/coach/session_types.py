"""Errors and small value types of the Coach session service (NF-FC-008)."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.coach_profile import SlotName, SlotSource
from app.schemas.coach_session import CoachSession, MessageRole
from app.schemas.contract import ReportLanguage


class SessionNotFoundError(LookupError):
    """No such session for this worker, or it has expired."""


class SessionNotActiveError(RuntimeError):
    """The session is completed or abandoned: it takes no more turns."""


class SessionFullError(RuntimeError):
    """The transcript already holds the most messages a session may."""


class SessionConflictError(RuntimeError):
    """Another request changed the session between reading and writing it."""


@dataclass(frozen=True)
class StartResult:
    session: CoachSession
    resumed: bool


@dataclass(frozen=True)
class SlotUpdate:
    """One answer to store. `value` is whatever `CoachProfile` holds for the slot."""

    slot: SlotName
    value: object
    confidence: float
    confirmed: bool
    source: SlotSource = "user"


@dataclass(frozen=True)
class NewMessage:
    role: MessageRole
    text: str
    language: ReportLanguage
