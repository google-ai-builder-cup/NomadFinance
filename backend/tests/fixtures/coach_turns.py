"""Stand-ins and helpers for the Coach turn tests (NF-FC-009)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Self

from fastapi import FastAPI

from app.dependencies import get_coach_turns
from app.integrations.gemini import ChatReply, ChatTurn
from app.services.coach.session_service import CoachSessions
from app.services.coach.turn_service import CoachTurns
from app.services.coach.turn_types import Guard, Understanding
from tests.fixtures.coach_sessions import NOW, FakeSessionRepo, make_coach_app, make_sessions

OPENING = ["Hello! ", "Which country will you work in?"]


class ScriptedStream:
    """A reply stream that gives `pieces`, then ends, or fails with `error` after them."""

    def __init__(
        self,
        pieces: Sequence[str] = tuple(OPENING),
        *,
        error: Exception | None = None,
        dropped: Sequence[ChatTurn] = (),
        hang: bool = False,
    ) -> None:
        self._pieces = list(pieces)
        self._error = error
        self._hang = hang
        self.text = ""
        self.usage = None
        self.time_to_first_token_ms = 0
        self.dropped_turns = list(dropped)
        self.closed = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        if self.closed:
            raise StopAsyncIteration
        if self._pieces:
            piece = self._pieces.pop(0)
            self.text += piece
            return piece
        if self._hang:
            await asyncio.Event().wait()
        if self._error is not None:
            raise self._error
        raise StopAsyncIteration

    async def aclose(self) -> None:
        self.closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


class StubGemini:
    """The two calls the Coach turn makes, answered from what a test sets."""

    def __init__(self, stream: ScriptedStream | None = None, summary: str = "Notes.") -> None:
        self.next_stream = stream or ScriptedStream()
        self.summary = summary
        self.open_error: Exception | None = None
        self.summary_error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    async def stream(self, **kwargs: Any) -> ScriptedStream:
        self.calls.append({"call": "stream", **kwargs})
        if self.open_error is not None:
            raise self.open_error
        return self.next_stream

    async def chat(self, **kwargs: Any) -> ChatReply:
        self.calls.append({"call": "chat", **kwargs})
        if self.summary_error is not None:
            raise self.summary_error
        return ChatReply(text=self.summary, dropped_turns=[])

    def streams(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["call"] == "stream"]


class StubExtractor:
    """Understands whatever a test says it understood."""

    def __init__(self, understanding: Understanding | None = None) -> None:
        self.understanding = understanding or Understanding()
        self.seen: list[str] = []

    async def extract(self, document: dict[str, Any], text: str, language: str) -> Understanding:
        self.seen.append(text)
        return self.understanding


def make_turns(
    gemini: StubGemini | None = None,
    extractor: StubExtractor | None = None,
    guard: Guard | None = None,
) -> tuple[CoachTurns, CoachSessions, FakeSessionRepo, StubGemini]:
    """The turn service over in-memory storage and a stub Gemini."""
    service, repo, _ = make_sessions()
    stub = gemini or StubGemini()
    turns = CoachTurns(service, stub, extractor=extractor, guard=guard)  # type: ignore[arg-type]
    return turns, service, repo, stub


def make_turn_app(turns: CoachTurns, service: CoachSessions, **options: Any) -> FastAPI:
    app = make_coach_app(service, **options)
    app.dependency_overrides[get_coach_turns] = lambda: turns
    return app


def parse_stream(text: str) -> list[tuple[str, Any]]:
    """The events of a stream body, in order; a heartbeat comes back as `("ping", None)`."""
    found: list[tuple[str, Any]] = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if line]
        if not lines:
            continue
        if all(line.startswith(":") for line in lines):
            assert all(line == ": ping" for line in lines)
            found.append(("ping", None))
            continue
        assert lines[0].startswith("event: ") and lines[1].startswith("data: ") and len(lines) == 2
        found.append((lines[0][7:], json.loads(lines[1][6:])))
    return found


def reply_text(events: list[tuple[str, Any]]) -> str:
    return "".join(data["text"] for name, data in events if name == "token")


def later(minutes: float = 1.0) -> Any:
    return NOW + timedelta(minutes=minutes)


def stored(repo: Any, uid: str, session_id: str) -> dict[str, Any]:
    document: dict[str, Any] = repo.docs[(uid, session_id)]
    return document
