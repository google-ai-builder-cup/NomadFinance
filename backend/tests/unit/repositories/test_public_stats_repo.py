from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.repositories.public_stats_repo import PublicStatsRepository


class FakeQuery:
    """Stands in for a Firestore collection or query: `count()` and `sum()` return an
    aggregation whose `get()` answers `[[AggregationResult]]`, as the SDK does."""

    def __init__(self, number: int | None) -> None:
        self._number = number

    def where(self, **_: Any) -> FakeQuery:
        return self

    def count(self) -> FakeQuery:
        return self

    def sum(self, _field: str) -> FakeQuery:
        return self

    def get(self) -> list[list[Any]]:
        return [[SimpleNamespace(value=self._number)]]


class FakeClient:
    def __init__(self, numbers: dict[str, int | None]) -> None:
        self._numbers = numbers

    def collection(self, name: str) -> FakeQuery:
        return FakeQuery(self._numbers[name])

    def collection_group(self, name: str) -> FakeQuery:
        return FakeQuery(self._numbers[name])


def repo(numbers: dict[str, int | None]) -> PublicStatsRepository:
    return PublicStatsRepository(FakeClient(numbers))  # type: ignore[arg-type]


def test_a_count_reads_the_one_number_an_aggregation_returns() -> None:
    stats = repo({"users": 12, "current": 4})

    assert (stats.workers(), stats.alerts_generated()) == (12, 4)


def test_an_aggregation_over_nothing_is_zero_not_none() -> None:
    assert repo({"users": None}).workers() == 0


def test_scam_checks_sums_checks_and_scams_over_the_weekly_counts() -> None:
    # The fake answers every sum with the same number: enough to see both are asked for.
    assert repo({"weeks": 9}).scam_checks() == (9, 9)
