"""A small in-memory cache with a lifetime, and the log line that shows a cache's hit rate.

Each Cloud Run instance has its own copy, which is enough for what it holds: the answer to a
question that Gemini would answer the same way again (NF-HR-010). A value that must survive a
restart or be shared by instances belongs in Firestore, like the stored scam checks.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable
from time import monotonic
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

V = TypeVar("V")


class TtlCache(Generic[V]):
    """At most `max_entries` values, each forgotten `ttl_seconds` after it was stored.

    When full, the entry that was stored longest ago goes first. Not thread-safe, which is fine
    for the one event loop each worker runs its handlers on.
    """

    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._clock = clock
        self._items: OrderedDict[str, tuple[float, V]] = OrderedDict()

    def get(self, key: str) -> V | None:
        found = self._items.get(key)
        if found is None:
            return None
        stored_at, value = found
        if self._clock() - stored_at >= self._ttl:
            del self._items[key]
            return None
        return value

    def put(self, key: str, value: V) -> None:
        self._items.pop(key, None)
        self._items[key] = (self._clock(), value)
        while len(self._items) > self._max:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


def log_cache_lookup(feature: str, name: str, *, hit: bool) -> None:
    """One `cache_lookup` line per question put to a cache, for the `nf_cache_lookups` metric.

    A hit is a Gemini call (or several) that was not made, so the hit rate per feature is the
    quota the caches save.
    """
    result = "hit" if hit else "miss"
    logger.info(
        "cache_lookup feature=%s name=%s result=%s",
        feature,
        name,
        result,
        extra={"cache_lookup": {"feature": feature, "name": name, "result": result}},
    )
