from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator

import pytest

from app.config import Settings
from app.core.logging import (
    JsonFormatter,
    RequestContext,
    TextFormatter,
    bind_user,
    configure_logging,
    reset_request_context,
    set_request_context,
)
from app.utils.hashing import hash_user_id

TRACE = "105445aa7843bc8bf206b12000100000"


def _record(
    message: str = "hello", *, extra: dict[str, object] | None = None, exc: bool = False
) -> logging.LogRecord:
    """A record built the way the logging module builds it, so the context fields exist."""
    logger = logging.getLogger("test.logging")
    exc_info = None
    if exc:
        try:
            raise ValueError("bad value")
        except ValueError:
            exc_info = sys.exc_info()
    record = logger.makeRecord("test.logging", logging.INFO, "f.py", 1, message, (), exc_info)
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


@pytest.fixture
def root_logger_restored() -> Iterator[logging.Logger]:
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return Settings()


def test_json_line_uses_cloud_logging_fields() -> None:
    line = JsonFormatter("proj-x").format(_record("hello"))

    payload = json.loads(line)
    assert payload["severity"] == "INFO"
    assert payload["message"] == "hello"
    assert payload["logger"] == "test.logging"
    assert "timestamp" in payload
    assert "request_id" not in payload
    assert "\n" not in line


def test_json_line_carries_request_context_and_trace() -> None:
    token = set_request_context(RequestContext("req-12345678", trace_id=TRACE))
    try:
        bind_user("some-uid")
        payload = json.loads(JsonFormatter("proj-x").format(_record()))
    finally:
        reset_request_context(token)

    assert payload["request_id"] == "req-12345678"
    assert payload["uid_hash"] == hash_user_id("some-uid")
    assert payload["logging.googleapis.com/trace"] == f"projects/proj-x/traces/{TRACE}"
    assert "some-uid" not in json.dumps(payload)


def test_json_line_includes_extra_fields_and_survives_odd_values() -> None:
    record = _record(extra={"gemini_usage": {"model": "m", "total_tokens": 7}, "odd": object()})

    payload = json.loads(JsonFormatter("proj-x").format(record))

    assert payload["gemini_usage"] == {"model": "m", "total_tokens": 7}
    assert isinstance(payload["odd"], str)


def test_json_line_puts_the_traceback_in_the_message() -> None:
    payload = json.loads(JsonFormatter("proj-x").format(_record("failed", exc=True)))

    assert payload["message"].startswith("failed\nTraceback")
    assert "ValueError: bad value" in payload["message"]


def test_text_line_shows_request_tags_only_inside_a_request() -> None:
    outside = TextFormatter().format(_record("hello"))
    token = set_request_context(RequestContext("req-12345678"))
    try:
        bind_user("some-uid")
        inside = TextFormatter().format(_record("hello"))
    finally:
        reset_request_context(token)

    assert outside.endswith("test.logging: hello")
    assert inside.endswith(f"hello [req=req-12345678 uid={hash_user_id('some-uid')}]")


def test_bind_user_outside_a_request_does_nothing() -> None:
    bind_user("some-uid")


def test_configure_logging_is_repeatable_and_applies_the_level(
    root_logger_restored: logging.Logger, settings: Settings
) -> None:
    configure_logging(settings)
    configure_logging(settings)

    ours = [h for h in root_logger_restored.handlers if getattr(h, "_nomadfinance_handler", False)]
    assert len(ours) == 1
    assert isinstance(ours[0].formatter, TextFormatter)
    assert root_logger_restored.level == logging.INFO


def test_configure_logging_uses_json_outside_local(
    root_logger_restored: logging.Logger, settings: Settings
) -> None:
    prod = settings.model_copy(update={"app_env": "prod"})

    configure_logging(prod)

    ours = [h for h in root_logger_restored.handlers if getattr(h, "_nomadfinance_handler", False)]
    assert isinstance(ours[0].formatter, JsonFormatter)


def test_http_client_url_logging_is_silenced_because_urls_can_hold_api_keys(
    root_logger_restored: logging.Logger, settings: Settings
) -> None:
    configure_logging(settings)

    assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
    assert not logging.getLogger("httpcore").isEnabledFor(logging.INFO)


def test_json_line_carries_the_requests_feature() -> None:
    token = set_request_context(RequestContext("req-12345678", feature="remittance"))
    try:
        payload = json.loads(JsonFormatter("proj-x").format(_record()))
    finally:
        reset_request_context(token)

    assert payload["feature"] == "remittance"


def test_a_gemini_lines_own_feature_beats_the_requests() -> None:
    token = set_request_context(RequestContext("req-12345678", feature="platform"))
    try:
        record = _record(extra={"gemini_usage": {"feature": "contract", "model": "m"}})
        payload = json.loads(JsonFormatter("proj-x").format(record))
    finally:
        reset_request_context(token)

    assert payload["feature"] == "contract"
    assert payload["gemini_usage"]["feature"] == "contract"


def test_a_line_outside_any_request_has_no_feature() -> None:
    payload = json.loads(JsonFormatter("proj-x").format(_record()))

    assert "feature" not in payload
    assert "uid_hash" not in payload


def test_text_line_shows_the_feature_too() -> None:
    token = set_request_context(RequestContext("req-12345678", feature="radar"))
    try:
        line = TextFormatter().format(_record("hello"))
    finally:
        reset_request_context(token)

    assert line.endswith("hello [req=req-12345678 feature=radar]")
