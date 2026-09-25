from __future__ import annotations

from collections.abc import Sequence

import httpx
from pydantic import SecretStr

from app.integrations.fx.base import FxProvider, FxProviderError, FxQuote, pick_rates


class WiseProvider(FxProvider):
    """Wise rates API, needs a personal API token. One request per currency pair."""

    name = "wise"
    url = "https://api.wise.com/v1/rates"

    def __init__(self, client: httpx.AsyncClient, api_token: SecretStr | None) -> None:
        super().__init__(client)
        self._api_token = api_token.get_secret_value().strip() if api_token else ""

    @property
    def configured(self) -> bool:
        return bool(self._api_token)

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        rates: dict[str, float] = {}
        rate_date = ""
        for quote in quotes:
            data = await self._get_json(
                self.url,
                params={"source": base, "target": quote},
                headers={"Authorization": f"Bearer {self._api_token}"},
            )
            # v1 answers with a one-item list; the newer dated API with a single object.
            entry = data[0] if isinstance(data, list) and data else data
            if not isinstance(entry, dict) or entry.get("target") != quote:
                raise FxProviderError("invalid_response")
            rates.update(pick_rates({quote: entry.get("rate")}, [quote]))
            rate_date = str(entry.get("time", ""))[:10]
        return FxQuote(base=base, rates=rates, rate_date=rate_date)
