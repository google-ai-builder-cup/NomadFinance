from __future__ import annotations

import asyncio
import logging
import math
import time
from functools import partial

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from app.config import Settings
from app.integrations.gemini.budget import EMBEDDING_TIER, GeminiBudget
from app.integrations.gemini.errors import (
    GeminiBudgetExhaustedError,
    GeminiError,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
    is_retryable,
)
from app.integrations.gemini.sdk_errors import is_daily_quota
from app.integrations.gemini.usage import feature_of, log_failure, log_retry

logger = logging.getLogger(__name__)

# Firestore vectors are capped at 2048 numbers and gemini-embedding-001 returns 3072 by
# default, so every request asks for 768 (docs/data-model/collections/radar.md).
EMBEDDING_DIMENSION = 768


async def embed_text(
    sdk: genai.Client,
    settings: Settings,
    text: str,
    *,
    operation: str,
    max_backoff_seconds: float = 8.0,
    budget: GeminiBudget | None = None,
) -> list[float]:
    """Embed `text` as one normalized `EMBEDDING_DIMENSION`-number vector.

    Raises:
        GeminiRequestError: The request was rejected; retrying will not help.
        GeminiRateLimitError: Still rate limited after all attempts.
        GeminiUnavailableError: Server or network errors on every attempt.
        GeminiTimeoutError: Every attempt timed out.
        GeminiResponseError: The answer had no vector, or one of the wrong size.
    """
    model = settings.gemini_model_embedding
    retrying = AsyncRetrying(
        stop=stop_after_attempt(settings.gemini_max_attempts),
        wait=wait_random_exponential(multiplier=1, max=max_backoff_seconds),
        retry=retry_if_exception(is_retryable),
        # Every attempt counts against the embedding model's daily quota (NF-F0-016).
        before_sleep=partial(log_retry, operation=operation, tier=None, model=model),
        reraise=True,
    )
    started = time.perf_counter()
    try:
        response: types.EmbedContentResponse = await retrying(
            _attempt, sdk, settings, text, budget or GeminiBudget(), feature_of(operation)
        )
    except GeminiBudgetExhaustedError:
        raise  # refused before a request was made; the budget logged it (see client._run)
    except GeminiError as exc:
        log_failure(
            exc,
            operation=operation,
            tier=None,
            model=model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            attempts=retrying.statistics.get("attempt_number", 1),
        )
        raise
    latency_ms = round((time.perf_counter() - started) * 1000)

    values = response.embeddings[0].values if response.embeddings else None
    if not values or len(values) != EMBEDDING_DIMENSION:
        raise GeminiResponseError(f"{model} returned no {EMBEDDING_DIMENSION}-number vector")
    # No token counts in an embedding response, so input size stands in for cost tracking.
    logger.info(
        "gemini_call operation=%s feature=%s model=%s input_chars=%d latency_ms=%d attempts=%d",
        operation,
        feature_of(operation),
        model,
        len(text),
        latency_ms,
        retrying.statistics.get("attempt_number", 1),
        extra={
            "gemini_usage": {
                "operation": operation,
                "feature": feature_of(operation),
                "tier": None,
                "model": model,
                "input_chars": len(text),
                "latency_ms": latency_ms,
                "attempts": retrying.statistics.get("attempt_number", 1),
            }
        },
    )
    return _normalize(values, model)


async def _attempt(
    sdk: genai.Client, settings: Settings, text: str, budget: GeminiBudget, feature: str
) -> types.EmbedContentResponse:
    async with budget.attempt(feature, EMBEDDING_TIER):
        return await _call(sdk, settings, text)


async def _call(sdk: genai.Client, settings: Settings, text: str) -> types.EmbedContentResponse:
    model = settings.gemini_model_embedding
    timeout = settings.gemini_timeout_seconds
    try:
        async with asyncio.timeout(timeout):
            return await sdk.aio.models.embed_content(
                model=model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY", output_dimensionality=EMBEDDING_DIMENSION
                ),
            )
    except TimeoutError as exc:
        raise GeminiTimeoutError(f"{model} did not respond within {timeout:g}s") from exc
    except genai_errors.ClientError as exc:
        detail = f"{model}: {exc.code} {exc.status} {exc.message}"
        if exc.code == 429:
            raise GeminiRateLimitError(detail, daily=is_daily_quota(exc.details)) from exc
        raise GeminiRequestError(detail) from exc
    except genai_errors.ServerError as exc:
        raise GeminiUnavailableError(f"{model}: {exc.code} {exc.status} {exc.message}") from exc
    except httpx.TransportError as exc:
        raise GeminiUnavailableError(f"{model}: network error ({type(exc).__name__})") from exc


def _normalize(values: list[float], model: str) -> list[float]:
    # Shortened vectors are not unit length; cosine search needs them to be.
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0:
        raise GeminiResponseError(f"{model} returned an all-zero vector")
    return [v / norm for v in values]
