from __future__ import annotations

from collections.abc import Sequence

from app.integrations.fx.base import FxProvider, FxProviderError, FxQuote, pick_rates


class FrankfurterProvider(FxProvider):
    """European Central Bank reference rates, no key. Published once per working day."""

    name = "frankfurter"
    url = "https://api.frankfurter.dev/v1/latest"

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        data = await self._get_json(self.url, params={"base": base, "symbols": ",".join(quotes)})
        if not isinstance(data, dict) or not isinstance(data.get("rates"), dict):
            raise FxProviderError("invalid_response")
        return FxQuote(
            base=base, rates=pick_rates(data["rates"], quotes), rate_date=str(data.get("date"))
        )
