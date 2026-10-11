from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

from app.core.logging import REQUEST_ID_HEADER
from app.integrations.gemini import (
    GeminiBudgetExhaustedError,
    GeminiError,
    GeminiRateLimitError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.integrations.gemini.budget import seconds_until_reset
from app.schemas.errors import ErrorDetail, ErrorEnvelope

logger = logging.getLogger(__name__)

# Quota exhaustion is our capacity problem, not the caller's, so it maps to 503, not 429.
# GeminiRequestError and anything unlisted fall through to 500: that is a bug on our side.
# The third field is the `/api/v2` error code; v1 only looks at the status and message.
_GEMINI_ERROR_RESPONSES: list[tuple[type[GeminiError], int, str, str]] = [
    (
        GeminiRateLimitError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "ai_busy",
        "The AI service is busy. Please try again in a minute.",
    ),
    (
        GeminiUnavailableError,
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "ai_unavailable",
        "The AI service is temporarily unavailable. Please try again.",
    ),
    (
        GeminiTimeoutError,
        status.HTTP_504_GATEWAY_TIMEOUT,
        "ai_timeout",
        "The AI service took too long to respond. Please try again.",
    ),
    (
        GeminiResponseError,
        status.HTTP_502_BAD_GATEWAY,
        "ai_bad_response",
        "The AI service returned an unusable answer. Please try again.",
    ),
]
_RETRY_AFTER_SECONDS = "30"
# A spent daily quota is still `ai_busy` (the v2 contract has no other code for it, and the
# client shows its "try later" text for it), but "in a minute" would be wrong.
_DAILY_LIMIT_MESSAGE = "The AI service has reached its limit for today. Please try again later."

V2_PREFIX = "/api/v2"
_INTERNAL_MESSAGE = "Something went wrong. Please try again."
# Status to code for errors raised as a plain HTTPException; `ApiError` carries its own.
_STATUS_CODES = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    413: "payload_too_large",
    422: "validation_failed",
    429: "rate_limited",
}
_MAX_DETAILS = 20
_MAX_ISSUE_LENGTH = 200


class ApiError(HTTPException):
    """An HTTPException that also names its `/api/v2` error code.

    Raise it where the status alone is ambiguous (e.g. 409 `request_in_progress`). On a v1
    route it behaves like any HTTPException and `code` is ignored.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code


def is_v2_path(path: str) -> bool:
    return path == V2_PREFIX or path.startswith(V2_PREFIX + "/")


def request_id_from_scope(scope: Scope) -> str:
    """The id `RequestLoggingMiddleware` gave this request; a fresh one if it did not run."""
    request_id = (scope.get("state") or {}).get("request_id")
    return request_id if isinstance(request_id, str) else uuid.uuid4().hex


def error_response(
    scope: Scope,
    status_code: int,
    code: str,
    message: str,
    *,
    details: list[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the `/api/v2` error body: `{code, message, request_id}` plus optional details."""
    envelope = ErrorEnvelope(
        code=code, message=message, request_id=request_id_from_scope(scope), details=details
    )
    return JSONResponse(
        status_code=status_code, content=envelope.model_dump(exclude_none=True), headers=headers
    )


def _is_daily_limit(exc: Exception) -> bool:
    return isinstance(exc, GeminiRateLimitError) and exc.daily


def _retry_after(exc: Exception) -> str:
    """Seconds until the daily quota is back for a spent day; the short wait otherwise."""
    if isinstance(exc, GeminiBudgetExhaustedError):
        return str(exc.retry_after_seconds)
    if _is_daily_limit(exc):
        return str(seconds_until_reset(datetime.now(UTC)))
    return _RETRY_AFTER_SECONDS


def _response_for(exc: Exception) -> tuple[int, str, str]:
    if _is_daily_limit(exc):
        return status.HTTP_503_SERVICE_UNAVAILABLE, "ai_busy", _DAILY_LIMIT_MESSAGE
    for error_type, status_code, code, message in _GEMINI_ERROR_RESPONSES:
        if isinstance(exc, error_type):
            return status_code, code, message
    return status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Document processing failed."


def error_parts(exc: Exception) -> tuple[int, str, str]:
    """Status, `/api/v2` code and message for an error that reaches a client as an `error` event.

    A Gemini failure keeps its `ai_*` code; anything else is `internal_error` with the neutral
    text, never the exception's own.
    """
    status_code, code, message = _response_for(exc)
    return status_code, code, _INTERNAL_MESSAGE if code == "internal_error" else message


async def gemini_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Turn a `GeminiError` into a short JSON error without internals or a traceback."""
    status_code, code, message = _response_for(exc)
    # The exception text holds model, status code and API message only, never prompt data.
    logger.warning(
        "gemini_error path=%s status=%d error=%s: %s",
        request.url.path,
        status_code,
        type(exc).__name__,
        exc,
    )
    headers = (
        {"Retry-After": _retry_after(exc)}
        if status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        else None
    )
    if is_v2_path(request.url.path):
        # The v1 text for an unlisted error says "Document", which v2 features are not.
        if code == "internal_error":
            message = _INTERNAL_MESSAGE
        return error_response(request.scope, status_code, code, message, headers=headers)
    return JSONResponse(status_code=status_code, content={"detail": message}, headers=headers)


async def http_error_handler(request: Request, exc: Exception) -> Response:
    """Wrap an HTTPException in the `/api/v2` envelope; v1 keeps FastAPI's `{"detail"}`."""
    assert isinstance(exc, StarletteHTTPException)
    if not is_v2_path(request.url.path):
        return await http_exception_handler(request, exc)
    code = exc.code if isinstance(exc, ApiError) else _STATUS_CODES.get(exc.status_code)
    if code is None:
        code = "bad_request" if exc.status_code < 500 else "internal_error"
    message = exc.detail if isinstance(exc.detail, str) else _INTERNAL_MESSAGE
    return error_response(request.scope, exc.status_code, code, message, headers=exc.headers)


async def validation_error_handler(request: Request, exc: Exception) -> Response:
    """List which fields failed on `/api/v2`, without echoing what was sent.

    FastAPI's default 422 repeats the rejected value, and a NaN in it cannot be written as
    JSON (D-63), so the v2 body reads only the path and reason of each error.
    """
    assert isinstance(exc, RequestValidationError)
    if not is_v2_path(request.url.path):
        return await request_validation_exception_handler(request, exc)
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            issue=str(error["msg"])[:_MAX_ISSUE_LENGTH],
        )
        for error in exc.errors()[:_MAX_DETAILS]
    ]
    return error_response(
        request.scope,
        422,
        "validation_failed",
        "The request is not valid.",
        details=details,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> Response:
    """Answer an uncaught exception without its text; the traceback is already in the logs."""
    if not is_v2_path(request.url.path):
        # Same body Starlette sends when no handler is registered.
        return PlainTextResponse("Internal Server Error", status_code=500)
    # This runs outside RequestLoggingMiddleware, so its X-Request-ID header is not added.
    return error_response(
        request.scope,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        _INTERNAL_MESSAGE,
        headers={REQUEST_ID_HEADER: request_id_from_scope(request.scope)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the app-wide exception handlers."""
    app.add_exception_handler(GeminiError, gemini_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
