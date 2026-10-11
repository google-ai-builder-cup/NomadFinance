"""A real `GeminiBudget` in front of a fake Gemini client (NF-HR-010).

The fakes in this folder replace the whole `GeminiClient`, so they skip the daily budget. To see
how a feature behaves when its quota is spent, `GatedGemini` puts the real budget in front of any
of them: each call goes through `budget.attempt(feature, tier)` first, exactly as the client's
own attempts do, and is refused with the same `GeminiBudgetExhaustedError`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.integrations.gemini import GeminiBudget
from app.integrations.gemini.budget import EMBEDDING_TIER
from app.integrations.gemini.usage import feature_of

#: 10:00 Pacific on 12 November 2026, 14 hours before the quota day turns.
MORNING = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


class Clock:
    """A settable clock for the budget, so a test can let the quota day turn."""

    def __init__(self, now: datetime = MORNING) -> None:
        self.now = now

    def utc(self) -> datetime:
        return self.now


def make_budget(rpd: dict[str, int] | None = None, clock: Clock | None = None) -> GeminiBudget:
    """A budget that counts in this process, on `clock`."""
    clock = clock or Clock()
    return GeminiBudget(None, rpd, now=clock.utc)


class GatedGemini:
    """Refuses a call the budget would refuse; otherwise hands it to `inner`."""

    def __init__(self, inner: Any, budget: GeminiBudget) -> None:
        self.inner = inner
        self.budget = budget

    @property
    def calls(self) -> list[dict[str, Any]]:
        """The calls that got through to the fake."""
        calls: list[dict[str, Any]] = self.inner.calls
        return calls

    async def generate_structured(self, **kwargs: Any) -> Any:
        async with self.budget.attempt(feature_of(kwargs["operation"]), kwargs["tier"].value):
            return await self.inner.generate_structured(**kwargs)

    async def chat(self, **kwargs: Any) -> Any:
        async with self.budget.attempt(feature_of(kwargs["operation"]), kwargs["tier"].value):
            return await self.inner.chat(**kwargs)

    async def stream(self, **kwargs: Any) -> Any:
        async with self.budget.attempt(feature_of(kwargs["operation"]), kwargs["tier"].value):
            return await self.inner.stream(**kwargs)

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        async with self.budget.attempt(feature_of(operation), EMBEDDING_TIER):
            result: list[float] = await self.inner.embed_text(text, operation=operation)
            return result
