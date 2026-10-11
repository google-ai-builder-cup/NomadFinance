"""Stand-ins shared by the budget tests (NF-HR-010): a store held in a dict, a settable clock,
and the two kinds of 429 Google sends."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from google.genai import errors as genai_errors

from app.integrations.gemini import GeminiBudget
from app.integrations.gemini.budget import DayUsage, UsageStoreError

DAY_ONE = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)
DAILY_429 = genai_errors.ClientError(
    429,
    {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "quota",
            "details": [
                {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}
            ],
        }
    },
)
PER_MINUTE_429 = genai_errors.ClientError(
    429,
    {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "quota",
            "details": [{"violations": [{"quotaId": "GenerateRequestsPerMinutePerProject"}]}],
        }
    },
)


class FakeStore:
    """The shared counts, held in a dict; can be told to fail like a Firestore outage."""

    def __init__(self) -> None:
        self.days: dict[str, DayUsage] = {}
        self.down = False
        self.reads = 0

    def read(self, day: str) -> DayUsage:
        self.reads += 1
        if self.down:
            raise UsageStoreError("ServiceUnavailable")
        return copy.deepcopy(self.days.get(day, DayUsage()))

    def add(self, day: str, feature: str, tier: str, count: int) -> None:
        if self.down:
            raise UsageStoreError("ServiceUnavailable")
        usage = self.days.setdefault(day, DayUsage())
        usage.calls[(feature, tier)] = usage.calls.get((feature, tier), 0) + count

    def mark_exhausted(self, day: str, tier: str) -> None:
        if self.down:
            raise UsageStoreError("ServiceUnavailable")
        self.days.setdefault(day, DayUsage()).exhausted.add(tier)


class Clock:
    def __init__(self, now: datetime = DAY_ONE) -> None:
        self.now = now
        self.seconds = 1000.0

    def utc(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return self.seconds


def make_budget(
    rpd: dict[str, int] | None = None, store: FakeStore | None = None, clock: Clock | None = None
) -> tuple[GeminiBudget, FakeStore, Clock]:
    store = store if store is not None else FakeStore()
    clock = clock or Clock()
    budget = GeminiBudget(store, rpd, now=clock.utc, monotonic_clock=clock.monotonic)
    return budget, store, clock
