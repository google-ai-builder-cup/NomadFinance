from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import TypeVar

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from app.config import Settings, get_settings
from app.integrations.gemini.errors import (
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.integrations.gemini.model_tiers import ModelTier, model_for

logger = logging.getLogger(__name__)

ResponseT = TypeVar("ResponseT", bound=BaseModel)

_RETRYABLE = (GeminiRateLimitError, GeminiUnavailableError, GeminiTimeoutError)


class GeminiClient:
    """Single entry point for Gemini calls across all pillars.

    Picks the model from a `ModelTier`, forces structured output through a Pydantic
    `response_schema`, enforces a per-attempt timeout, retries transient failures
    with jittered exponential backoff, and logs token usage per call.

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
    ) -> ResponseT:
        """Run one Gemini call and return its output validated as `response_model`.

        Args:
            operation: Pipeline step label for logs and cost tracking, e.g. "contract.extract".
            tier: Workload tier; selects the model.
            contents: Prompt text and/or parts (e.g. `types.Part.from_bytes` for images, PDFs).
            response_model: Pydantic model used as the response schema and for validation.
            system_instruction: System prompt, loaded from the prompt library by the caller.
            temperature: Sampling temperature; None keeps the model default.

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
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_model,
            # No tools are ever passed, so the SDK's function-calling loop only adds log noise.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._settings.gemini_max_attempts),
            wait=wait_random_exponential(multiplier=1, max=self._max_backoff_seconds),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=_log_retry,
            reraise=True,
        )

        started = time.perf_counter()
        response: types.GenerateContentResponse = await retrying(
            self._call, model, contents, config
        )
        latency_ms = round((time.perf_counter() - started) * 1000)

        _log_usage(
            response,
            operation=operation,
            tier=tier,
            model=model,
            latency_ms=latency_ms,
            attempts=retrying.statistics.get("attempt_number", 1),
        )
        return _parse(response, response_model, model)

    async def _call(
        self,
        model: str,
        contents: types.ContentListUnion | types.ContentListUnionDict,
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        timeout = self._settings.gemini_timeout_seconds
        try:
            async with asyncio.timeout(timeout):
                return await self._sdk.aio.models.generate_content(
                    model=model, contents=contents, config=config
                )
        except TimeoutError as exc:
            raise GeminiTimeoutError(f"{model} did not respond within {timeout:g}s") from exc
        except genai_errors.ClientError as exc:
            # Only the code/status/message are kept: the raw response JSON can echo prompt data.
            detail = f"{model}: {exc.code} {exc.status} {exc.message}"
            if exc.code == 429:
                raise GeminiRateLimitError(detail) from exc
            raise GeminiRequestError(detail) from exc
        except genai_errors.ServerError as exc:
            raise GeminiUnavailableError(f"{model}: {exc.code} {exc.status} {exc.message}") from exc
        except httpx.TransportError as exc:
            raise GeminiUnavailableError(f"{model}: network error ({type(exc).__name__})") from exc


def _parse(
    response: types.GenerateContentResponse, response_model: type[ResponseT], model: str
) -> ResponseT:
    if isinstance(response.parsed, response_model):
        return response.parsed

    text = response.text
    if not text:
        raise GeminiResponseError(f"{model} returned no content ({_empty_reason(response)})")
    try:
        return response_model.model_validate_json(text)
    except ValidationError as exc:
        raise GeminiResponseError(
            f"{model} output did not match {response_model.__name__}: "
            f"{exc.error_count()} validation error(s)"
        ) from exc


def _empty_reason(response: types.GenerateContentResponse) -> str:
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason is not None:
        return f"prompt blocked: {feedback.block_reason}"
    if response.candidates and response.candidates[0].finish_reason is not None:
        return f"finish reason: {response.candidates[0].finish_reason}"
    return "no candidates"


def _log_usage(
    response: types.GenerateContentResponse,
    *,
    operation: str,
    tier: ModelTier,
    model: str,
    latency_ms: int,
    attempts: int,
) -> None:
    usage = response.usage_metadata
    fields = {
        "operation": operation,
        "tier": tier.value,
        "model": model,
        "prompt_tokens": usage.prompt_token_count if usage else None,
        "output_tokens": usage.candidates_token_count if usage else None,
        "thinking_tokens": usage.thoughts_token_count if usage else None,
        "total_tokens": usage.total_token_count if usage else None,
        "latency_ms": latency_ms,
        "attempts": attempts,
    }
    # Readable in plain-text logs now; `extra` carries the same fields for JSON logging.
    logger.info(
        "gemini_call %s",
        " ".join(f"{key}={value}" for key, value in fields.items()),
        extra={"gemini_usage": fields},
    )


def _log_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "gemini_retry attempt=%d error=%s: %s",
        retry_state.attempt_number,
        type(exc).__name__,
        exc,
    )


@lru_cache
def get_gemini_client() -> GeminiClient:
    """Return the process-wide Gemini client (one SDK connection pool per worker)."""
    return GeminiClient(get_settings())
