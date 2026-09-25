from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx


class FxProviderError(Exception):
    """A provider couldn't supply the rates. `code` is short and safe to store in Firestore."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FxQuote:
    """Mid-market rates for one base currency: units of each quote per 1 unit of base."""

    base: str
    rates: dict[str, float]
    rate_date: str  # YYYY-MM-DD, the day the provider says the rates are for


class FxProvider(ABC):
    """One source in the failover chain (ADR-006)."""

    name: str

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @property
    def configured(self) -> bool:
        """False when the provider needs a key that isn't set; the router then skips it."""
        return True

    @abstractmethod
    async def fetch(self, base: str, quotes: Sequence[str]) -> FxQuote:
        """Return rates for every currency in `quotes`, or raise FxProviderError."""

    async def _get_json(self, url: str, **kwargs: Any) -> Any:
        # Response bodies can echo the API key, so only short codes leave this method.
        try:
            response = await self._client.get(url, **kwargs)
        except httpx.TimeoutException as exc:
            raise FxProviderError("timeout") from exc
        except httpx.TransportError as exc:
            raise FxProviderError("network") from exc
        if response.status_code != 200:
            raise FxProviderError(f"http_{response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise FxProviderError("invalid_response") from exc


def pick_rates(available: dict[str, Any], quotes: Sequence[str]) -> dict[str, float]:
    """Keep the requested quotes, rejecting missing, non-numeric or non-positive rates."""
    rates: dict[str, float] = {}
    for quote in quotes:
        if quote not in available:
            raise FxProviderError("missing_quote")
        try:
            rate = float(available[quote])
        except (TypeError, ValueError) as exc:
            raise FxProviderError("invalid_response") from exc
        if not math.isfinite(rate) or rate <= 0:
            raise FxProviderError("invalid_response")
        rates[quote] = rate
    return rates
