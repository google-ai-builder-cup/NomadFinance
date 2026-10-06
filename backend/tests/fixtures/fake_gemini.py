"""A stand-in for `GeminiClient` that replays recorded answers (NF-F0-014).

Tests of a service or an endpoint need Gemini's answer, not Gemini. `FakeGemini` has the same
three calls as the real client (`generate_structured`, `chat`, `stream`) and answers each one
from a JSON file in `tests/fixtures/gemini/`, found by the call's `operation` name. No network,
no key, no quota.

A recording is one file named after the operation, `<operation>.json`:

    {"operation": "contract.detect", "kind": "structured", "response": {...}}
    {"operation": "coach.reply", "kind": "text", "text": "The whole reply."}
    {"operation": "coach.reply", "kind": "text", "pieces": ["The ", "whole ", "reply."]}
    {"operation": "scam.classify", "kind": "structured", "error": "GeminiRateLimitError"}

- `structured`: `response` is validated into the call's `response_model`, so a recording that no
  longer fits the model fails the test, which is the point.
- `text`: `text` for `chat`, and for `stream` split into `pieces` (or give `pieces` yourself).
- `error`: the name of an exception in `app.integrations.gemini.errors`, raised instead.
- `responses`: a list of any of the above, replayed in order, the last one repeated, for a test
  that makes the same call more than once.

Recordings are synthetic. Never save a real worker's text, or a real model answer containing
one, in this folder.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Self

from fastapi import FastAPI

from app.integrations.gemini import ChatReply, GeminiClient, errors, get_gemini_client

RECORDINGS_DIR = Path(__file__).resolve().parent / "gemini"


class NoRecordingError(AssertionError):
    """A call had no recording, so the test is missing a file or has a wrong operation name."""


class FakeStream:
    """The part of `GeminiStream` that callers use: `async for`, `async with`, `text`."""

    def __init__(self, pieces: list[str]) -> None:
        self._pieces = list(pieces)
        self.text = ""
        self.usage = None
        self.time_to_first_token_ms = 0
        self.dropped_turns: list[Any] = []
        self.closed = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        if self.closed or not self._pieces:
            raise StopAsyncIteration
        piece = self._pieces.pop(0)
        self.text += piece
        return piece

    async def aclose(self) -> None:
        self.closed = True

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()


class FakeGemini:
    """Replays recorded answers by `operation`, and keeps every call for the test to inspect."""

    def __init__(
        self,
        recordings: Mapping[str, Any] | None = None,
        *,
        directory: Path = RECORDINGS_DIR,
    ) -> None:
        # In-memory recordings win over files, so a test can set one answer in one line.
        self._recordings = dict(recordings or {})
        self._directory = directory
        self._served: dict[str, int] = {}
        self.calls: list[dict[str, Any]] = []

    def _next(self, operation: str, kind: str) -> dict[str, Any]:
        recording = self._recordings.get(operation)
        if recording is None:
            path = self._directory / f"{operation}.json"
            if not path.is_file():
                raise NoRecordingError(
                    f"no recording for operation {operation!r}: add {path.name} to "
                    f"{self._directory} or pass it to FakeGemini(recordings=...)"
                )
            recording = json.loads(path.read_text(encoding="utf-8"))
        entries = recording["responses"] if "responses" in recording else [recording]
        index = min(self._served.get(operation, 0), len(entries) - 1)
        self._served[operation] = self._served.get(operation, 0) + 1
        entry: dict[str, Any] = entries[index]
        if "error" in entry:
            error_type = getattr(errors, entry["error"])
            raise error_type(entry.get("message", "recorded failure"))
        if entry.get("kind", recording.get("kind")) != kind:
            raise NoRecordingError(
                f"the recording for {operation!r} is not a {kind!r} answer: "
                f"it is {entry.get('kind', recording.get('kind'))!r}"
            )
        return entry

    async def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append({"call": "generate_structured", **kwargs})
        entry = self._next(kwargs["operation"], "structured")
        return kwargs["response_model"].model_validate(entry["response"])

    async def chat(self, **kwargs: Any) -> ChatReply:
        self.calls.append({"call": "chat", **kwargs})
        entry = self._next(kwargs["operation"], "text")
        return ChatReply(text=_whole_text(entry), dropped_turns=[])

    async def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append({"call": "stream", **kwargs})
        entry = self._next(kwargs["operation"], "text")
        return FakeStream(entry["pieces"] if "pieces" in entry else _split(entry["text"]))


def _whole_text(entry: dict[str, Any]) -> str:
    return str(entry["text"]) if "text" in entry else "".join(entry["pieces"])


def _split(text: str) -> list[str]:
    # A word at a time, with its space, so a streamed reply joins back to exactly `text`.
    words = text.split(" ")
    return [word + " " for word in words[:-1]] + [words[-1]]


def override_gemini(app: FastAPI, fake: FakeGemini) -> None:
    """Make an app under test use `fake` wherever it asks for the Gemini client."""
    app.dependency_overrides[get_gemini_client] = lambda: fake


def as_client(fake: FakeGemini) -> GeminiClient:
    """For a service that takes a `GeminiClient`: the type checker cannot know a fake fits."""
    return fake  # type: ignore[return-value]
