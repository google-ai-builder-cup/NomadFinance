"""Small helpers shared by the demo loaders."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def parse_iso(value: str) -> datetime:
    """An ISO datetime as written by the backend's test builders (`...Z`), in UTC."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def shift_times(node: Any, delta: timedelta) -> Any:
    """`node` with every full ISO datetime string moved by `delta` and returned as a datetime.

    Dates without a time (`2026-11-01`) are left alone: they are not instants, and the loader
    sets them from the day it runs.
    """
    if isinstance(node, dict):
        return {key: shift_times(value, delta) for key, value in node.items()}
    if isinstance(node, list):
        return [shift_times(value, delta) for value in node]
    if isinstance(node, str) and _ISO_DATETIME.match(node):
        return parse_iso(node) + delta
    return node


def replace_value(node: Any, old: str, new: str) -> Any:
    """`node` with every string equal to `old` replaced by `new` (the departure day)."""
    if isinstance(node, dict):
        return {key: replace_value(value, old, new) for key, value in node.items()}
    if isinstance(node, list):
        return [replace_value(value, old, new) for value in node]
    return new if node == old else node
