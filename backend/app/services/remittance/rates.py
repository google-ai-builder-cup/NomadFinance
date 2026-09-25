from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from app.constants import CURRENCY_PAIRS, CurrencyPair
from app.integrations.fx import FxResult, FxRouter
from app.repositories.rate_repo import RateRepository
from app.schemas.remittance import (
    FailedPair,
    ProviderAttemptOut,
    RefreshedPair,
    RefreshRatesResponse,
)

logger = logging.getLogger(__name__)


def _pairs_by_base() -> dict[str, list[CurrencyPair]]:
    grouped: dict[str, list[CurrencyPair]] = {}
    for pair in CURRENCY_PAIRS:
        grouped.setdefault(pair.base, []).append(pair)
    return grouped


async def refresh_rates(
    *, fx: FxRouter, repo: RateRepository, now: datetime
) -> RefreshRatesResponse:
    """Fetch the latest rate for every corridor pair and store it in Firestore.

    One provider call covers all pairs sharing a base currency. A base whose whole
    failover chain fails is reported in `failed`; the other pairs are still saved.

    Args:
        fx: Provider failover chain.
        repo: Firestore writer for rates_cache and rates_history.
        now: Current UTC time; its hour names the history point.
    """
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    grouped = _pairs_by_base()
    # Bases are independent, so fetch them together: the worst case stays one chain of timeouts.
    results: list[FxResult] = await asyncio.gather(
        *(fx.fetch(base, [pair.quote for pair in pairs]) for base, pairs in grouped.items())
    )

    refreshed: list[RefreshedPair] = []
    failed: list[FailedPair] = []
    for pairs, result in zip(grouped.values(), results, strict=True):
        attempts = [ProviderAttemptOut(**vars(attempt)) for attempt in result.attempts]
        if result.quote is None or result.provider is None:
            failed.extend(FailedPair(pair=pair.pair_id, attempts=attempts) for pair in pairs)
            continue
        for pair in pairs:
            # The Firestore SDK is synchronous; keep it off the event loop.
            await asyncio.to_thread(
                repo.save_pair, pair, result.quote, result.provider, result.attempts, hour_start
            )
            refreshed.append(
                RefreshedPair(
                    pair=pair.pair_id,
                    rate=result.quote.rates[pair.quote],
                    provider=result.provider,
                    rate_date=result.quote.rate_date,
                )
            )

    logger.info(
        "rates_refresh refreshed=%d failed=%d point=%s providers=%s",
        len(refreshed),
        len(failed),
        hour_start.strftime("%Y-%m-%dT%H"),
        sorted({item.provider for item in refreshed}),
    )
    return RefreshRatesResponse(
        history_point=hour_start.strftime("%Y-%m-%dT%H"),
        refreshed=refreshed,
        failed=failed,
        completed_at=now,
    )
