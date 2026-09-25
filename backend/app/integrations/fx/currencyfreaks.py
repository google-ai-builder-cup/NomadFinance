from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import SecretStr

from app.integrations.fx.base import FxProvider, FxProviderError, FxQuote, pick_rates


class CurrencyFreaksProvider(FxProvider):
    """CurrencyFreaks, needs an API key. Rates arrive as strings."""

    name = "currencyfreaks"
    url = "https://api.currencyfreaks.com/v2.0/rates/latest"

    def __init__(self, client: httpx.AsyncClient, api_key: SecretStr | None) -> None:
        super().__init__(client)
        self._api_key = api_key.get_secret_value().strip() if api_key else ""

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        # The free plan only quotes from USD, so fetch USD→base and USD→quote and divide.
        symbols = [base, *quotes]
        data = await self._get_json(
            self.url, params={"apikey": self._api_key, "symbols": ",".join(symbols)}
        )
        if not isinstance(data, dict) or not isinstance(data.get("rates"), dict):
            raise FxProviderError("invalid_response")
        usd_rates = pick_rates(data["rates"], symbols)
        rates = {quote: usd_rates[quote] / usd_rates[base] for quote in quotes}
        # "date" looks like "2026-08-25 12:43:00+00".
        return FxQuote(base=base, rates=rates, rate_date=str(data.get("date", ""))[:10])
