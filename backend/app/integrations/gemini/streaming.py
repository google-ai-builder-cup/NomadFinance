from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

from google import genai
from google.genai import types

from app.integrations.gemini.chat import ChatTurn
from app.integrations.gemini.errors import GeminiResponseError
from app.integrations.gemini.model_tiers import ModelTier
from app.integrations.gemini.sdk_errors import empty_reason, translate_sdk_errors
from app.integrations.gemini.usage import log_failure, log_usage

logger = logging.getLogger(__name__)

Chunks = AsyncIterator[types.GenerateContentResponse]


async def _close(iterator: Chunks | None) -> None:
    aclose = getattr(iterator, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        # Nothing useful to do if the upstream is already gone.
        logger.debug("gemini_stream_close_failed", exc_info=True)


async def open_attempt(
    sdk: genai.Client,
    model: str,
    contents: list[types.ContentUnion],
    config: types.GenerateContentConfig,
    timeout_seconds: float,
) -> tuple[Chunks, types.GenerateContentResponse]:
    """Open the stream and wait for its first chunk that has text; one attempt, no retry.

    The retry belongs outside, and only up to here: once a first piece has gone to the worker,
    starting over would show the same words twice. An empty answer (a blocked prompt) is a
    `GeminiResponseError`, which is not retried.
    """
    iterator: Chunks | None = None
    try:
        with translate_sdk_errors(model, timeout_seconds):
            async with asyncio.timeout(timeout_seconds):
                iterator = await sdk.aio.models.generate_content_stream(
                    model=model, contents=contents, config=config
                )
                last: types.GenerateContentResponse | None = None
                while True:
                    try:
                        chunk = await anext(iterator)
                    except StopAsyncIteration:
                        raise GeminiResponseError(
                            f"{model} returned no content ({empty_reason(last)})"
                        ) from None
                    last = chunk
                    if chunk.text:
                        return iterator, chunk
    except BaseException:
        await _close(iterator)
        raise


class GeminiStream:
    """A model reply arriving piece by piece: `async for piece in stream`.

    Opened by `GeminiClient.stream`, which has already waited for the first piece, so an error
    that can still be retried has been retried and one that cannot has been raised. From here a
    failure ends the iteration with a `GeminiError` for the caller to report (the endpoint sends
    an SSE `error` event: the status line has gone out already).

    It closes the upstream call when the loop ends, fails, is cancelled (the worker's phone went
    away) or `aclose()` / `async with` is used, so a Gemini call is never left running for
    nobody. Cancellation is passed on untouched.

    Attributes:
        text: Everything received so far.
        usage: Token counts, once Google has sent them (the last chunk carries them).
        time_to_first_token_ms: From the start of the call, retries included.
        dropped_turns: History turns left out by truncation, for the caller to summarise.
    """

    def __init__(
        self,
        iterator: Chunks,
        first: types.GenerateContentResponse,
        *,
        model: str,
        tier: ModelTier,
        operation: str,
        timeout: float,
        started: float,
        attempts: int,
        dropped_turns: list[ChatTurn],
    ) -> None:
        self._iterator = iterator
        self._pending: types.GenerateContentResponse | None = first
        self._model = model
        self._tier = tier
        self._operation = operation
        self._timeout = timeout
        self._started = started
        self._attempts = attempts
        self._done = False
        self.text = ""
        self.usage: types.GenerateContentResponseUsageMetadata | None = None
        self.time_to_first_token_ms = _ms_since(started)
        self.dropped_turns = dropped_turns

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> str:
        while not self._done:
            chunk, self._pending = self._pending, None
            if chunk is None:
                try:
                    chunk = await self._next_chunk()
                except StopAsyncIteration:
                    self._finish()
                    await _close(self._iterator)
                    break
                except BaseException as exc:
                    await self._abort(exc)
                    raise
            if chunk.usage_metadata is not None:
                self.usage = chunk.usage_metadata
            if chunk.text:
                self.text += chunk.text
                return chunk.text
        raise StopAsyncIteration

    async def _next_chunk(self) -> types.GenerateContentResponse:
        with translate_sdk_errors(self._model, self._timeout):
            async with asyncio.timeout(self._timeout):
                return await anext(self._iterator)

    def _finish(self) -> None:
        if self._done:
            return
        self._done = True
        log_usage(
            self.usage,
            operation=self._operation,
            tier=self._tier,
            model=self._model,
            latency_ms=_ms_since(self._started),
            attempts=self._attempts,
            time_to_first_token_ms=self.time_to_first_token_ms,
        )

    async def _abort(self, error: BaseException) -> None:
        if not self._done:
            self._done = True
            log_failure(
                error,
                operation=self._operation,
                tier=self._tier,
                model=self._model,
                latency_ms=_ms_since(self._started),
                attempts=self._attempts,
                outcome="cancelled" if isinstance(error, asyncio.CancelledError) else "failed",
            )
        await _close(self._iterator)

    async def aclose(self) -> None:
        """Stop reading and close the upstream call. Safe to call again, and after the end."""
        if not self._done:
            self._done = True
            log_failure(
                None,
                operation=self._operation,
                tier=self._tier,
                model=self._model,
                latency_ms=_ms_since(self._started),
                attempts=self._attempts,
                outcome="closed",
            )
        await _close(self._iterator)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()


def _ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
