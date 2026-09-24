from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.integrations.gemini import (
    GeminiError,
    GeminiRateLimitError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)

logger = logging.getLogger(__name__)

# Quota exhaustion is our capacity problem, not the caller's, so it maps to 503, not 429.
# GeminiRequestError and anything unlisted fall through to 500: that is a bug on our side.
_GEMINI_ERROR_RESPONSES: list[tuple[type[GeminiError], int, str]] = [
    (
        GeminiRateLimitError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The AI service is busy. Please try again in a minute.",
    ),
    (
        GeminiUnavailableError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The AI service is temporarily unavailable. Please try again.",
    ),
    (
        GeminiTimeoutError,
        status.HTTP_504_GATEWAY_TIMEOUT,
        "The AI service took too long to respond. Please try again.",
    ),
    (
        GeminiResponseError,
        status.HTTP_502_BAD_GATEWAY,
        "The AI service returned an unusable answer. Please try again.",
    ),
]
_RETRY_AFTER_SECONDS = "30"


def _response_for(exc: Exception) -> tuple[int, str]:
    for error_type, status_code, message in _GEMINI_ERROR_RESPONSES:
        if isinstance(exc, error_type):
            return status_code, message
    return status.HTTP_500_INTERNAL_SERVER_ERROR, "Document processing failed."


async def gemini_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn a `GeminiError` into a short JSON error without internals or a traceback."""
    status_code, message = _response_for(exc)
    # The exception text holds model, status code and API message only, never prompt data.
    logger.warning(
        "gemini_error path=%s status=%d error=%s: %s",
        request.url.path,
        status_code,
        type(exc).__name__,
        exc,
    )
    headers = (
        {"Retry-After": _RETRY_AFTER_SECONDS}
        if status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        else None
    )
    return JSONResponse(status_code=status_code, content={"detail": message}, headers=headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the app-wide exception handlers."""
    app.add_exception_handler(GeminiError, gemini_error_handler)
