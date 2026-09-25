from __future__ import annotations

from dataclasses import dataclass


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
