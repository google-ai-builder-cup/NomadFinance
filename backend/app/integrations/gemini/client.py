from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from functools import lru_cache, partial
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.config import Settings, get_settings
from app.integrations.gemini.chat import ChatReply, ChatTurn
from app.integrations.gemini.conversation import build_config, prepare_chat, start_stream
from app.integrations.gemini.embeddings import embed_text
from app.integrations.gemini.errors import (
    GeminiError,
    GeminiRateLimitError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.integrations.gemini.model_tiers import ModelTier, model_for
from app.integrations.gemini.sdk_errors import empty_reason, translate_sdk_errors
from app.integrations.gemini.streaming import GeminiStream
from app.integrations.gemini.usage import log_failure, log_retry, log_usage

ResponseT = TypeVar("ResponseT", bound=BaseModel)

_RETRYABLE = (GeminiRateLimitError, GeminiUnavailableError, GeminiTimeoutError)


class GeminiClient:
    """Single entry point for Gemini calls across all pillars.

    Picks the model from a `ModelTier`, enforces a per-attempt timeout, retries transient
    failures with jittered exponential backoff, and logs one line per call with the feature,
    model, tokens in and out and latency (also for a call that fails). `generate_structured`
    forces output into a Pydantic `response_schema`; `chat` and `stream` carry a conversation
    (the caller keeps it: the client holds no state between calls).

    Args:
        settings: App settings (API key, per-tier model IDs, timeout, attempts).
        sdk_client: Pre-built google-genai client; tests inject a fake here.
        max_backoff_seconds: Upper bound for the wait between retries.
    """

    def __init__(
        self,
        settings: Settings,
        sdk_client: genai.Client | None = None,
        *,
        max_backoff_seconds: float = 8.0,
    ) -> None:
        self._settings = settings
        self._sdk = sdk_client or genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        self._max_backoff_seconds = max_backoff_seconds

    async def generate_structured(
        self,
        *,
        operation: str,
        tier: ModelTier,
        contents: types.ContentListUnion | types.ContentListUnionDict,
        response_model: type[ResponseT],
        system_instruction: str | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        safety_settings: Sequence[types.SafetySetting] | None = None,
        thinking_budget: int | None = None,
    ) -> ResponseT:
        """Run one Gemini call and return its output validated as `response_model`.

        Args:
            operation: Pipeline step label for logs and cost tracking, e.g. "contract.extract".
            tier: Workload tier; selects the model.
            contents: Prompt text and/or parts (e.g. `types.Part.from_bytes` for images, PDFs).
            response_model: Pydantic model used as the response schema and for validation.
            system_instruction: System prompt, loaded from the prompt library by the caller.
            temperature: Sampling temperature; None keeps the model default.
            timeout_seconds: Per-attempt timeout; None uses GEMINI_TIMEOUT_SECONDS. Calls
                whose output grows with the input (a long contract) need more.
            safety_settings: Per-call content filter thresholds; None keeps Google's defaults.
            thinking_budget: Most tokens the model may spend thinking (0 turns it off); None
                keeps the model default. Only the reasoning tier thinks much.

        Returns:
            The validated `response_model` instance.

        Raises:
            GeminiRequestError: The request was rejected; retrying will not help.
            GeminiRateLimitError: Still rate limited after all attempts.
            GeminiUnavailableError: Server or network errors on every attempt.
            GeminiTimeoutError: Every attempt timed out.
            GeminiResponseError: Empty, blocked, or schema-invalid output.
        """
        model = model_for(tier, self._settings)
        config = build_config(
            system_instruction=system_instruction,
            temperature=temperature,
            safety_settings=safety_settings,
            thinking_budget=thinking_budget,
            response_mime_type="application/json",
            response_schema=response_model,
        )
        response = await self._run(operation, tier, model, contents, config, timeout_seconds)
        return _parse(response, response_model, model)

    async def chat(
        self,
        *,
        operation: str,
        tier: ModelTier,
        message: str,
        history: Sequence[ChatTurn] = (),
        system_instruction: str | None = None,
        summary: str | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        safety_settings: Sequence[types.SafetySetting] | None = None,
        thinking_budget: int | None = None,
        max_history_turns: int | None = None,
        max_history_tokens: int | None = None,
    ) -> ChatReply:
        """Answer one message of a conversation, with the whole answer at once.

        `history` is truncated first (`truncate_history`: the newest turns that fit
        `max_history_turns` and `max_history_tokens`, defaulting to the GEMINI_CHAT_HISTORY_*
        settings). The turns left out come back in `ChatReply.dropped_turns` for the caller to
        summarise; `summary`, framed by the caller, is added after the system instruction.
        Other arguments and errors are as in `generate_structured`; a reply with no text is a
        `GeminiResponseError`.
        """
        prepared = prepare_chat(
            self._settings,
            tier,
            message,
            history,
            system_instruction=system_instruction,
            summary=summary,
            temperature=temperature,
            safety_settings=safety_settings,
            thinking_budget=thinking_budget,
            max_history_turns=max_history_turns,
            max_history_tokens=max_history_tokens,
        )
        model = prepared.model
        response = await self._run(
            operation, tier, model, prepared.contents, prepared.config, timeout_seconds
        )
        if not response.text:
            raise GeminiResponseError(f"{model} returned no content ({empty_reason(response)})")
        return ChatReply(text=response.text, dropped_turns=prepared.dropped_turns)

    async def stream(
        self,
        *,
        operation: str,
        tier: ModelTier,
        message: str,
        history: Sequence[ChatTurn] = (),
        system_instruction: str | None = None,
        summary: str | None = None,
        temperature: float | None = None,
        timeout_seconds: float | None = None,
        safety_settings: Sequence[types.SafetySetting] | None = None,
        thinking_budget: int | None = None,
        max_history_turns: int | None = None,
        max_history_tokens: int | None = None,
    ) -> GeminiStream:
        """Start a reply and return it as a stream of text pieces (`async for piece in stream`).

        Same arguments as `chat`. Returns once the first piece has arrived: opening is retried
        like any call (429s, 5xx, timeouts), but nothing is retried after a piece has gone out.
        `timeout_seconds` bounds the wait for the first piece and then the wait between pieces.
        Errors before the first piece are raised here; later ones end the iteration. Use it as
        `async with` so the upstream call closes however the loop ends.
        """
        prepared = prepare_chat(
            self._settings,
            tier,
            message,
            history,
            system_instruction=system_instruction,
            summary=summary,
            temperature=temperature,
            safety_settings=safety_settings,
            thinking_budget=thinking_budget,
            max_history_turns=max_history_turns,
            max_history_tokens=max_history_tokens,
        )
        return await start_stream(
            self._sdk,
            self._retrying(operation, tier, prepared.model),
            prepared,
            operation=operation,
            tier=tier,
            timeout_seconds=timeout_seconds or self._settings.gemini_timeout_seconds,
        )

    async def _run(
        self,
        operation: str,
        tier: ModelTier,
        model: str,
        contents: types.ContentListUnion | types.ContentListUnionDict,
        config: types.GenerateContentConfig,
        timeout_seconds: float | None,
    ) -> types.GenerateContentResponse:
        """One non-streaming call with retries; logs a usage line, or a failure line."""
        retrying = self._retrying(operation, tier, model)
        started = time.perf_counter()
        try:
            response: types.GenerateContentResponse = await retrying(
                self._call, model, contents, config, timeout_seconds
            )
        except GeminiError as exc:
            log_failure(
                exc,
                operation=operation,
                tier=tier,
                model=model,
                latency_ms=_ms_since(started),
                attempts=retrying.statistics.get("attempt_number", 1),
            )
            raise
        log_usage(
            response.usage_metadata,
            operation=operation,
            tier=tier,
            model=model,
            latency_ms=_ms_since(started),
            attempts=retrying.statistics.get("attempt_number", 1),
        )
        return response

    def _retrying(self, operation: str, tier: ModelTier, model: str) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(self._settings.gemini_max_attempts),
            wait=wait_random_exponential(multiplier=1, max=self._max_backoff_seconds),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=partial(log_retry, operation=operation, tier=tier, model=model),
            reraise=True,
        )

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        """Embed `text` as one normalized 768-number vector (`gemini_model_embedding`).

        Same error contract as `generate_structured`; see `embeddings.embed_text`.
        """
        return await embed_text(
            self._sdk,
            self._settings,
            text,
            operation=operation,
            max_backoff_seconds=self._max_backoff_seconds,
        )

    async def _call(
        self,
        model: str,
        contents: types.ContentListUnion | types.ContentListUnionDict,
        config: types.GenerateContentConfig,
        timeout_seconds: float | None = None,
    ) -> types.GenerateContentResponse:
        timeout = timeout_seconds or self._settings.gemini_timeout_seconds
        with translate_sdk_errors(model, timeout):
            async with asyncio.timeout(timeout):
                return await self._sdk.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )


def _ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _parse(
    response: types.GenerateContentResponse, response_model: type[ResponseT], model: str
) -> ResponseT:
    if isinstance(response.parsed, response_model):
        return response.parsed

    text = response.text
    if not text:
        raise GeminiResponseError(f"{model} returned no content ({empty_reason(response)})")
    try:
        return response_model.model_validate_json(text)
    except ValidationError as exc:
        raise GeminiResponseError(
            f"{model} output did not match {response_model.__name__}: "
            f"{exc.error_count()} validation error(s)"
        ) from exc


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Return the process-wide Gemini client (one SDK connection pool per worker)."""
    return GeminiClient(get_settings())
