"""The small cache behind the recommendation answers, and its log line (NF-HR-010)."""

from __future__ import annotations

import logging

import pytest

from app.core.cache import TtlCache, log_cache_lookup


class Ticking:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def test_a_stored_value_is_found_until_its_life_is_over() -> None:
    clock = Ticking()
    cache: TtlCache[str] = TtlCache(60, 10, clock=clock)
    cache.put("k", "v")

    clock.now += 59.9
    assert cache.get("k") == "v"
    clock.now += 0.1
    assert cache.get("k") is None
    assert len(cache) == 0  # an expired value is dropped, not kept


def test_a_missing_key_is_none() -> None:
    assert TtlCache[str](60, 10).get("nothing") is None


def test_storing_again_restarts_the_life() -> None:
    clock = Ticking()
    cache: TtlCache[str] = TtlCache(60, 10, clock=clock)
    cache.put("k", "old")
    clock.now += 50
    cache.put("k", "new")
    clock.now += 50

    assert cache.get("k") == "new"


def test_when_full_the_value_stored_longest_ago_goes_first() -> None:
    cache: TtlCache[int] = TtlCache(60, 2)
    for number, key in enumerate(("a", "b", "c")):
        cache.put(key, number)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (None, 1, 2)


def test_clear_forgets_everything() -> None:
    cache: TtlCache[int] = TtlCache(60, 2)
    cache.put("a", 1)
    cache.clear()

    assert cache.get("a") is None and len(cache) == 0


@pytest.mark.parametrize(("hit", "result"), [(True, "hit"), (False, "miss")])
def test_a_lookup_is_logged_with_its_feature_cache_and_result(
    caplog: pytest.LogCaptureFixture, hit: bool, result: str
) -> None:
    with caplog.at_level(logging.INFO):
        log_cache_lookup("remittance", "recommend", hit=hit)

    record = next(r for r in caplog.records if r.getMessage().startswith("cache_lookup"))
    assert record.getMessage() == f"cache_lookup feature=remittance name=recommend result={result}"
    assert record.__dict__["cache_lookup"] == {
        "feature": "remittance",
        "name": "recommend",
        "result": result,
    }
