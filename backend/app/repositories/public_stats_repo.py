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

    @staticmethod
    def _value(result: Any) -> int:
        # An aggregation answers `[[AggregationResult]]`: one row, one number.
        return int(result[0][0].value or 0)

    def workers(self) -> int:
        return self._value(self._client.collection("users").count().get())

    def contracts_checked(self) -> int:
        # An equality filter on a collection group needs a collection-group index on `status`.
        # Without it this raises, and the service leaves the figure out rather than counting
        # contracts that were uploaded but never analysed.
        query = self._client.collection_group("contracts").where(
            filter=FieldFilter("status", "==", "completed")
        )
        return self._value(query.count().get())

    def radar_reports(self) -> int:
        reports = self._client.collection("radar_reports")
        total = self._value(reports.count().get())
        hidden = self._value(reports.where(filter=FieldFilter("hidden", "==", True)).count().get())
        return max(total - hidden, 0)

    def alerts_generated(self) -> int:
        # `radar_alerts/{corridor}/current/{alertId}`: expired alerts stay, so this is all-time.
        return self._value(self._client.collection_group("current").count().get())

    def scam_checks(self) -> tuple[int, int]:
        """`(checks, scams)` summed over every `scam_stats/{corridor}/weeks/{week}` document.

        The checks themselves are deleted after 90 days; the weekly counts are not, so this is
        the running total the job has recorded.
        """
        weeks = self._client.collection_group("weeks")
        checks = self._value(weeks.sum("checks").get())
        scams = self._value(weeks.sum("scams").get())
        return checks, scams

    def coach_plans(self) -> int:
        return self._value(self._client.collection_group("coach_plans").count().get())


@lru_cache
def get_public_stats_repository() -> PublicStatsRepository:
    return PublicStatsRepository(get_firestore_client())
