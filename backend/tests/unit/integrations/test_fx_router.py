from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.integrations.fx import FxProvider, FxProviderError, FxQuote, FxRouter, ProviderAttempt

pytestmark = pytest.mark.anyio


class FakeProvider(FxProvider):
    def __init__(self, name: str, outcome: FxQuote | str, configured: bool = True) -> None:
        self.name = name
        self._outcome = outcome
        self._configured = configured
        self.calls = 0

    @property
    def configured(self) -> bool:
        return self._configured

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        self.calls += 1
        if isinstance(self._outcome, str):
            raise FxProviderError(self._outcome)
        return self._outcome


QUOTE = FxQuote(base="SGD", rates={"PHP": 49.0}, rate_date="2026-09-25")


async def test_first_working_provider_wins() -> None:
    first, second = FakeProvider("a", QUOTE), FakeProvider("b", QUOTE)

    result = await FxRouter([first, second]).fetch("SGD", ["PHP"])

    assert result.provider == "a"
    assert result.quote == QUOTE
    assert result.attempts == [ProviderAttempt("a", ok=True)]
    assert second.calls == 0


async def test_fails_over_and_records_every_attempt() -> None:
    providers = [
        FakeProvider("frankfurter", "timeout"),
        FakeProvider("exchangerate_api", "http_503"),
        FakeProvider("currencyfreaks", QUOTE, configured=False),
        FakeProvider("wise", QUOTE),
    ]

    result = await FxRouter(providers).fetch("SGD", ["PHP"])

    assert result.provider == "wise"
    assert result.attempts == [
        ProviderAttempt("frankfurter", ok=False, error="timeout"),
        ProviderAttempt("exchangerate_api", ok=False, error="http_503"),
        ProviderAttempt("currencyfreaks", ok=False, error="not_configured"),
        ProviderAttempt("wise", ok=True),
    ]
    assert providers[2].calls == 0


async def test_all_providers_failing_returns_no_quote() -> None:
    result = await FxRouter(
        [FakeProvider("a", "network"), FakeProvider("b", "missing_quote")]
    ).fetch("SGD", ["PHP"])

    assert result.quote is None
    assert result.provider is None
    assert [attempt.error for attempt in result.attempts] == ["network", "missing_quote"]
