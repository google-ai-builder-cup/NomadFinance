"""Shared by the Coach mock tests (NF-FC-002): the mock files and ways to read them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
MOCKS = REPO / "docs" / "mocks" / "coach"
JSON_FILES = sorted(MOCKS.glob("*.json"))
SSE_FILES = sorted(MOCKS.glob("*.sse"))


def load(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def is_success(path: Path) -> bool:
    return bool(load(path)["status"] < 400)


def _bodies(request_prefix: str) -> dict[str, dict[str, Any]]:
    """Success bodies of the mocks whose request starts with the prefix, by id."""
    found = {}
    for path in JSON_FILES:
        mock = load(path)
        if mock["status"] < 400 and mock["request"].startswith(request_prefix):
            found[mock["body"]["id"]] = mock["body"]
    return found


def sessions_by_id() -> dict[str, dict[str, Any]]:
    """Every session the `GET /sessions/{id}` mocks show, by id."""
    return _bodies("GET /api/v2/coach/sessions/")


def plans_by_key() -> dict[str, dict[str, Any]]:
    """Every plan body of a success mock, by `<id>/<language>` (the same plan may appear twice)."""
    found = {}
    for path in JSON_FILES:
        mock = load(path)
        if mock["status"] < 400 and "/plan" in mock["request"].split("?")[0].split("coach")[1]:
            body = mock["body"]
            found[f"{body['id']}/{body['language']}"] = body
    return found


def stream_events(path: Path) -> list[tuple[str, dict[str, Any]]]:
    """The events of a stream file, in order, without the heartbeats (which must be `: ping`)."""
    text = path.read_text(encoding="utf-8")
    found: list[tuple[str, dict[str, Any]]] = []
    for block in text.split("\n\n"):
        lines = [line for line in block.splitlines() if line]
        if all(line.startswith(":") for line in lines):
            assert all(line == ": ping" for line in lines)
            continue
        assert lines[0].startswith("event: ") and lines[1].startswith("data: ")
        assert len(lines) == 2, "one data line per event"
        found.append((lines[0][7:], json.loads(lines[1][6:])))
    return found
