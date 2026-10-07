"""A worker's stored checks: the history list and one check (NF-SA-012)."""

from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.schemas.scam import ScamCheckDetail, ScamCheckListResponse, ScamCheckSummary
from app.services.scam.check_store import (
    CheckStore,
    StoredCheckUnreadableError,
    from_document,
    is_expired,
)
from app.utils.hashing import hash_user_id

EXCERPT_CHARS = 140
# What an id can look like (32 hex today). Anything else cannot be a check of ours, and a path
# like `..` would make the Firestore client raise instead of answering "not found".
_CHECK_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def valid_check_id(check_id: str) -> bool:
    """Whether `check_id` could be one of ours (the report route checks it too)."""
    return _CHECK_ID.match(check_id) is not None


class CheckNotFoundError(LookupError):
    """No such check for this worker: unknown, expired, or someone else's. All look the same."""


class InvalidCursorError(ValueError):
    """A cursor this worker was not given: malformed, altered, or issued to someone else."""


def encode_cursor(uid: str, created_at: datetime) -> str:
    """An opaque position in the history: the `created_at` of the last row, tied to the worker.

    It names no document and widens nothing: the query is always the caller's own collection,
    and the worker's hash only makes a cursor from another worker's page fail.
    """
    payload = {"u": hash_user_id(uid), "t": created_at.isoformat()}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


def decode_cursor(uid: str, cursor: str) -> datetime:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        payload: Any = json.loads(raw)
        position = datetime.fromisoformat(payload["t"])
        owner = payload["u"]
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError from exc
    if owner != hash_user_id(uid) or position.tzinfo is None:
        raise InvalidCursorError
    return position


def _summary(check: ScamCheckDetail) -> ScamCheckSummary:
    return ScamCheckSummary(
        id=check.id,
        created_at=check.created_at,
        input_type=check.input_type,
        language=check.language,
        is_scam=check.verdict.is_scam,
        scam_type=check.verdict.scam_type,
        risk_level=check.verdict.risk_level,
        confidence=check.verdict.confidence,
        excerpt=check.redacted_text[:EXCERPT_CHARS],
        reported=check.reported,
    )


async def list_checks(
    store: CheckStore, uid: str, *, limit: int, cursor: str | None, now: datetime
) -> ScamCheckListResponse:
    """The worker's checks, newest first. A page can hold fewer than `limit` rows (an expired or
    unreadable one is left out); only `next_cursor: null` means the end."""
    before = decode_cursor(uid, cursor) if cursor else None
    # One more than asked for shows whether another page exists without a second query.
    rows = await run_in_threadpool(store.checks.list_newest, uid, limit + 1, before=before)
    page = rows[:limit]
    items: list[ScamCheckSummary] = []
    for check_id, document in page:
        if is_expired(document, now):
            continue
        try:
            items.append(_summary(from_document(check_id, document)))
        except StoredCheckUnreadableError:
            continue
    more = len(rows) > limit and isinstance(page[-1][1].get("created_at"), datetime)
    return ScamCheckListResponse(
        items=items, next_cursor=encode_cursor(uid, page[-1][1]["created_at"]) if more else None
    )


async def get_check(store: CheckStore, uid: str, check_id: str, now: datetime) -> ScamCheckDetail:
    """One stored check with `seen` read live. Raises `CheckNotFoundError` for anything absent."""
    if not _CHECK_ID.match(check_id):
        raise CheckNotFoundError(check_id)
    document = await run_in_threadpool(store.checks.get, uid, check_id)
    if document is None or is_expired(document, now):
        raise CheckNotFoundError(check_id)
    try:
        check = from_document(check_id, document)
    except StoredCheckUnreadableError as exc:
        raise CheckNotFoundError(check_id) from exc
    return check.model_copy(update={"indicators": await store.with_seen(check.indicators)})
