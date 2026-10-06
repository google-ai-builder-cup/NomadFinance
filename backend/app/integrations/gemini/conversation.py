from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass

from google import genai
from google.genai import types
from tenacity import AsyncRetrying

from app.config import Settings
from app.integrations.gemini.chat import (
    ChatTurn,
    build_contents,
    truncate_history,
    with_summary,
)
from app.integrations.gemini.errors import GeminiError
from app.integrations.gemini.model_tiers import ModelTier, model_for
from app.integrations.gemini.streaming import Chunks, GeminiStream, open_attempt
from app.integrations.gemini.usage import log_failure


def build_config(
    *,
    system_instruction: str | None,
    temperature: float | None,
    safety_settings: Sequence[types.SafetySetting] | None,
    thinking_budget: int | None,
    **structured: object,
) -> types.GenerateContentConfig:
    """The request config every call shares; `structured` adds the response schema, if any."""
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        safety_settings=list(safety_settings) if safety_settings else None,
        thinking_config=(
            types.ThinkingConfig(thinking_budget=thinking_budget)
            if thinking_budget is not None
            else None
        ),
        # No tools are ever passed, so the SDK's function-calling loop only adds log noise.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **structured,
    )


@dataclass(frozen=True)
class PreparedChat:
    """A conversation turned into one request: the model, config and contents to send."""

    model: str
    config: types.GenerateContentConfig
    contents: list[types.ContentUnion]
    dropped_turns: list[ChatTurn]


def prepare_chat(
    settings: Settings,
    tier: ModelTier,
    message: str,
    history: Sequence[ChatTurn],
    *,
    system_instruction: str | None,
    summary: str | None,
    temperature: float | None,
    safety_settings: Sequence[types.SafetySetting] | None,
    thinking_budget: int | None,
    max_history_turns: int | None,
    max_history_tokens: int | None,
) -> PreparedChat:
    window = truncate_history(
        history,
        max_turns=max_history_turns or settings.gemini_chat_history_turns,
        max_tokens=max_history_tokens or settings.gemini_chat_history_tokens,
    )
    return PreparedChat(
        model=model_for(tier, settings),
        config=build_config(
            system_instruction=with_summary(system_instruction, summary),
            temperature=temperature,
            safety_settings=safety_settings,
            thinking_budget=thinking_budget,
        ),
        contents=build_contents(window.kept, message),
        dropped_turns=window.dropped,
    )


def _attempts(retrying: AsyncRetrying) -> int:
    return int(retrying.statistics.get("attempt_number", 1))


async def start_stream(
    sdk: genai.Client,
    retrying: AsyncRetrying,
    prepared: PreparedChat,
    *,
    operation: str,
    tier: ModelTier,
    timeout_seconds: float,
) -> GeminiStream:
    """Open the stream (retried until the first piece arrives) and wrap it; logs a failure."""
    started = time.perf_counter()
    try:
        opened: tuple[Chunks, types.GenerateContentResponse] = await retrying(
            open_attempt,
            sdk,
            prepared.model,
            prepared.contents,
            prepared.config,
            timeout_seconds,
        )
        iterator, first = opened
    except (GeminiError, asyncio.CancelledError) as exc:
        log_failure(
            exc,
            operation=operation,
            tier=tier,
            model=prepared.model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            attempts=_attempts(retrying),
            outcome="cancelled" if isinstance(exc, asyncio.CancelledError) else "failed",
        )
        raise
    return GeminiStream(
        iterator,
        first,
        model=prepared.model,
        tier=tier,
        operation=operation,
        timeout=timeout_seconds,
        started=started,
        attempts=_attempts(retrying),
        dropped_turns=prepared.dropped_turns,
    )
