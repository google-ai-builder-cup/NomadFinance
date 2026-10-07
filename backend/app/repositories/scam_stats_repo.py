from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client, FieldFilter

from app.repositories.base import get_firestore_client

# What a count needs from a stored check and nothing else: the field mask keeps the redacted
# text, the indicators and the explainer from even being read, let alone copied.
_COUNTED_FIELDS = (
    "corridor_id",
    "verdict.is_scam",
    "verdict.scam_type",
    "input_type",
    "reported_at",
)


class ScamStatsRepository:
    """`scam_stats/{corridor}/weeks/{iso_week}`: counts per corridor and week (scam.md).

    Reads the workers' stored checks across all users (a collection-group query on
    `created_at`, which needs its own index) and writes the counts. Backend only: no client
    rule matches `scam_stats`, so it is closed to browsers.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def checks_created_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """The counted fields of every check created in `[start, end)`, whoever's it is."""
        query = (
            self._client.collection_group("scam_checks")
            .where(filter=FieldFilter("created_at", ">=", start))
            .where(filter=FieldFilter("created_at", "<", end))
            .select(list(_COUNTED_FIELDS))
        )
        return [snapshot.to_dict() or {} for snapshot in query.stream()]

    def write_weeks(self, corridors: dict[str, dict[str, Any]], week: str, now: datetime) -> int:
        """Replace one week's document for every corridor in one batch; returns how many.

        `set` without a merge: the whole document is the answer, so a repeated run, or a run after
        a check was deleted, can only produce what is true now. The corridor's own document is
        written too, so the collection can be listed.
        """
        batch = self._client.batch()
        stats = self._client.collection("scam_stats")
        for corridor, data in corridors.items():
            parent = stats.document(corridor)
            batch.set(parent, {"corridor_id": corridor, "updated_at": now})
            batch.set(parent.collection("weeks").document(week), data)
        batch.commit()
        return len(corridors)


@lru_cache
def get_scam_stats_repository() -> ScamStatsRepository:
    return ScamStatsRepository(get_firestore_client())
