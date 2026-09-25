from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from app.integrations.fx.base import FxProvider, FxProviderError, FxQuote, pick_rates


class ExchangeRateApiProvider(FxProvider):
    """ExchangeRate-API open access endpoint, no key, updated daily.

    Its terms require an attribution link wherever these rates are shown to users.
    """

    name = "exchangerate_api"
    url = "https://open.er-api.com/v6/latest/{base}"

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        data = await self._get_json(self.url.format(base=base))
        if (
            not isinstance(data, dict)
            or data.get("result") != "success"
            or not isinstance(data.get("rates"), dict)
            or not isinstance(data.get("time_last_update_unix"), int)
        ):
            raise FxProviderError("invalid_response")
        rate_date = datetime.fromtimestamp(data["time_last_update_unix"], tz=UTC).date()
        return FxQuote(
            base=base, rates=pick_rates(data["rates"], quotes), rate_date=rate_date.isoformat()
        )
