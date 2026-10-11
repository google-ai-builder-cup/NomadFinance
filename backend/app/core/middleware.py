from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response, is_v2_path
from app.core.features import feature_for_path
from app.core.logging import (
    REQUEST_ID_HEADER,
    RequestContext,
    reset_request_context,
    set_request_context,
)

logger = logging.getLogger(__name__)

# A caller's own id is reused so one id can follow a request across systems, but only in a
# shape that cannot forge log lines or fill the logs with junk.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
# Cloud Run sends "TRACE_ID/SPAN_ID;o=1"; the trace id is 32 hex characters.
_TRACE_ID = re.compile(r"^([0-9a-f]{32})/", re.IGNORECASE)

# Probes hit these constantly; at INFO they would bury the real traffic.
_QUIET_PATHS = frozenset({"/health"})

# A v2 JSON body is a short answer: at most a 4,000-character message, which is under 50 KB even
# when every character is escaped. A screenshot is multipart and keeps the upload cap.
V2_JSON_MAX_BYTES = 128 * 1024


class RequestLoggingMiddleware:
    """Give every request an id and write one `request_completed` line when it ends.

    Plain ASGI rather than BaseHTTPMiddleware, which runs the app in another task and would
    hide the user id that the auth dependency records. Logs the path only: never the query
    string, headers or body, which can hold tokens and personal data.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        supplied = headers.get(REQUEST_ID_HEADER, "")
        trace = _TRACE_ID.match(headers.get("x-cloud-trace-context", ""))
        context = RequestContext(
            request_id=supplied if _VALID_REQUEST_ID.match(supplied) else uuid.uuid4().hex,
            trace_id=trace.group(1).lower() if trace else None,
            feature=feature_for_path(scope["path"]),
        )
        # The 500 handler runs outside this middleware, after the context var is reset, so the
        # id is also kept on the scope for error responses to read.
        scope.setdefault("state", {})["request_id"] = context.request_id
        token = set_request_context(context)
        started = time.perf_counter()
        status_code: int | None = None
        error: Exception | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, context.request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            # Clients get only a generic 500 (Starlette); the traceback stays in our logs.
            error = exc
            status_code = 500
            raise
        finally:
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            path = scope["path"]
            fields = {
                "method": scope["method"],
                "path": path,
                "status": status_code,
                "latency_ms": latency_ms,
            }
            if error is not None:
                level = logging.ERROR
            elif path in _QUIET_PATHS:
                level = logging.DEBUG
            else:
                level = logging.ERROR if (status_code or 0) >= 500 else logging.INFO
            logger.log(
                level,
                "request_completed %s",
                " ".join(f"{key}={value}" for key, value in fields.items()),
                # `status_class` ("2xx", "4xx", "5xx") is only a field, not in the message: the
                # per-feature error metric (NF-F0-016) filters on it without parsing text.
                extra=fields | {"status_class": f"{(status_code or 0) // 100}xx"},
                exc_info=error,
            )
            reset_request_context(token)


class BodySizeLimitMiddleware:
    """Refuse request bodies over `max_bytes` before they are read (413).

    FastAPI parses a whole multipart form into a temporary file before the endpoint can check
    the size, so without this an upload endpoint would receive up to Cloud Run's 32 MB. A
    declared Content-Length is rejected at once; a body without one is counted as it arrives.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    @staticmethod
    def _message(limit: int) -> str:
        size = (
            f"{limit // 1024} KB" if limit == V2_JSON_MAX_BYTES else f"{limit // (1024 * 1024)} MB"
        )
        return f"The request is larger than {size}."

    def _limit_for(self, scope: Scope) -> int:
        """The cap for this request: a short one for v2 JSON, the upload cap for the rest."""
        content_type = Headers(scope=scope).get("content-type", "").split(";")[0].strip().lower()
        if is_v2_path(scope["path"]) and content_type == "application/json":
            return min(self.max_bytes, V2_JSON_MAX_BYTES)
        return self.max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit_for(scope)
        declared = Headers(scope=scope).get("content-length", "")
        if declared.isdigit() and int(declared) > limit:
            if is_v2_path(scope["path"]):
                response: Response = error_response(
                    scope, 413, "payload_too_large", self._message(limit)
                )
            else:
                response = JSONResponse(status_code=413, content={"detail": self._message(limit)})
            await response(scope, receive, send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # FastAPI re-raises an HTTPException from body parsing unchanged.
                    raise HTTPException(413, self._message(limit))
            return message

        await self.app(scope, counting_receive, send)


class SecurityHeadersMiddleware:
    """Keep what a browser or a cache does with an answer from becoming a leak.

    Every answer says its type is not to be guessed. An answer under `/api/` that does not choose
    its own `Cache-Control` is marked `no-store`: it holds a worker's pay, debts or messages, and
    a phone is often shared. An answer that sets its own (the plan PDF, a stream) keeps it.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        private = scope["path"].startswith("/api/")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                if private:
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)
