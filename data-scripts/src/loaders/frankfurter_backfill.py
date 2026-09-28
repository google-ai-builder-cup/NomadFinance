"""Backfill daily mid-market rates into `rates_history/{pair}.daily` (D-36, NF-P2-015).

Run from data-scripts/:  python -m src.loaders.frankfurter_backfill [--days 365] [--dry-run]

Frankfurter serves the European Central Bank's reference rates, one per working day, the same
source the rate cron asks first. The trend chart and the best-day and savings figures read the
`daily` map (docs/data-model/collections/rates_cache.md); the cron only adds days from its first
run on. A day already in the map is never overwritten, so the cron's own values win and
re-running the script changes nothing.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from google.cloud.firestore import Client
from pydantic import BaseModel, PositiveFloat

from src.config import CORRIDORS, Corridor
from src.firestore_client import get_firestore_client

log = logging.getLogger(__name__)

HISTORY_COLLECTION = "rates_history"
FRANKFURTER_URL = "https://api.frankfurter.dev/v1/{start}..{end}?base={base}&symbols={symbols}"
PROVIDER = "frankfurter"
TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class Pair:
    base: str
    quote: str

    @property
    def pair_id(self) -> str:
        return f"{self.base}_{self.quote}"


class FrankfurterSeries(BaseModel):
    """Frankfurter's time-series answer; `rates` is keyed by the working day."""

    base: str
    rates: dict[date, dict[str, PositiveFloat]]


def currency_pairs(corridors: tuple[Corridor, ...] = CORRIDORS) -> list[Pair]:
    """One pair per corridor, in corridor order; the same ids the backend's cron writes."""
    pairs: list[Pair] = []
    for corridor in corridors:
        pair = Pair(corridor.source_currency, corridor.destination_currency)
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def fetch_series(base: str, quotes: list[str], start: date, end: date) -> FrankfurterSeries:
    url = FRANKFURTER_URL.format(
        start=start.isoformat(), end=end.isoformat(), base=base, symbols=",".join(quotes)
    )
    request = urllib.request.Request(url, headers={"User-Agent": "nomadfinance-data-scripts"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return FrankfurterSeries.model_validate(json.load(response))


def new_entries(
    series: FrankfurterSeries, quote: str, existing: dict[str, Any], start: date
) -> dict[str, dict[str, Any]]:
    """Daily entries for the days the map lacks. Frankfurter starts a range on the working day
    before `start` when `start` is not one; that day is left out."""
    return {
        day.isoformat(): {"rate": rates[quote], "provider": PROVIDER, "source": "backfill"}
        for day, rates in sorted(series.rates.items())
        if day >= start and quote in rates and day.isoformat() not in existing
    }


def backfill_pair(
    client: Client, pair: Pair, series: FrankfurterSeries, start: date
) -> tuple[int, int]:
    """Merge the missing days into the pair's header; returns (days added, days kept)."""
    ref = client.collection(HISTORY_COLLECTION).document(pair.pair_id)
    snapshot = ref.get()
    data = snapshot.to_dict() if snapshot.exists else None
    existing = (data or {}).get("daily") or {}
    entries = new_entries(series, pair.quote, existing, start)
    if entries:
        ref.set(
            {"base_currency": pair.base, "quote_currency": pair.quote, "daily": entries},
            merge=True,
        )
    offered = sum(1 for day, rates in series.rates.items() if day >= start and pair.quote in rates)
    return len(entries), offered - len(entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill daily ECB rates into rates_history.")
    parser.add_argument("--days", type=int, default=365, help="Days back from --end (1 to 3650)")
    parser.add_argument(
        "--end", type=date.fromisoformat, default=None, help="Last day, YYYY-MM-DD (today UTC)"
    )
    parser.add_argument("--only", nargs="+", metavar="PAIR", help="Pair ids, e.g. SGD_PHP")
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch and report without touching Firestore"
    )
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 3650:
        parser.error("--days must be between 1 and 3650")

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    end: date = args.end or datetime.now(UTC).date()
    start = end - timedelta(days=args.days)
    pairs = currency_pairs()
    if args.only:
        unknown = set(args.only) - {pair.pair_id for pair in pairs}
        if unknown:
            parser.error(f"unknown pair ids: {', '.join(sorted(unknown))}")
        pairs = [pair for pair in pairs if pair.pair_id in args.only]

    client = None if args.dry_run else get_firestore_client()
    for base in dict.fromkeys(pair.base for pair in pairs):
        quotes = [pair.quote for pair in pairs if pair.base == base]
        series = fetch_series(base, quotes, start, end)
        for pair in (p for p in pairs if p.base == base):
            if client is None:
                offered = len(new_entries(series, pair.quote, {}, start))
                log.info("[dry-run] %s  %d days from %s to %s", pair.pair_id, offered, start, end)
                continue
            added, kept = backfill_pair(client, pair, series, start)
            log.info("%s  %3d days added, %3d already stored", pair.pair_id, added, kept)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
