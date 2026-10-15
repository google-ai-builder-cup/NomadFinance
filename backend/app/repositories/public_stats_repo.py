from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client, FieldFilter

from app.repositories.base import get_firestore_client


class PublicStatsRepository:
    """Platform-wide totals, read as Firestore aggregation queries (`count`, `sum`).

    An aggregation returns one number and reads no document, so nothing a worker wrote reaches
    this process, let alone a browser. Backend only: no client rule matches these reads.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    # The SDK's aggregation methods (`count`, `sum`, `get`) are untyped and mypy reads `get` as
    # an unbound call, so the query goes in as `Any` and the answer comes out as an int.
    @staticmethod
    def _count(query: Any) -> int:
        # An aggregation answers `[[AggregationResult]]`: one row, one number.
        return int(query.count().get()[0][0].value or 0)

    @staticmethod
    def _sum(query: Any, field: str) -> int:
        return int(query.sum(field).get()[0][0].value or 0)

    def workers(self) -> int:
        return self._count(self._client.collection("users"))

    def contracts_checked(self) -> int:
        # An equality filter on a collection group needs a collection-group index on `status`.
        # Without it this raises, and the service leaves the figure out rather than counting
        # contracts that were uploaded but never analysed.
        query = self._client.collection_group("contracts").where(
            filter=FieldFilter("status", "==", "completed")
        )
        return self._count(query)

    def radar_reports(self) -> int:
        reports = self._client.collection("radar_reports")
        hidden = reports.where(filter=FieldFilter("hidden", "==", True))
        return max(self._count(reports) - self._count(hidden), 0)

    def alerts_generated(self) -> int:
        # `radar_alerts/{corridor}/current/{alertId}`: expired alerts stay, so this is all-time.
        return self._count(self._client.collection_group("current"))

    def scam_checks(self) -> tuple[int, int]:
        """`(checks, scams)` summed over every `scam_stats/{corridor}/weeks/{week}` document.

        The checks themselves are deleted after 90 days; the weekly counts are not, so this is
        the running total the job has recorded.
        """
        weeks = self._client.collection_group("weeks")
        return self._sum(weeks, "checks"), self._sum(weeks, "scams")


@lru_cache
def get_public_stats_repository() -> PublicStatsRepository:
    return PublicStatsRepository(get_firestore_client())
