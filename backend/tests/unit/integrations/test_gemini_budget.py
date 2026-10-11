"""The daily budget of Gemini requests (NF-HR-010): the quota day, the shares and the refusals."""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime

import pytest

from app.integrations.gemini import GeminiBudget, GeminiBudgetExhaustedError, GeminiRateLimitError
from app.integrations.gemini.budget import (
    REFRESH_SECONDS,
    SHARES,
    UNLISTED_SHARE,
    DayUsage,
    budget_day,
    seconds_until_reset,
)
from tests.unit.integrations.budget_fakes import FakeStore, make_budget

pytestmark = pytest.mark.anyio


# --- the quota day -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("utc", "day", "left"),
    [
        # Daylight time (UTC-7): the day turns at 07:00 UTC, as the team saw in September.
        (datetime(2026, 9, 28, 6, 59, 59, tzinfo=UTC), "2026-09-27", 1),
        (datetime(2026, 9, 28, 7, 0, 0, tzinfo=UTC), "2026-09-28", 86400),
        # Standard time (UTC-8): 08:00 UTC.
        (datetime(2026, 11, 12, 7, 59, 59, tzinfo=UTC), "2026-11-11", 1),
        (datetime(2026, 11, 12, 8, 0, 0, tzinfo=UTC), "2026-11-12", 86400),
        # The switch back, 02:00 PDT on the first Sunday of November (09:00 UTC).
        (datetime(2026, 11, 1, 8, 59, 59, tzinfo=UTC), "2026-11-01", 22 * 3600 + 1),
        (datetime(2026, 11, 1, 9, 0, 0, tzinfo=UTC), "2026-11-01", 23 * 3600),
        # The switch forward, 02:00 PST on the second Sunday of March (10:00 UTC).
        (datetime(2026, 3, 8, 9, 59, 59, tzinfo=UTC), "2026-03-08", 22 * 3600 + 1),
        (datetime(2026, 3, 8, 10, 0, 0, tzinfo=UTC), "2026-03-08", 21 * 3600),
    ],
)
def test_the_quota_day_turns_at_midnight_pacific(utc: datetime, day: str, left: int) -> None:
    assert budget_day(utc) == day
    assert seconds_until_reset(utc) == left


# --- the shares --------------------------------------------------------------------------------


def test_a_features_limit_is_its_share_of_the_models_day_rounded_down() -> None:
    budget, _, _ = make_budget({"reasoning": 500})

    assert budget.limit_for("coach", "reasoning") == math.floor(500 * SHARES["reasoning"]["coach"])
    assert budget.limit_for("coach", "reasoning") == 100


def test_a_feature_missing_from_the_table_gets_the_small_default_share() -> None:
    budget, _, _ = make_budget({"reasoning": 500})

    assert budget.limit_for("brand_new_feature", "reasoning") == int(500 * UNLISTED_SHARE)


def test_a_tier_without_a_configured_limit_has_no_budget() -> None:
    budget, _, _ = make_budget({"reasoning": 500})

    assert budget.limit_for("coach", "classification") is None


def test_a_very_small_limit_still_lets_one_request_through() -> None:
    budget, _, _ = make_budget({"reasoning": 3})

    assert budget.limit_for("fib", "reasoning") == 1


def test_shares_never_add_up_to_more_than_the_models_day() -> None:
    for tier, shares in SHARES.items():
        assert sum(shares.values()) + UNLISTED_SHARE <= 1.0, tier


# --- refusing ----------------------------------------------------------------------------------


async def test_a_feature_is_refused_after_its_share_and_others_are_not() -> None:
    budget, store, _ = make_budget({"reasoning": 20})  # coach 4, scam 5

    for _ in range(5):
        await budget.admit("scam", "reasoning")
    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        await budget.admit("scam", "reasoning")
    await budget.admit("coach", "reasoning")

    assert refused.value.source == "budget"
    assert refused.value.daily is True
    assert isinstance(refused.value, GeminiRateLimitError)
    assert store.days["2026-11-12"].calls == {("scam", "reasoning"): 5, ("coach", "reasoning"): 1}


async def test_a_refusal_says_when_the_quota_is_back() -> None:
    budget, _, _ = make_budget({"reasoning": 1})  # scam 1 (floor, at least 1)
    await budget.admit("scam", "reasoning")

    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        await budget.admit("scam", "reasoning")

    # 18:00 UTC on 12 Nov is 10:00 Pacific: 14 hours to midnight.
    assert refused.value.retry_after_seconds == 14 * 3600


async def test_a_refusal_is_logged_with_its_feature_and_tier(
    caplog: pytest.LogCaptureFixture,
) -> None:
    budget, _, _ = make_budget({"reasoning": 1})
    await budget.admit("scam", "reasoning")

    with caplog.at_level(logging.WARNING), pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("scam", "reasoning")

    record = next(r for r in caplog.records if r.getMessage().startswith("gemini_budget_blocked"))
    assert record.__dict__["gemini_budget"] == {
        "feature": "scam",
        "tier": "reasoning",
        "source": "budget",
        "used": 1,
        "limit": 1,
    }
    assert not hasattr(record, "gemini_usage")  # not a request to Google


async def test_the_counts_start_again_when_the_quota_day_turns() -> None:
    budget, store, clock = make_budget({"reasoning": 1})
    await budget.admit("scam", "reasoning")
    clock.now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)  # past 00:00 Pacific on the 13th

    await budget.admit("scam", "reasoning")

    assert store.days["2026-11-13"].calls == {("scam", "reasoning"): 1}


async def test_without_a_configured_limit_nothing_is_refused() -> None:
    budget, _, _ = make_budget({})

    for _ in range(50):
        await budget.admit("coach", "reasoning")


# --- Google's own daily 429 --------------------------------------------------------------------


async def test_a_daily_429_closes_the_tier_for_every_feature_until_the_day_turns() -> None:
    budget, store, clock = make_budget({})

    with pytest.raises(GeminiRateLimitError):
        async with budget.attempt("coach", "reasoning"):
            raise GeminiRateLimitError("quota", daily=True)

    with pytest.raises(GeminiBudgetExhaustedError) as refused:
        await budget.admit("scam", "reasoning")
    await budget.admit("scam", "classification")  # another model, another quota
    assert refused.value.source == "google"
    assert store.days["2026-11-12"].exhausted == {"reasoning"}

    clock.now = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
    await budget.admit("scam", "reasoning")


async def test_a_tier_closed_before_the_first_request_of_the_day_stays_closed() -> None:
    budget, _, _ = make_budget({})

    await budget.mark_exhausted("reasoning")

    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("coach", "reasoning")


async def test_a_per_minute_429_does_not_close_the_tier() -> None:
    budget, _, _ = make_budget({})

    with pytest.raises(GeminiRateLimitError):
        async with budget.attempt("coach", "reasoning"):
            raise GeminiRateLimitError("slow down", daily=False)

    await budget.admit("coach", "reasoning")


async def test_another_instances_closed_tier_is_learned_on_the_next_refresh() -> None:
    store = FakeStore()
    store.days["2026-11-12"] = DayUsage(exhausted={"reasoning"})
    budget, _, _ = make_budget({}, store)

    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("coach", "reasoning")


# --- sharing the count -------------------------------------------------------------------------


async def test_requests_made_by_another_instance_count_against_the_share() -> None:
    store = FakeStore()
    store.days["2026-11-12"] = DayUsage(calls={("scam", "reasoning"): 5})
    budget, _, _ = make_budget({"reasoning": 20}, store)  # scam 5

    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("scam", "reasoning")


async def test_the_shared_count_is_read_again_only_after_the_refresh_interval() -> None:
    budget, store, clock = make_budget({"reasoning": 20})

    await budget.admit("coach", "reasoning")
    await budget.admit("coach", "reasoning")
    assert store.reads == 1

    clock.seconds += REFRESH_SECONDS
    await budget.admit("coach", "reasoning")
    assert store.reads == 2


async def test_an_outage_of_the_store_never_stops_a_request(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = FakeStore()
    store.down = True
    budget, _, _ = make_budget({"reasoning": 20}, store)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            await budget.admit("coach", "reasoning")
        with pytest.raises(GeminiRateLimitError):
            async with budget.attempt("coach", "reasoning"):
                raise GeminiRateLimitError("quota", daily=True)

    assert any("gemini_budget_store_unavailable" in r.getMessage() for r in caplog.records)
    # The process still counts for itself, so one instance cannot run past its share.
    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("coach", "reasoning")


async def test_a_store_that_hangs_does_not_hold_up_the_request(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr("app.integrations.gemini.budget.STORE_TIMEOUT_SECONDS", 0.05)

    class Hanging(FakeStore):
        def read(self, day: str) -> DayUsage:
            time.sleep(0.4)
            return super().read(day)

        def add(self, day: str, feature: str, tier: str, count: int) -> None:
            time.sleep(0.4)

    budget, _, _ = make_budget({"reasoning": 20}, Hanging())

    started = time.perf_counter()
    with caplog.at_level(logging.WARNING):
        await budget.admit("coach", "reasoning")

    assert time.perf_counter() - started < 0.3  # two store calls, each cut off at 50 ms
    assert any(
        "gemini_budget_store_unavailable error=TimeoutError" in r.getMessage()
        for r in caplog.records
    )


async def test_without_a_store_the_budget_counts_in_the_process_only() -> None:
    budget = GeminiBudget(None, {"reasoning": 1})

    await budget.admit("scam", "reasoning")
    with pytest.raises(GeminiBudgetExhaustedError):
        await budget.admit("scam", "reasoning")
