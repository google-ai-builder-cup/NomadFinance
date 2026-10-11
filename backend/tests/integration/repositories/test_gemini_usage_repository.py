"""NF-HR-010 against the Firestore emulator: the day's document, counted with server-side
increments so that two instances never overwrite each other."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from google.api_core.exceptions import ServiceUnavailable
from google.cloud.firestore import Client

from app.integrations.gemini.budget import UsageStoreError
from app.repositories.gemini_usage_repo import GeminiUsageRepository

needs_emulator = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="Firestore Emulator not running (FIRESTORE_EMULATOR_HOST not set)",
)
DAY = "2026-11-12"


@needs_emulator
def test_counts_add_up_per_feature_and_tier(clean_firestore: Client) -> None:
    repo = GeminiUsageRepository(clean_firestore)

    repo.add(DAY, "coach", "classification", 1)
    repo.add(DAY, "coach", "classification", 1)
    repo.add(DAY, "coach", "reasoning", 1)
    repo.add(DAY, "scam", "classification", 1)

    usage = repo.read(DAY)
    assert usage.calls == {
        ("coach", "classification"): 2,
        ("coach", "reasoning"): 1,
        ("scam", "classification"): 1,
    }
    assert usage.exhausted == set()


@needs_emulator
def test_a_day_nobody_has_used_reads_as_empty(clean_firestore: Client) -> None:
    usage = GeminiUsageRepository(clean_firestore).read("2026-01-01")

    assert usage.calls == {} and usage.exhausted == set()


@needs_emulator
def test_two_instances_writing_at_once_lose_no_request(clean_firestore: Client) -> None:
    first, second = GeminiUsageRepository(clean_firestore), GeminiUsageRepository(clean_firestore)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for number in range(40):
            pool.submit((first if number % 2 else second).add, DAY, "scam", "reasoning", 1)

    assert first.read(DAY).calls == {("scam", "reasoning"): 40}


@needs_emulator
def test_a_closed_tier_is_kept_and_does_not_disturb_the_counts(clean_firestore: Client) -> None:
    repo = GeminiUsageRepository(clean_firestore)
    repo.add(DAY, "coach", "reasoning", 3)

    repo.mark_exhausted(DAY, "reasoning")
    repo.add(DAY, "coach", "reasoning", 1)

    usage = repo.read(DAY)
    assert usage.exhausted == {"reasoning"}
    assert usage.calls == {("coach", "reasoning"): 4}


@needs_emulator
def test_the_document_is_one_per_day_and_carries_the_schema_version(
    clean_firestore: Client,
) -> None:
    repo = GeminiUsageRepository(clean_firestore)
    repo.add(DAY, "coach", "reasoning", 1)

    data = clean_firestore.collection("gemini_usage").document(DAY).get().to_dict() or {}

    assert data["schema_version"] == 1 and data["updated_at"] is not None
    assert [d.id for d in clean_firestore.collection("gemini_usage").stream()] == [DAY]


class _BrokenClient:
    def collection(self, _: str) -> object:
        raise ServiceUnavailable("firestore is down")


def test_a_firestore_failure_is_a_store_error_the_budget_can_absorb() -> None:
    repo = GeminiUsageRepository(_BrokenClient())  # type: ignore[arg-type]

    for call in (
        lambda: repo.read(DAY),
        lambda: repo.add(DAY, "coach", "reasoning", 1),
        lambda: repo.mark_exhausted(DAY, "reasoning"),
    ):
        with pytest.raises(UsageStoreError):
            call()
