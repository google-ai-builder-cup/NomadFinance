"""The scam-check repositories against the real Firestore emulator (NF-SA-012)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from google.cloud.firestore import Client

from app.repositories.scam_check_repo import ScamCheckRepository
from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.services.scam.check_store import CHECK_TTL, CheckStore, cache_key, check_id_for
from app.services.scam.history import get_check, list_checks
from tests.fixtures.scam_checks import NOW, FakeCheckRepo, mock_check, put_check

pytestmark = pytest.mark.anyio

UID = "worker-1"


def _document(n: int = 0, **changes: Any) -> tuple[str, dict[str, Any]]:
    memory = FakeCheckRepo()
    created = NOW + timedelta(hours=n)
    check = mock_check(
        redacted_text=f"Pay the processing fee number {n} today",
        created_at=created,
        expires_at=created + CHECK_TTL,
    )
    check_id = put_check(memory, UID, check, **changes)
    return check_id, memory.docs[(UID, check_id)]


def test_a_check_is_written_and_read_back_with_its_timestamps(clean_firestore: Client) -> None:
    repo = ScamCheckRepository(clean_firestore)
    check_id, document = _document()

    repo.save(UID, check_id, document)
    read = repo.get(UID, check_id)

    assert read is not None
    assert read["verdict"] == document["verdict"]
    assert read["created_at"] == document["created_at"]
    assert isinstance(read["expires_at"], datetime)


def test_a_missing_check_is_none_and_another_workers_is_not_seen(clean_firestore: Client) -> None:
    repo = ScamCheckRepository(clean_firestore)
    check_id, document = _document()
    repo.save("someone-else", check_id, document)

    assert repo.get(UID, check_id) is None
    assert repo.get(UID, "0" * 32) is None


def test_touch_counts_one_more_check_and_moves_the_expiry(clean_firestore: Client) -> None:
    repo = ScamCheckRepository(clean_firestore)
    check_id, document = _document(check_count=1)
    repo.save(UID, check_id, document)
    later = NOW + timedelta(days=3)

    repo.touch(UID, check_id, last_checked_at=later, expires_at=later + CHECK_TTL)
    repo.touch(UID, check_id, last_checked_at=later, expires_at=later + CHECK_TTL)

    read = repo.get(UID, check_id)
    assert read is not None
    assert read["check_count"] == 3 and read["expires_at"] == later + CHECK_TTL


def test_the_newest_come_first_and_before_pages_without_repeats(clean_firestore: Client) -> None:
    repo = ScamCheckRepository(clean_firestore)
    ids = []
    for n in range(5):
        check_id, document = _document(n)
        repo.save(UID, check_id, document)
        ids.append(check_id)
    repo.save("someone-else", *_document(9))

    first = repo.list_newest(UID, 2)
    second = repo.list_newest(UID, 2, before=first[-1][1]["created_at"])
    third = repo.list_newest(UID, 2, before=second[-1][1]["created_at"])

    assert [i for i, _ in first + second + third] == list(reversed(ids))


async def test_the_whole_flow_runs_on_the_real_repositories(clean_firestore: Client) -> None:
    store = CheckStore(
        ScamCheckRepository(clean_firestore), ScamIndicatorRepository(clean_firestore)
    )
    check = mock_check()
    key = cache_key(check.redacted_text, check.language)
    check = check.model_copy(update={"id": check_id_for(key)})

    assert (await store.lookup(UID, key, 1, NOW)).hit is None
    await store.save(UID, key, check, taxonomy_version=1, previous=None, now=NOW)
    hit = (await store.lookup(UID, key, 1, NOW)).hit
    assert hit is not None
    answer = await store.serve_hit(UID, hit, NOW + timedelta(hours=1))
    page = await list_checks(store, UID, limit=20, cursor=None, now=NOW + timedelta(hours=1))
    detail = await get_check(store, UID, check.id, NOW + timedelta(hours=1))

    assert answer.cached is True and answer.id == check.id
    assert [item.id for item in page.items] == [check.id]
    assert detail.verdict == check.verdict
    stored = ScamCheckRepository(clean_firestore).get(UID, check.id)
    assert stored is not None and stored["check_count"] == 2


def test_the_indicator_counts_are_read_in_one_call(clean_firestore: Client) -> None:
    clean_firestore.document("scam_indicators/aaa").set({"report_count": 2})
    clean_firestore.document("scam_indicators/bbb").set({"report_count": 7})
    repo = ScamIndicatorRepository(clean_firestore)

    found = repo.get_many(["aaa", "bbb", "missing"])

    assert set(found) == {"aaa", "bbb"} and found["bbb"]["report_count"] == 7
    assert repo.get_many([]) == {}
