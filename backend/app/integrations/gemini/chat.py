from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from google.genai import types

Role = Literal["user", "model"]

# No tokenizer call (a round trip, and quota): this many characters per token is deliberately on
# the low side, so the estimate is high. Devanagari and Bengali text costs more tokens per
# character than English, which is the case that matters here.
_CHARS_PER_TOKEN = 3


@dataclass(frozen=True)
class ChatTurn:
    """One message of a conversation, as the caller stores it."""

    role: Role
    text: str


@dataclass(frozen=True)
class HistoryWindow:
    """The turns to send and the older ones left out, both in conversation order."""

    kept: list[ChatTurn]
    dropped: list[ChatTurn]


@dataclass(frozen=True)
class ChatReply:
    """A whole answer from `GeminiClient.chat`, and the turns left out of the history sent."""

    text: str
    dropped_turns: list[ChatTurn]


def estimate_tokens(text: str) -> int:
    return -(-len(text) // _CHARS_PER_TOKEN)


def truncate_history(
    turns: Sequence[ChatTurn], *, max_turns: int, max_tokens: int
) -> HistoryWindow:
    """Keep the newest turns that fit `max_turns` and `max_tokens` (estimated).

    The newest turn is taken first, even if it alone is over the token limit: a window with
    nothing in it would lose the message the model most needs. The window then starts on a user
    turn, because Gemini refuses a conversation that opens with a model turn; model turns
    skipped for that reason are returned in `dropped` like the rest. The caller can summarise
    `dropped` and pass the summary back, so older turns are not simply forgotten.
    """
    start = len(turns)
    used = 0
    while start > 0 and len(turns) - start < max_turns:
        cost = estimate_tokens(turns[start - 1].text)
        if used + cost > max_tokens and start < len(turns):
            break
        used += cost
        start -= 1
    while start < len(turns) and turns[start].role != "user":
        start += 1
    return HistoryWindow(kept=list(turns[start:]), dropped=list(turns[:start]))


def build_contents(turns: Sequence[ChatTurn], message: str) -> list[types.ContentUnion]:
    """The conversation in the SDK's shape: each turn, then the new user message."""
    contents: list[types.ContentUnion] = [
        types.Content(role=turn.role, parts=[types.Part(text=turn.text)]) for turn in turns
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


def with_summary(system_instruction: str | None, summary: str | None) -> str | None:
    """Add a summary of the dropped turns after the system instruction.

    The summary arrives already framed by the caller (its delimiters and the note that it is
    data, not instructions, live in the prompt file), so nothing is said here.
    """
    if not summary:
        return system_instruction
    return f"{system_instruction}\n\n{summary}" if system_instruction else summary
