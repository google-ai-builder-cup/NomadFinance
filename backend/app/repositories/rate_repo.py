from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from app.constants import CurrencyPair
from app.integrations.fx import FxQuote, ProviderAttempt
from app.repositories.base import FirestoreRepository, get_firestore_client


class RateRepository(FirestoreRepository):
    """rates_cache/{pair} and rates_history/{pair}/points/{hour} (collections/rates_cache.md)."""

    collection_name = "rates_cache"

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        """The latest cached rate of a pair such as `SGD_PHP`, or None if the cron never ran."""
        return self.get(pair_id)

    def save_pair(
        self,
        pair: CurrencyPair,
        quote: FxQuote,
        provider: str,
        attempts: list[ProviderAttempt],
        hour_start: datetime,
    ) -> None:
        """Write the latest rate, the history header and the hourly point in one batch.

        The point id is the UTC hour, so a second run in the same hour overwrites the
        point instead of adding a duplicate.
        """
        rate = quote.rates[pair.quote]
        history = self._client.collection("rates_history").document(pair.pair_id)
        batch = self._client.batch()
        batch.set(
            self.document(pair.pair_id),
            {
                "base_currency": pair.base,
                "quote_currency": pair.quote,
                "rate": rate,
                "provider": provider,
                "rate_date": quote.rate_date,
                "fetched_at": firestore.SERVER_TIMESTAMP,
                "attempts": [
                    {k: v for k, v in asdict(a).items() if v is not None} for a in attempts
                ],
                "corridor_ids": list(pair.corridor_ids),
                "schema_version": 1,
            },
        )
        batch.set(
            history,
            {
                "base_currency": pair.base,
                "quote_currency": pair.quote,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
        )
        batch.set(
            history.collection("points").document(hour_start.strftime("%Y-%m-%dT%H")),
            {"at": hour_start, "rate": rate, "provider": provider, "source": "cron"},
        )
        batch.commit()


@lru_cache
def get_rate_repository() -> RateRepository:
    return RateRepository(get_firestore_client())
