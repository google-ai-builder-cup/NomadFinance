from __future__ import annotations

from typing import Any

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.services.feature_flag_service import MAX_ALLOW_UIDS, FeatureFlagService

pytestmark = pytest.mark.anyio


def _document(**flags: dict[str, Any]) -> dict[str, Any]:
    return {"flags": flags, "updated_by": "XX", "schema_version": 1}


class _FakeRepo:
    def __init__(self, document: dict[str, Any] | None) -> None:
        self.document = document
        self.error: Exception | None = None
        self.reads = 0

    def get_feature_flags(self) -> dict[str, Any] | None:
        self.reads += 1
        if self.error is not None:
            raise self.error
        return self.document


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _service(document: dict[str, Any] | None) -> tuple[FeatureFlagService, _FakeRepo, _Clock]:
    repo, clock = _FakeRepo(document), _Clock()
    return FeatureFlagService(repo, clock=clock), repo, clock  # type: ignore[arg-type]


async def test_a_flag_that_is_enabled_is_on_for_everyone() -> None:
    service, _, _ = _service(_document(scam={"enabled": True, "allow_uids": []}))

    assert await service.is_enabled("scam", "anyone") is True


async def test_a_disabled_flag_is_off_for_everyone_not_on_the_list() -> None:
    service, _, _ = _service(_document(coach={"enabled": False, "allow_uids": ["tester"]}))

    assert await service.is_enabled("coach", "someone-else") is False


async def test_the_allow_list_turns_a_disabled_flag_on_for_named_users_only() -> None:
    service, _, _ = _service(_document(coach={"enabled": False, "allow_uids": ["tester"]}))

    assert await service.is_enabled("coach", "tester") is True
    assert await service.is_enabled("coach", "someone-else") is False


async def test_flags_are_independent() -> None:
    service, _, _ = _service(
        _document(coach={"enabled": False}, scam={"enabled": True, "allow_uids": []})
    )

    assert await service.enabled_for("u1") == {"coach": False, "scam": True}


@pytest.mark.parametrize(
    "document",
    [
        None,
        {},
        {"flags": None},
        {"flags": "on"},
        {"flags": {}},
        {"flags": {"coach": None}},
        {"flags": {"coach": True}},
        {"flags": {"coach": {"enabled": "true"}}},
        {"flags": {"coach": {"enabled": 1}}},
        {"flags": {"coach": {"allow_uids": "u1"}}},
        {"flags": {"coach": {"allow_uids": [None, 5, ""]}}},
    ],
)
async def test_a_missing_or_malformed_document_means_off(document: dict[str, Any] | None) -> None:
    service, _, _ = _service(document)

    assert await service.enabled_for("u1") == {"coach": False, "scam": False}


async def test_an_unknown_flag_name_in_the_document_is_ignored() -> None:
    service, _, _ = _service(_document(billing={"enabled": True}))

    assert await service.enabled_for("u1") == {"coach": False, "scam": False}


async def test_a_malformed_allow_list_does_not_hide_a_good_enabled_value() -> None:
    service, _, _ = _service(_document(scam={"enabled": True, "allow_uids": "oops"}))

    assert await service.is_enabled("scam", "u1") is True


async def test_an_oversize_allow_list_keeps_the_first_entries_and_never_turns_a_flag_off() -> None:
    uids = [f"u{i}" for i in range(MAX_ALLOW_UIDS + 5)]
    service, _, _ = _service(_document(coach={"enabled": False, "allow_uids": uids}))

    assert await service.is_enabled("coach", "u0") is True
    assert await service.is_enabled("coach", f"u{MAX_ALLOW_UIDS - 1}") is True
    assert await service.is_enabled("coach", f"u{MAX_ALLOW_UIDS}") is False


async def test_the_document_is_read_once_a_minute_not_on_every_call() -> None:
    service, repo, clock = _service(_document(scam={"enabled": True}))

    await service.is_enabled("scam", "u1")
    clock.now += 59.9
    await service.is_enabled("scam", "u2")
    await service.enabled_for("u3")

    assert repo.reads == 1


async def test_a_change_in_firestore_shows_up_within_a_minute() -> None:
    service, repo, clock = _service(_document(scam={"enabled": False}))
    assert await service.is_enabled("scam", "u1") is False

    repo.document = _document(scam={"enabled": True})
    clock.now += 59.0
    assert await service.is_enabled("scam", "u1") is False  # still the cached copy
    clock.now += 1.0
    assert await service.is_enabled("scam", "u1") is True
    assert repo.reads == 2


async def test_a_flag_switched_off_stops_applying_within_a_minute() -> None:
    service, repo, clock = _service(_document(scam={"enabled": True}))
    assert await service.is_enabled("scam", "u1") is True

    repo.document = _document(scam={"enabled": False})
    clock.now += 60.0

    assert await service.is_enabled("scam", "u1") is False


async def test_a_failed_read_keeps_the_last_good_copy_and_tries_again_next_time() -> None:
    service, repo, clock = _service(_document(scam={"enabled": True}))
    assert await service.is_enabled("scam", "u1") is True

    repo.error = ServiceUnavailable("firestore is down")
    clock.now += 61.0
    assert await service.is_enabled("scam", "u1") is True  # not hidden by an outage
    assert await service.is_enabled("scam", "u1") is True
    assert repo.reads == 3  # first read, then a retry on each call while it is down

    repo.error = None
    repo.document = _document(scam={"enabled": False})
    assert await service.is_enabled("scam", "u1") is False  # recovered, new value used


async def test_a_failed_first_read_means_off_never_on() -> None:
    service, repo, _ = _service(_document(scam={"enabled": True}))
    repo.error = ServiceUnavailable("firestore is down")

    assert await service.enabled_for("u1") == {"coach": False, "scam": False}
