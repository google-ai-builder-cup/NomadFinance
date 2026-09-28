from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
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

    def get_history(self, pair_id: str) -> dict[str, Any] | None:
        """The rates_history header of a pair, with its `daily` map, or None if never written.

        The map holds one rate per market day, so a year of history is one read instead of
        thousands of hourly points.
        """
        snapshot = self._client.collection("rates_history").document(pair_id).get()
        return snapshot.to_dict() if snapshot.exists else None

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
        point instead of adding a duplicate. The header's `daily` map gets the rate under the
        provider's own date (a weekend run repeats Friday's rate, so it only rewrites Friday);
        the merge keeps every other day.
        """
        rate = quote.rates[pair.quote]
        try:
            day = date.fromisoformat(quote.rate_date).isoformat()
        except ValueError:
            day = hour_start.date().isoformat()
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
                "daily": {day: {"rate": rate, "provider": provider, "source": "cron"}},
            },
            merge=True,
        )
        batch.set(
            history.collection("points").document(hour_start.strftime("%Y-%m-%dT%H")),
            {"at": hour_start, "rate": rate, "provider": provider, "source": "cron"},
        )
        batch.commit()


@lru_cache
def get_rate_repository() -> RateRepository:
    return RateRepository(get_firestore_client())
