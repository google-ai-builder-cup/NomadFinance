from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.constants import CURRENCY_PAIRS
from app.integrations.fx import FxQuote, FxResult, FxRouter, ProviderAttempt
from app.repositories.rate_repo import RateRepository
from app.services.remittance.rates import refresh_rates

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 27, 8, 41, 17, tzinfo=UTC)


class FakeFx:
    def __init__(self, failing_bases: frozenset[str] = frozenset()) -> None:
        self.failing_bases = failing_bases
        self.calls: list[tuple[str, list[str]]] = []

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxResult:
        self.calls.append((base, list(quotes)))
        if base in self.failing_bases:
            return FxResult(
                quote=None,
                provider=None,
                attempts=[ProviderAttempt("frankfurter", False, "timeout")],
            )
        rates = {quote: float(len(base) + len(quote)) for quote in quotes}
        return FxResult(
            quote=FxQuote(base=base, rates=rates, rate_date="2026-09-26"),
            provider="frankfurter",
            attempts=[ProviderAttempt("frankfurter", True)],
        )


class FakeRepo:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    def save_pair(
        self, pair: Any, quote: FxQuote, provider: str, attempts: Any, hour_start: datetime
    ) -> None:
        self.saved.append({"pair": pair.pair_id, "provider": provider, "hour": hour_start})


async def run(fx: FakeFx, repo: FakeRepo) -> Any:
    return await refresh_rates(fx=cast(FxRouter, fx), repo=cast(RateRepository, repo), now=NOW)


async def test_one_call_per_base_currency_and_all_pairs_saved() -> None:
    fx, repo = FakeFx(), FakeRepo()

    result = await run(fx, repo)

    assert sorted(fx.calls) == [
        ("AUD", ["INR", "PHP"]),
        ("JPY", ["PHP"]),
        ("MYR", ["IDR"]),
        ("SGD", ["PHP", "INR"]),
    ]
    assert sorted(item["pair"] for item in repo.saved) == sorted(p.pair_id for p in CURRENCY_PAIRS)
    assert {item["hour"] for item in repo.saved} == {datetime(2026, 9, 27, 8, tzinfo=UTC)}
    assert result.history_point == "2026-09-27T08"
    assert len(result.refreshed) == 6
    assert result.failed == []


async def test_a_failed_base_is_reported_and_the_rest_still_saved() -> None:
    fx, repo = FakeFx(failing_bases=frozenset({"AUD"})), FakeRepo()

    result = await run(fx, repo)

    assert sorted(item.pair for item in result.failed) == ["AUD_INR", "AUD_PHP"]
    assert result.failed[0].attempts[0].error == "timeout"
    assert len(result.refreshed) == 4
    assert all(not item["pair"].startswith("AUD") for item in repo.saved)
