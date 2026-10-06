from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
from google.genai import errors as genai_errors
from google.genai import types

from app.integrations.gemini.errors import (
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)


def is_daily_quota(details: object) -> bool:
    """Whether a 429's details name a per-day quota (a `quotaId` such as
    "GenerateRequestsPerDayPerProjectPerModel-FreeTier"). Only quota ids are read: the rest of
    the response can echo prompt data."""
    pending: list[object] = [details]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key == "quotaId" and isinstance(value, str) and "PerDay" in value:
                    return True
                pending.append(value)
        elif isinstance(item, list):
            pending.extend(item)
    return False


def empty_reason(response: types.GenerateContentResponse | None) -> str:
    """Why an answer has no text, for the error message."""
    if response is None:
        return "no candidates"
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason is not None:
        return f"prompt blocked: {feedback.block_reason}"
    if response.candidates and response.candidates[0].finish_reason is not None:
        return f"finish reason: {response.candidates[0].finish_reason}"
    return "no candidates"


@contextmanager
def translate_sdk_errors(model: str, timeout: float) -> Iterator[None]:
    """Raise the client's own errors for what the SDK, `asyncio.timeout` and httpx raise.

    Put it outside the `asyncio.timeout(timeout)` block, so the expired timeout is what it sees.
    Used for a whole call and for each step of a stream.
    """
    try:
        yield
    except TimeoutError as exc:
        raise GeminiTimeoutError(f"{model} did not respond within {timeout:g}s") from exc
    except genai_errors.ClientError as exc:
        # Only the code/status/message are kept: the raw response JSON can echo prompt data.
        detail = f"{model}: {exc.code} {exc.status} {exc.message}"
        if exc.code == 429:
            raise GeminiRateLimitError(detail, daily=is_daily_quota(exc.details)) from exc
        raise GeminiRequestError(detail) from exc
    except genai_errors.ServerError as exc:
        raise GeminiUnavailableError(f"{model}: {exc.code} {exc.status} {exc.message}") from exc
    except httpx.TransportError as exc:
        raise GeminiUnavailableError(f"{model}: network error ({type(exc).__name__})") from exc
