"""A daily budget of Gemini requests for each feature (NF-HR-010).

Every Gemini model has one daily request quota that all features and all workers share (the
figure is only shown in Google AI Studio, ADR-002). Without a budget, a run of Coach plans can
use up the reasoning model before a scam explainer is asked for, and every call that follows
retries a quota that is already gone. This module does two things before a request is sent:

- It refuses a request when its feature has used its share of the model's day (`SHARES`), so the
  other features keep theirs.
- It remembers that Google answered a per-day 429 for a model, and refuses the model's requests
  until the day turns, instead of spending three attempts on each.

Both refusals are a `GeminiBudgetExhaustedError`, a rate-limit error, so the scam explainer's
fallback tier and the API's 503 already handle it. Counts live in Firestore (`gemini_usage/{day}`)
so every Cloud Run instance sees the same day; each instance re-reads them every
`REFRESH_SECONDS`, so with two instances a share can be overshot by the requests made in that
window. The budget only acts once the model's daily limit is configured (`GEMINI_RPD_*`);
without it nothing is counted outside this process and no Firestore call is made.
"""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from datetime import time as day_time
from time import monotonic
from typing import Protocol, TypeVar

from fastapi.concurrency import run_in_threadpool

from app.integrations.gemini.errors import GeminiBudgetExhaustedError, GeminiRateLimitError

logger = logging.getLogger(__name__)

EMBEDDING_TIER = "embedding"

# The share of a model's daily requests each feature may use. The rest is headroom for retries,
# other users of the same key and a feature missing from this table (`UNLISTED_SHARE`). Sized
# from the journey counts and the demo-day projection in
# docs/runbooks/NF-HR-010-gemini-quota-guard.md (`scripts/project_demo_usage.py`). Coach has a
# share of the extraction model too, for the day its reply is moved there
# (`GEMINI_COACH_REPLY_TIER=extraction`).
SHARES: dict[str, dict[str, float]] = {
    "reasoning": {"coach": 0.20, "scam": 0.25, "contract": 0.25, "fib": 0.05},
    "extraction": {"coach": 0.40, "contract": 0.15, "scam": 0.10, "radar": 0.05, "fib": 0.10},
    "classification": {
        "coach": 0.50,
        "scam": 0.15,
        "contract": 0.08,
        "radar": 0.05,
        "remittance": 0.05,
        "fib": 0.05,
    },
    EMBEDDING_TIER: {"scam": 0.40, "radar": 0.40},
}
UNLISTED_SHARE = 0.05
REFRESH_SECONDS = 15.0
# A Firestore call that hangs must not hold up a Gemini request; the Firestore client's own
# timeout is a minute.
STORE_TIMEOUT_SECONDS = 2.0

T = TypeVar("T")


class UsageStoreError(Exception):
    """The shared counts could not be read or written; the budget then goes on with its own."""


@dataclass
class DayUsage:
    """One day's counts: requests per (feature, tier), and the tiers Google has run dry."""

    calls: dict[tuple[str, str], int] = field(default_factory=dict)
    exhausted: set[str] = field(default_factory=set)


class UsageStore(Protocol):
    """Where the counts are shared between instances (sync, like the other repositories)."""

    def read(self, day: str) -> DayUsage: ...

    def add(self, day: str, feature: str, tier: str, count: int) -> None: ...

    def mark_exhausted(self, day: str, tier: str) -> None: ...


def _nth_sunday(year: int, month: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(6 - first.weekday()) % 7, weeks=n - 1)


def pacific_time(now: datetime) -> datetime:
    """Wall-clock time in US Pacific (naive). Google's daily quotas reset at midnight there.

    Written out instead of read from the time zone database, which the slim container and
    Windows do not carry. Daylight time runs from 02:00 on the second Sunday of March to 02:00
    on the first Sunday of November.
    """
    utc = now.astimezone(UTC)
    starts = datetime.combine(_nth_sunday(utc.year, 3, 2), day_time(10), tzinfo=UTC)
    ends = datetime.combine(_nth_sunday(utc.year, 11, 1), day_time(9), tzinfo=UTC)
    offset = timedelta(hours=-7 if starts <= utc < ends else -8)
    return (utc + offset).replace(tzinfo=None)


def budget_day(now: datetime) -> str:
    """The quota day `now` falls in, as the id of its `gemini_usage` document."""
    return pacific_time(now).date().isoformat()


def seconds_until_reset(now: datetime) -> int:
    """Whole seconds to the next midnight Pacific, at least 1 (used for `Retry-After`)."""
    local = pacific_time(now)
    midnight = datetime.combine(local.date() + timedelta(days=1), day_time.min)
    return max(1, math.ceil((midnight - local).total_seconds()))


def _utc_now() -> datetime:
    return datetime.now(UTC)


class GeminiBudget:
    """Counts Gemini requests per feature and tier for the quota day, and refuses past the limit.

    Args:
        store: Shared counts; None keeps them in this process only.
        rpd: Daily requests per tier (`reasoning`, `extraction`, `classification`, `embedding`).
            A tier not listed has no budget; Google's own 429 is still remembered for it.
        now, monotonic_clock: Clocks, replaced in tests.
    """

    def __init__(
        self,
        store: UsageStore | None = None,
        rpd: Mapping[str, int] | None = None,
        *,
        now: Callable[[], datetime] = _utc_now,
        monotonic_clock: Callable[[], float] = monotonic,
    ) -> None:
        self._store = store
        self._rpd = dict(rpd or {})
        self._now = now
        self._monotonic = monotonic_clock
        self._day = ""
        self._calls: dict[tuple[str, str], int] = {}
        self._exhausted: set[str] = set()
        self._loaded_at: float | None = None

    def limit_for(self, feature: str, tier: str) -> int | None:
        """The requests `feature` may make to `tier`'s model today, or None for no limit."""
        rpd = self._rpd.get(tier)
        if rpd is None:
            return None
        share = SHARES.get(tier, {}).get(feature, UNLISTED_SHARE)
        return max(1, math.floor(rpd * share))

    @asynccontextmanager
    async def attempt(self, feature: str, tier: str) -> AsyncIterator[None]:
        """Wrap ONE request to Gemini: refuse it if the day is spent, remember a spent day.

        Retries each open their own, since each one is a request against the quota.

        Raises:
            GeminiBudgetExhaustedError: Before the request is made.
        """
        await self.admit(feature, tier)
        try:
            yield
        except GeminiRateLimitError as exc:
            if exc.daily and not isinstance(exc, GeminiBudgetExhaustedError):
                await self.mark_exhausted(tier)
            raise

    async def admit(self, feature: str, tier: str) -> None:
        """Count one request for `feature` on `tier`, or raise if it may not be made."""
        now = self._now()
        day = budget_day(now)
        await self._sync(day)
        retry_after = seconds_until_reset(now)
        if tier in self._exhausted:
            self._log_blocked(feature, tier, "google", used=None, limit=None)
            raise GeminiBudgetExhaustedError(
                f"the {tier} model's daily quota is used up",
                source="google",
                retry_after_seconds=retry_after,
            )
        used = self._calls.get((feature, tier), 0)
        limit = self.limit_for(feature, tier)
        if limit is not None and used >= limit:
            self._log_blocked(feature, tier, "budget", used=used, limit=limit)
            raise GeminiBudgetExhaustedError(
                f"{feature} has used its {limit} {tier} requests for today",
                source="budget",
                retry_after_seconds=retry_after,
            )
        self._calls[(feature, tier)] = used + 1
        if self._store is not None:
            await self._shared(self._store.add, day, feature, tier, 1)

    async def mark_exhausted(self, tier: str) -> None:
        """Remember that Google refused `tier`'s model for the rest of the quota day."""
        day = budget_day(self._now())
        # Synced first, so the mark belongs to today's state even if the day turned since the
        # request was admitted (the next request would otherwise start a new day and drop it).
        await self._sync(day)
        if tier in self._exhausted:
            return
        self._exhausted.add(tier)
        logger.warning("gemini_quota_exhausted tier=%s", tier)
        if self._store is not None:
            await self._shared(self._store.mark_exhausted, day, tier)

    async def _sync(self, day: str) -> None:
        if day != self._day:
            self._day, self._calls, self._exhausted, self._loaded_at = day, {}, set(), None
        if self._store is None:
            return
        if self._loaded_at is not None and self._monotonic() - self._loaded_at < REFRESH_SECONDS:
            return
        # Stamped before the read, so a store that is down is asked again after the interval,
        # not by every request in the meantime.
        self._loaded_at = self._monotonic()
        remote = await self._shared(self._store.read, day)
        if remote is None:
            return
        for key, count in remote.calls.items():
            self._calls[key] = max(self._calls.get(key, 0), count)
        self._exhausted |= remote.exhausted

    async def _shared(self, call: Callable[..., T], *args: object) -> T | None:
        """Run a store call in a thread. The budget must never be the reason a request fails."""
        try:
            async with asyncio.timeout(STORE_TIMEOUT_SECONDS):
                return await run_in_threadpool(call, *args)
        except (UsageStoreError, TimeoutError) as exc:
            logger.warning(
                "gemini_budget_store_unavailable error=%s", str(exc) or type(exc).__name__
            )
            return None

    @staticmethod
    def _log_blocked(
        feature: str, tier: str, source: str, *, used: int | None, limit: int | None
    ) -> None:
        # Its own extra key, not `gemini_usage`: the line is not a request to Google.
        logger.warning(
            "gemini_budget_blocked feature=%s tier=%s source=%s used=%s limit=%s",
            feature,
            tier,
            source,
            used,
            limit,
            extra={
                "gemini_budget": {
                    "feature": feature,
                    "tier": tier,
                    "source": source,
                    "used": used,
                    "limit": limit,
                }
            },
        )
