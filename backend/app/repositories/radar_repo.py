from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from google.cloud.firestore import CollectionReference
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.repositories.base import FirestoreRepository, get_firestore_client
from app.schemas.radar import RadarReport

EMBEDDINGS_COLLECTION = "report_embeddings"


@dataclass(frozen=True)
class SimilarReport:
    """One `report_embeddings` neighbour. `distance` is cosine distance (0 = identical)."""

    report_id: str
    entity_slug: str
    distance: float


class RadarRepository(FirestoreRepository):
    """radar_reports/{id} (docs/data-model/collections/radar.md).

    Reports are written here (NF-P2-021, NF-P3-001); NF-P3-002 adds the similar-report search
    over `report_embeddings/{id}`. Entity aggregation (NF-P3-003) adds its own methods later.
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

    @property
    def _embeddings(self) -> CollectionReference:
        return self._client.collection(EMBEDDINGS_COLLECTION)

    def get_cluster_id(self, report_id: str) -> str | None:
        """The `cluster_id` of an existing report, or None if it is gone."""
        data = self.get(report_id)
        return None if data is None else str(data["cluster_id"])

    def find_similar(
        self, embedding: list[float], corridor_id: str, limit: int
    ) -> list[SimilarReport]:
        """Nearest stored reports on one corridor, closest first.

        Needs the vector index on `report_embeddings` (`corridor_id` asc + `embedding`,
        dimension 768; docs/data-model/firestore-schema.md). Without it Firestore rejects
        the query.
        """
        query = self._embeddings.where(filter=FieldFilter("corridor_id", "==", corridor_id))
        neighbours = query.find_nearest(
            vector_field="embedding",
            query_vector=Vector(embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
            distance_result_field="distance",
        ).stream()  # type: ignore[call-arg]  # SDK annotates find_nearest's return unbound
        return [
            SimilarReport(
                report_id=doc.id,
                entity_slug=str(doc.get("entity_slug")),
                distance=float(doc.get("distance")),
            )
            for doc in neighbours
        ]

    def create_embedding(
        self,
        report_id: str,
        embedding: list[float],
        *,
        model: str,
        corridor_id: str | None,
        entity_type: str,
        entity_slug: str,
        created_at: datetime,
    ) -> None:
        """Write `report_embeddings/{report_id}` (same id as the report)."""
        data: dict[str, object] = {
            "embedding": Vector(embedding),
            "embedding_model": model,
            "dimension": len(embedding),
            "entity_type": entity_type,
            "entity_slug": entity_slug,
            "created_at": created_at,
        }
        if corridor_id is not None:
            data["corridor_id"] = corridor_id
        self._embeddings.document(report_id).set(data)


@lru_cache
def get_radar_repository() -> RadarRepository:
    return RadarRepository(get_firestore_client())
