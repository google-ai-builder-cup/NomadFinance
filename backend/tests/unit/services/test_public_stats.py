from __future__ import annotations

from collections.abc import Iterator

import pytest
from google.api_core.exceptions import FailedPrecondition

from app.services import public_stats
from app.services.public_stats import get_public_stats

pytestmark = pytest.mark.anyio


class FakeReader:
    def __init__(self, *, failing: frozenset[str] = frozenset()) -> None:
        self.calls = 0
        self._failing = failing

    def _read(self, name: str, value: int) -> int:
        self.calls += 1
        if name in self._failing:
            raise FailedPrecondition("the query requires an index")
        return value

    def workers(self) -> int:
        return self._read("workers", 12)

    def contracts_checked(self) -> int:
        return self._read("contracts_checked", 7)

    def radar_reports(self) -> int:
        return self._read("radar_reports", 31)

    def alerts_generated(self) -> int:
        return self._read("alerts_generated", 4)

    def scam_checks(self) -> tuple[int, int]:
        self._read("scam_checks", 0)
        return 20, 15


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    public_stats.clear_cache()
    yield
    public_stats.clear_cache()


async def test_collects_every_total() -> None:
    stats = await get_public_stats(FakeReader())

    assert (stats.workers, stats.contracts_checked, stats.radar_reports) == (12, 7, 31)
    assert stats.alerts_generated == 4
    assert (stats.scam_messages_checked, stats.scams_flagged) == (20, 15)


async def test_a_total_that_cannot_be_read_is_left_out_not_zeroed() -> None:
    stats = await get_public_stats(
        FakeReader(failing=frozenset({"contracts_checked", "scam_checks"}))
    )

    assert stats.contracts_checked is None
    assert stats.scam_messages_checked is None
    assert stats.scams_flagged is None
    assert stats.radar_reports == 31


async def test_a_second_call_within_the_cache_window_does_not_read_again() -> None:
    reader = FakeReader()

    first = await get_public_stats(reader)
    reads_after_first = reader.calls
    second = await get_public_stats(reader)

    assert second is first
    assert reader.calls == reads_after_first
