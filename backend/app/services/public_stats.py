from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.schemas.public_stats import PublicStatsResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")

# The landing page is public, so every visitor would otherwise cost a handful of Firestore
# aggregation reads. A few minutes old is fine for a running total.
CACHE_SECONDS = 300


class StatsReader(Protocol):
    def workers(self) -> int: ...
    def contracts_checked(self) -> int: ...
    def radar_reports(self) -> int: ...
    def alerts_generated(self) -> int: ...
    def scam_checks(self) -> tuple[int, int]: ...
    def coach_plans(self) -> int: ...


_cache: tuple[float, PublicStatsResponse] | None = None


def clear_cache() -> None:
    global _cache
    _cache = None


def _read(label: str, read: Callable[[], T]) -> T | None:
    """One total, or `None` when Firestore could not give it (a missing index, a timeout), so
    one bad count never takes the others down with it."""
    try:
        return read()
    except GoogleAPICallError:
        logger.warning("public stat %s could not be read", label, exc_info=True)
        return None


def _collect(reader: StatsReader, now: datetime) -> PublicStatsResponse:
    scam = _read("scam_checks", reader.scam_checks)
    return PublicStatsResponse(
        workers=_read("workers", reader.workers),
        contracts_checked=_read("contracts_checked", reader.contracts_checked),
        radar_reports=_read("radar_reports", reader.radar_reports),
        alerts_generated=_read("alerts_generated", reader.alerts_generated),
        scam_messages_checked=scam[0] if scam else None,
        scams_flagged=scam[1] if scam else None,
        coach_plans=_read("coach_plans", reader.coach_plans),
        generated_at=now,
    )


async def get_public_stats(reader: StatsReader) -> PublicStatsResponse:
    """The platform totals, recomputed at most once every `CACHE_SECONDS` per instance."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_SECONDS:
        return _cache[1]
    stats = await run_in_threadpool(_collect, reader, datetime.now(UTC))
    _cache = (now, stats)
    return stats
