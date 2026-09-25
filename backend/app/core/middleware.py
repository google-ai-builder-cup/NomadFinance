from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import RequestContext, reset_request_context, set_request_context

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

# A caller's own id is reused so one id can follow a request across systems, but only in a
# shape that cannot forge log lines or fill the logs with junk.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
# Cloud Run sends "TRACE_ID/SPAN_ID;o=1"; the trace id is 32 hex characters.
_TRACE_ID = re.compile(r"^([0-9a-f]{32})/", re.IGNORECASE)

# Probes hit these constantly; at INFO they would bury the real traffic.
_QUIET_PATHS = frozenset({"/health"})


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
        )
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
                extra=fields,
                exc_info=error,
            )
            reset_request_context(token)
