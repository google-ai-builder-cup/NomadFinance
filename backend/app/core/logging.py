from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.config import Settings
from app.utils.hashing import hash_user_id

_CONTEXT_FIELDS = ("request_id", "user_hash", "trace_id")

# Attributes every LogRecord has; anything else on a record came in through `extra=`.
# color_message is uvicorn's copy of its message with terminal colour codes.
_STANDARD_RECORD_FIELDS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
    "taskName",
    "color_message",
}

_HANDLER_MARK = "_nomadfinance_handler"
_QUIET_LIBRARIES = ("httpx", "httpcore")


@dataclass
class RequestContext:
    """Who and what the current request is, shared by every log line written during it."""

    request_id: str
    trace_id: str | None = None
    user_hash: str | None = None


# Holds a mutable object rather than plain values: the user is only known after the auth
# dependency runs, possibly in a different task than the middleware that logs the result.
_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def set_request_context(context: RequestContext) -> Token[RequestContext | None]:
    return _request_context.set(context)


def reset_request_context(token: Token[RequestContext | None]) -> None:
    _request_context.reset(token)


def bind_user(uid: str) -> None:
    """Tag the rest of this request's log lines with the caller's hashed uid."""
    context = _request_context.get()
    if context is not None:
        context.user_hash = hash_user_id(uid)


def _install_record_factory() -> None:
    previous = logging.getLogRecordFactory()
    if getattr(previous, _HANDLER_MARK, False):
        return

    # A record factory (not a handler filter) so the fields exist on the record no matter
    # which handler sees it, including pytest's caplog.
    def factory(*args: Any, **kwargs: Any) -> logging.LogRecord:
        record = previous(*args, **kwargs)
        context = _request_context.get()
        for field in _CONTEXT_FIELDS:
            setattr(record, field, getattr(context, field, None))
        return record

    setattr(factory, _HANDLER_MARK, True)
    logging.setLogRecordFactory(factory)


class JsonFormatter(logging.Formatter):
    """One JSON object per line, in the field names Cloud Logging understands."""

    def __init__(self, project_id: str) -> None:
        super().__init__()
        self._project_id = project_id

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            # Error Reporting groups failures by the stack trace found inside `message`.
            message = f"{message}\n{self.formatException(record.exc_info)}"
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": message,
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "logger": record.name,
        }
        for field in ("request_id", "user_hash"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        trace_id = getattr(record, "trace_id", None)
        if trace_id is not None:
            # Links the line to the Cloud Run request log in the Logs Explorer.
            payload["logging.googleapis.com/trace"] = (
                f"projects/{self._project_id}/traces/{trace_id}"
            )
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and key not in _CONTEXT_FIELDS:
                payload.setdefault(key, value)
        return json.dumps(payload, default=str, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Readable lines for local development, with the request id where there is one."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)-7s %(name)s: %(message)s%(request_tags)s")

    def format(self, record: logging.LogRecord) -> str:
        tags = [
            f"{name}={getattr(record, field)}"
            for name, field in (("req", "request_id"), ("user", "user_hash"))
            if getattr(record, field, None)
        ]
        record.request_tags = f" [{' '.join(tags)}]" if tags else ""
        return super().format(record)


def configure_logging(settings: Settings) -> None:
    """Send all logs to stdout: JSON on Cloud Run, readable text for local development.

    Safe to call again (tests build many apps): it replaces only the handler it added.
    """
    _install_record_factory()

    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(
        TextFormatter()
        if settings.app_env == "local"
        else JsonFormatter(settings.firebase_project_id)
    )

    root = logging.getLogger()
    for existing in [h for h in root.handlers if getattr(h, _HANDLER_MARK, False)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # uvicorn's own handlers would print a second, differently shaped copy of every line.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # The request middleware logs each request with more detail, so uvicorn's access line is noise.
    logging.getLogger("uvicorn.access").disabled = True

    # httpx logs every outbound URL at INFO, query string included, and the CurrencyFreaks
    # API key travels in its query string. Warnings and errors still come through.
    for name in _QUIET_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)
