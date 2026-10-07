"""The history list, one check, and the cursor (NF-SA-012)."""

from __future__ import annotations

import base64
import json
from datetime import timedelta
from typing import Any

import pytest

from app.schemas.scam import ScamCheckSummary
from app.services.scam.check_store import CHECK_TTL
from app.services.scam.history import (
    EXCERPT_CHARS,
    CheckNotFoundError,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
    get_check,
    list_checks,
)
from tests.fixtures.scam_checks import (
    NOW,
    FakeCheckRepo,
    FakeIndicatorRepo,
    make_store,
    mock_check,
    put_check,
)

pytestmark = pytest.mark.anyio

UID = "worker-1"
LATER = NOW + timedelta(days=1)


def _put(repo: FakeCheckRepo, n: int, uid: str = UID, **changes: Any) -> str:
    """The n-th check of a worker: each a different message, made `n` hours after the first."""
    created = NOW + timedelta(hours=n)
    check = mock_check(
        redacted_text=f"Pay the processing fee number {n} today",
        created_at=created,
        expires_at=created + CHECK_TTL,
    )
    return put_check(repo, uid, check, **changes)


# --- the cursor --------------------------------------------------------------------------------


def test_a_cursor_round_trips_and_is_opaque() -> None:
    cursor = encode_cursor(UID, NOW)

    assert decode_cursor(UID, cursor) == NOW
    assert UID not in cursor and "2026" not in cursor  # not readable, names no worker


def test_a_cursor_from_another_worker_is_refused() -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor("worker-2", encode_cursor(UID, NOW))


@pytest.mark.parametrize(
    "garbage",
    [
        "",
        "not base64 at all!!",
        base64.urlsafe_b64encode(b"not json").decode(),
        base64.urlsafe_b64encode(b"[1, 2]").decode(),
        base64.urlsafe_b64encode(json.dumps({"u": "x"}).encode()).decode(),
        base64.urlsafe_b64encode(json.dumps({"u": "x", "t": "yesterday"}).encode()).decode(),
    ],
)
def test_a_cursor_that_was_never_issued_is_refused(garbage: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(UID, garbage)


def test_a_cursor_with_a_time_that_has_no_zone_is_refused() -> None:
    from app.utils.hashing import hash_user_id

    naive = {"u": hash_user_id(UID), "t": "2026-11-05T09:00:00"}
    cursor = base64.urlsafe_b64encode(json.dumps(naive).encode()).decode()

    with pytest.raises(InvalidCursorError):
        decode_cursor(UID, cursor)


# --- the list ----------------------------------------------------------------------------------


async def test_an_empty_history_is_an_empty_list_and_the_end() -> None:
    page = await list_checks(make_store(), UID, limit=20, cursor=None, now=LATER)

    assert page.items == [] and page.next_cursor is None


async def test_the_history_is_newest_first_and_pages_without_gaps_or_repeats() -> None:
    repo = FakeCheckRepo()
    ids = [_put(repo, n) for n in range(5)]  # oldest first
    store = make_store(repo)

    seen: list[str] = []
    cursor = None
    for _ in range(5):
        page = await list_checks(store, UID, limit=2, cursor=cursor, now=LATER)
        seen += [item.id for item in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break

    assert seen == list(reversed(ids))
    assert cursor is None


async def test_a_page_that_is_exactly_the_rest_has_no_next_cursor() -> None:
    repo = FakeCheckRepo()
    [_put(repo, n) for n in range(3)]

    page = await list_checks(make_store(repo), UID, limit=3, cursor=None, now=LATER)

    assert len(page.items) == 3 and page.next_cursor is None


async def test_a_row_carries_the_headline_and_an_excerpt_and_nothing_more() -> None:
    repo = FakeCheckRepo()
    check = mock_check(redacted_text="x" * 300)
    put_check(repo, UID, check)

    page = await list_checks(make_store(repo), UID, limit=20, cursor=None, now=LATER)

    row = page.items[0]
    assert row.excerpt == "x" * EXCERPT_CHARS
    assert set(row.model_dump()) == set(ScamCheckSummary.model_fields)
    assert (row.is_scam, row.scam_type, row.risk_level) == (True, "illegal_recruitment_fee", "high")
    assert row.reported is False


async def test_another_workers_checks_are_not_listed() -> None:
    repo = FakeCheckRepo()
    _put(repo, 1, uid="worker-2")
    mine = _put(repo, 2)

    page = await list_checks(make_store(repo), UID, limit=20, cursor=None, now=LATER)

    assert [item.id for item in page.items] == [mine]


async def test_an_expired_or_unreadable_check_is_left_out_of_the_list() -> None:
    repo = FakeCheckRepo()
    kept = _put(repo, 3)
    _put(repo, 2, expires_at=NOW)  # long expired
    broken = _put(repo, 1)
    del repo.docs[(UID, broken)]["verdict"]

    page = await list_checks(make_store(repo), UID, limit=20, cursor=None, now=LATER)

    assert [item.id for item in page.items] == [kept]


async def test_a_cursor_from_another_worker_cannot_page_this_history() -> None:
    repo = FakeCheckRepo()
    [_put(repo, n) for n in range(3)]

    with pytest.raises(InvalidCursorError):
        await list_checks(
            make_store(repo), UID, limit=2, cursor=encode_cursor("worker-2", NOW), now=LATER
        )


# --- one check ---------------------------------------------------------------------------------


async def test_one_check_is_returned_with_its_fields() -> None:
    repo = FakeCheckRepo()
    check_id = _put(repo, 1)

    check = await get_check(make_store(repo), UID, check_id, LATER)

    assert check.id == check_id and check.verdict.is_scam
    assert check.explainer_status == "ready"


@pytest.mark.parametrize(
    "who",
    ["missing", "another worker", "expired", "unreadable", "dot dot", "slash", "empty", "huge"],
)
async def test_an_absent_check_is_always_the_same_not_found(who: str) -> None:
    repo = FakeCheckRepo()
    mine = _put(repo, 1)
    theirs = _put(repo, 2, uid="worker-2")
    expired = _put(repo, 3, expires_at=NOW)
    broken = _put(repo, 4)
    del repo.docs[(UID, broken)]["verdict"]
    check_id = {
        "missing": "0" * 32,
        "another worker": theirs,
        "expired": expired,
        "unreadable": broken,
        "dot dot": "..",
        "slash": "a/b",
        "empty": "",
        "huge": "a" * 200,
    }[who]
    assert mine

    with pytest.raises(CheckNotFoundError):
        await get_check(make_store(repo), UID, check_id, LATER)


async def test_the_count_of_reports_is_read_when_the_check_is_shown() -> None:
    repo = FakeCheckRepo()
    check_id = _put(repo, 1)
    stored = repo.docs[(UID, check_id)]
    phone = next(i for i in stored["indicators"] if i["kind"] == "phone")
    from app.schemas.scam import ScamIndicator
    from app.services.scam.indicator_seen import indicator_doc_id

    doc_id = indicator_doc_id(ScamIndicator.model_validate(phone))
    indicators = FakeIndicatorRepo(
        {
            doc_id: {
                "report_count": 5,
                "incident_count": 3,
                "last_reported_at": LATER,
                "flagged": True,
                "hidden": False,
            }
        }
    )

    check = await get_check(make_store(repo, indicators), UID, check_id, LATER)

    seen = next(i for i in check.indicators if i.kind == "phone").seen
    assert seen is not None
    assert (seen.reports, seen.incidents, seen.flagged) == (5, 3, True)
    others = [i for i in check.indicators if i.kind != "phone"]
    assert all(i.seen is None for i in others)
