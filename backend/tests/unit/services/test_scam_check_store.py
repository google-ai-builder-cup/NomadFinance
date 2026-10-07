"""The cache key, the stored shape and the cache rules (NF-SA-012)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest

from app.services.scam.check_store import (
    CHECK_TTL,
    StoredCheckUnreadableError,
    cache_key,
    check_id_for,
    from_document,
    is_expired,
    is_usable_as_answer,
    models_used,
    prompt_versions,
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


def _document(case: str = "high", **changes: Any) -> dict[str, Any]:
    repo = FakeCheckRepo()
    put_check(repo, UID, mock_check(case), **changes)
    return repo.mine(UID)[0]


# --- the key -----------------------------------------------------------------------------------


def test_the_key_is_a_sha256_and_the_id_is_its_first_32_characters() -> None:
    key = cache_key("Pay the fee today", "hi")

    assert len(key) == 64 and int(key, 16) >= 0
    assert check_id_for(key) == key[:32]


@pytest.mark.parametrize(
    "variant",
    ["PAY THE FEE TODAY", "  Pay   the fee\ttoday \n", "Pay the fee today", "Ｐay the fee today"],
)
def test_a_message_that_differs_only_in_case_spacing_or_character_form_is_the_same(
    variant: str,
) -> None:
    assert cache_key(variant, "hi") == cache_key("Pay the fee today", "hi")


def test_a_different_message_or_language_is_a_different_key() -> None:
    base = cache_key("Pay the fee today", "hi")

    assert cache_key("Pay the fee tomorrow", "hi") != base
    assert cache_key("Pay the fee today", "en") != base


def test_the_language_cannot_be_smuggled_into_the_text() -> None:
    # The newline is the separator, so text ending in a language code is not the same key.
    assert cache_key("Pay the fee\nhi", "en") != cache_key("Pay the fee", "hi")


# --- the stored shape --------------------------------------------------------------------------


def test_a_stored_check_has_the_bookkeeping_the_data_model_asks_for() -> None:
    doc = _document()

    assert doc["schema_version"] == 1 and doc["check_count"] == 1
    assert doc["cache_key"] == cache_key(doc["redacted_text"], doc["language"])
    assert doc["expires_at"] - doc["created_at"] == CHECK_TTL
    assert doc["prompt_versions"] == prompt_versions(True)
    assert set(doc["models"]) == {"classifier", "explainer"}
    assert doc["taxonomy_version"] == 1


def test_a_benign_check_records_the_reassurance_prompt_not_the_explainer() -> None:
    doc = _document("benign")

    assert set(doc["prompt_versions"]) == set(prompt_versions(False))
    assert "scam.explain" not in doc["prompt_versions"]


def test_a_screenshot_check_records_the_vision_model() -> None:
    assert "vision" in models_used(True, "screenshot")
    assert "vision" not in models_used(True, "text")


def test_what_is_unknown_is_left_out_not_stored_as_null() -> None:
    doc = _document("benign")

    assert None not in doc.values()
    assert "reported_report_id" not in doc and "reported_at" not in doc


def test_seen_is_never_stored_on_a_check() -> None:
    # The count changes after the check is made, so it is read live (scam_indicators).
    doc = _document()

    assert doc["indicators"], "the high-risk mock has indicators"
    assert all("seen" not in indicator for indicator in doc["indicators"])


@pytest.mark.parametrize("case", ["high", "medium", "low", "benign"])
def test_a_check_read_back_is_the_check_that_was_stored(case: str) -> None:
    check = mock_check(case)
    repo = FakeCheckRepo()
    check_id = put_check(repo, UID, check)

    read = from_document(check_id, repo.docs[(UID, check_id)])

    expected = check.model_dump(exclude={"cached"})
    expected["id"] = check_id
    for indicator in expected["indicators"]:
        indicator["seen"] = None
    assert read.model_dump() == expected


def test_a_document_that_no_longer_fits_the_contract_is_unreadable_not_a_crash() -> None:
    doc = _document()
    del doc["verdict"]

    with pytest.raises(StoredCheckUnreadableError):
        from_document("x", doc)
    doc2 = _document()
    doc2["verdict"]["risk_level"] = "extreme"
    with pytest.raises(StoredCheckUnreadableError):
        from_document("x", doc2)


def test_a_reported_check_reads_back_as_reported() -> None:
    doc = _document(reported_report_id="r_1")

    check = from_document("x", doc)

    assert check.reported is True and check.report_id == "r_1"


# --- when a stored check may be served again ---------------------------------------------------


def test_a_good_stored_check_is_usable() -> None:
    assert is_usable_as_answer(_document(), taxonomy_version=1)


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"explainer": None}, "no explainer: the next try makes one"),
        ({"taxonomy_version": 2}, "the taxonomy has changed"),
        ({"prompt_versions": {"scam.classify": 1, "scam.explain": 1}}, "an older prompt"),
        ({"prompt_versions": {}}, "no record of the prompts"),
        ({"prompt_versions": "v1"}, "a malformed record"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_a_stored_check_is_not_served_when(change: dict[str, Any], why: str) -> None:
    document = _document()
    document.update(change)
    if change.get("explainer", 1) is None:
        document.pop("explainer")

    assert not is_usable_as_answer(document, taxonomy_version=1), why


def test_a_check_past_its_expiry_is_gone_even_before_the_ttl_job_removes_it() -> None:
    assert not is_expired(_document(), NOW + CHECK_TTL - timedelta(seconds=1))
    assert is_expired(_document(), NOW + CHECK_TTL)
    assert is_expired({"redacted_text": "no expiry field"}, NOW)


# --- the store ---------------------------------------------------------------------------------


async def test_a_stored_check_is_found_by_its_message_and_served_as_cached() -> None:
    repo = FakeCheckRepo()
    store = make_store(repo)
    check = mock_check()
    put_check(repo, UID, check)
    key = cache_key(check.redacted_text, check.language)

    lookup = await store.lookup(UID, key, 1, NOW)
    assert lookup.hit is not None
    answer = await store.serve_hit(UID, lookup.hit, NOW + timedelta(days=1))

    assert answer.cached is True and answer.id == check_id_for(key)
    assert answer.expires_at == NOW + timedelta(days=1) + CHECK_TTL
    stored = repo.mine(UID)[0]
    assert stored["check_count"] == 2 and stored["last_checked_at"] == NOW + timedelta(days=1)


async def test_another_workers_check_is_not_found() -> None:
    repo = FakeCheckRepo()
    check = mock_check()
    put_check(repo, "someone-else", check)

    lookup = await make_store(repo).lookup(
        UID, cache_key(check.redacted_text, check.language), 1, NOW
    )

    assert lookup.hit is None and lookup.previous is None


async def test_an_old_check_that_cannot_be_served_is_remembered_for_what_it_knew() -> None:
    repo = FakeCheckRepo()
    check = mock_check()
    put_check(repo, UID, check, taxonomy_version=7, reported_report_id="r_9")

    lookup = await make_store(repo).lookup(
        UID, cache_key(check.redacted_text, check.language), 1, NOW
    )

    assert lookup.hit is None
    assert lookup.previous is not None and lookup.previous["reported_report_id"] == "r_9"


async def test_an_expired_check_is_forgotten_entirely() -> None:
    repo = FakeCheckRepo()
    check = mock_check()
    put_check(repo, UID, check, reported_report_id="r_9")

    lookup = await make_store(repo).lookup(
        UID, cache_key(check.redacted_text, check.language), 1, NOW + CHECK_TTL
    )

    assert lookup.hit is None and lookup.previous is None


async def test_saving_over_an_older_check_keeps_the_report_and_counts_the_check() -> None:
    repo = FakeCheckRepo()
    old = mock_check()
    put_check(repo, UID, old, check_count=3, reported_report_id="r_9", reported_at=NOW)
    key = cache_key(old.redacted_text, old.language)
    previous = repo.mine(UID)[0]
    fresh = mock_check(id=check_id_for(key), reported=True, report_id="r_9")

    await make_store(repo).save(
        UID, key, fresh, taxonomy_version=1, previous=previous, now=NOW + timedelta(days=2)
    )

    stored = repo.mine(UID)[0]
    assert len(repo.mine(UID)) == 1
    assert stored["check_count"] == 4
    assert stored["reported_report_id"] == "r_9" and stored["reported_at"] == NOW


async def test_a_firestore_outage_never_fails_a_check() -> None:
    repo = FakeCheckRepo()
    store = make_store(repo, FakeIndicatorRepo())
    check = mock_check()
    key = cache_key(check.redacted_text, check.language)
    repo.down = True

    assert (await store.lookup(UID, key, 1, NOW)).hit is None  # a miss: the check goes on
    await store.save(UID, key, check, taxonomy_version=1, previous=None, now=NOW)  # swallowed
    assert repo.saves == 0


async def test_nothing_that_identifies_the_message_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = FakeCheckRepo()
    check = mock_check()
    key = cache_key(check.redacted_text, check.language)
    store = make_store(repo)
    caplog.set_level("DEBUG")

    await store.save(UID, key, check, taxonomy_version=1, previous=None, now=NOW)
    await store.lookup(UID, key, 1, NOW)

    assert key[:32] not in caplog.text and check.redacted_text not in caplog.text


def test_the_stored_document_is_json_serialisable_once_timestamps_are_text() -> None:
    # Firestore stores the datetimes natively; everything else must be plain data.
    document = _document()

    json.dumps(document, default=str)
