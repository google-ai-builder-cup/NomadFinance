from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class CurrencyPair:
    """One FX pair the corridors need. `pair_id` is the Firestore document id."""

    base: str
    quote: str
    corridor_ids: tuple[str, ...]

    @property
    def pair_id(self) -> str:
        return f"{self.base}_{self.quote}"


# Source → destination currency of the six corridors (docs/data-model/collections/rates_cache.md).
CURRENCY_PAIRS: tuple[CurrencyPair, ...] = (
    CurrencyPair("SGD", "PHP", ("SG-PH",)),
    CurrencyPair("SGD", "INR", ("SG-IN",)),
    CurrencyPair("AUD", "INR", ("AU-IN",)),
    CurrencyPair("MYR", "IDR", ("MY-ID",)),
    CurrencyPair("JPY", "PHP", ("JP-PH",)),
    CurrencyPair("AUD", "PHP", ("AU-PH",)),
)


# A cached rate older than this is flagged stale: the cron runs every 1 to 2 hours
# (docs/data-model/collections/rates_cache.md), so this means at least two runs failed.
RATE_MAX_AGE = timedelta(hours=6)


def pair_for_corridor(corridor_id: str) -> CurrencyPair:
    """The FX pair a corridor's live rate is stored under.

    Raises:
        KeyError: The id is not one of the six corridors.
    """
    for pair in CURRENCY_PAIRS:
        if corridor_id in pair.corridor_ids:
            return pair
    raise KeyError(corridor_id)
