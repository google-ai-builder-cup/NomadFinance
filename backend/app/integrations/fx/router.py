from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import Settings, get_settings
from app.integrations.fx.base import FxProvider, FxProviderError, FxQuote
from app.integrations.fx.currencyfreaks import CurrencyFreaksProvider
from app.integrations.fx.exchangerate_api import ExchangeRateApiProvider
from app.integrations.fx.frankfurter import FrankfurterProvider
from app.integrations.fx.wise import WiseProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    ok: bool
    error: str | None = None


@dataclass
class FxResult:
    """Outcome for one base currency: the quote, or None when every provider failed."""

    quote: FxQuote | None
    provider: str | None
    attempts: list[ProviderAttempt] = field(default_factory=list)


class FxRouter:
    """Tries providers in order and returns the first complete answer (ADR-006)."""

    def __init__(self, providers: Sequence[FxProvider]) -> None:
        self._providers = providers

    async def fetch(self, base: str, quotes: Sequence[str]) -> FxResult:
        attempts: list[ProviderAttempt] = []
        for provider in self._providers:
            if not provider.configured:
                attempts.append(ProviderAttempt(provider.name, ok=False, error="not_configured"))
                continue
            try:
                quote = await provider.fetch(base, quotes)
            except FxProviderError as exc:
                attempts.append(ProviderAttempt(provider.name, ok=False, error=exc.code))
                logger.warning(
                    "fx_provider_failed provider=%s base=%s error=%s", provider.name, base, exc.code
                )
                continue
            attempts.append(ProviderAttempt(provider.name, ok=True))
            return FxResult(quote=quote, provider=provider.name, attempts=attempts)
        return FxResult(quote=None, provider=None, attempts=attempts)


def build_fx_router(settings: Settings, client: httpx.AsyncClient) -> FxRouter:
    """The production chain: Frankfurter → ExchangeRate-API → CurrencyFreaks → Wise."""
    return FxRouter(
        [
            FrankfurterProvider(client),
            ExchangeRateApiProvider(client),
            CurrencyFreaksProvider(client, settings.currencyfreaks_api_key),
            WiseProvider(client, settings.wise_api_token),
        ]
    )


async def get_fx_router(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[FxRouter]:
    """FastAPI dependency: a router with one HTTP connection pool per request."""
    async with httpx.AsyncClient(timeout=settings.fx_timeout_seconds) as client:
        yield build_fx_router(settings, client)
