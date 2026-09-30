from __future__ import annotations

from functools import lru_cache

from app.repositories.base import FirestoreRepository, get_firestore_client
from app.schemas.radar import RadarReport


class RadarRepository(FirestoreRepository):
    """radar_reports/{id} (docs/data-model/collections/radar.md).

    Write-only from here: only what the contract signal needs (NF-P2-021). Reading,
    embedding, clustering and entity aggregation belong to NF-P3-001 to NF-P3-003, which add
    their own methods to this repository when they are built.
    """

    collection_name = "radar_reports"

    def new_report_id(self) -> str:
        """A fresh id for a report, assigned but not yet written.

        `radar_reports` documents have no natural id (unlike `labor_laws/{country}`), and a
        report's own id doubles as its `cluster_id` when it starts a new cluster
        (radar.md), so the id must exist before the report is built, not after.
        """
        return str(self.collection.document().id)

    def create_report(self, report_id: str, report: RadarReport) -> None:
        """Write one report under `report_id` (from `new_report_id`)."""
        # Not mode="json": created_at must stay a real datetime, so the Firestore SDK stores
        # it as a Timestamp (sortable, TTL-eligible), the same as every other repository here.
        self.document(report_id).set(report.model_dump(exclude_none=True))


@lru_cache
def get_radar_repository() -> RadarRepository:
    return RadarRepository(get_firestore_client())
