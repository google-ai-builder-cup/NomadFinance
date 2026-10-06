from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.errors import ErrorEnvelope

MOCKS = Path(__file__).resolve().parents[3] / "docs" / "mocks" / "conventions"
SSE_EVENTS = {"token", "slot_update", "done", "error"}


def _load(name: str) -> Any:
    return json.loads((MOCKS / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name", ["error-not-found.json", "error-validation-failed.json", "error-rate-limited.json"]
)
def test_error_mocks_match_the_envelope(name: str) -> None:
    mock = _load(name)
    envelope = ErrorEnvelope.model_validate(mock["body"])

    assert envelope.request_id == mock["headers"]["X-Request-ID"]


def test_idempotency_mock_errors_match_the_envelope() -> None:
    steps = _load("idempotency-exchange.json")["steps"]
    errors = [step["response"] for step in steps if step["response"]["status"] >= 400]

    assert {error["body"]["code"] for error in errors} == {
        "idempotency_key_reused",
        "request_in_progress",
        "idempotency_key_invalid",
    }
    for error in errors:
        envelope = ErrorEnvelope.model_validate(error["body"])
        assert envelope.request_id == error["headers"]["X-Request-ID"]


def test_pagination_mock_has_items_and_cursor() -> None:
    mock = _load("pagination-page.json")

    assert set(mock["body"]) == {"items", "next_cursor"}
    assert mock["last_page_body"] == {"items": [], "next_cursor": None}


def _events(name: str) -> list[tuple[str, dict[str, Any]]]:
    text = (MOCKS / name).read_text(encoding="utf-8")
    events: list[tuple[str, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if line and not line.startswith(":")]
        if not lines:
            continue  # a heartbeat comment
        assert lines[0].startswith("event: ") and lines[1].startswith("data: ")
        assert len(lines) == 2, "one data line per event"
        events.append((lines[0][7:], json.loads(lines[1][6:])))
    return events


def test_sse_streams_follow_the_event_rules() -> None:
    for name, terminal in (("sse-stream-done.sse", "done"), ("sse-stream-error.sse", "error")):
        events = _events(name)
        names = [event for event, _ in events]

        assert set(names) <= SSE_EVENTS
        assert names[-1] == terminal
        assert names.count("done") + names.count("error") == 1


def test_sse_error_event_is_the_envelope() -> None:
    event, data = _events("sse-stream-error.sse")[-1]

    assert event == "error"
    assert ErrorEnvelope.model_validate(data).details is None


def test_deprecation_mock_keeps_the_90_day_notice() -> None:
    from datetime import UTC, datetime
    from email.utils import parsedate_to_datetime

    headers = _load("deprecation-headers.json")["headers"]
    deprecated = datetime.fromtimestamp(int(headers["Deprecation"].lstrip("@")), UTC)
    sunset = parsedate_to_datetime(headers["Sunset"])

    assert (sunset - deprecated).days >= 90
