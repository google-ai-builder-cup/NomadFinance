from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any

from google.cloud.firestore import CollectionReference
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.repositories.base import FirestoreRepository, get_firestore_client
from app.schemas.radar import RadarEntity, RadarReport
from app.schemas.radar_alert import RadarAlert, RadarAlertHeader

EMBEDDINGS_COLLECTION = "report_embeddings"
ENTITIES_COLLECTION = "radar_entities"
ALERTS_COLLECTION = "radar_alerts"
ALERTS_SUBCOLLECTION = "current"


@dataclass(frozen=True)
class SimilarReport:
    """One `report_embeddings` neighbour. `distance` is cosine distance (0 = identical)."""

    report_id: str
    entity_slug: str
    distance: float


class RadarRepository(FirestoreRepository):
    """radar_reports/{id} (docs/data-model/collections/radar.md).

    Reports are written here (NF-P2-021, NF-P3-001); NF-P3-002 added the similar-report search
    over `report_embeddings/{id}`; NF-P3-003 adds the `radar_entities/{slug}` methods below.
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

    @property
    def _entities(self) -> CollectionReference:
        return self._client.collection(ENTITIES_COLLECTION)

    def get_entity(self, slug: str) -> dict[str, Any] | None:
        """The stored profile of one entity, or None if it has no reports yet."""
        snapshot = self._entities.document(slug).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set_entity(self, entity: RadarEntity) -> None:
        """Overwrite `radar_entities/{entity.slug}` with the freshly recomputed profile."""
        # Not mode="json": the three timestamps must stay real datetimes (Firestore Timestamp,
        # same reasoning as create_report), and community_rating's null is meaningful, not
        # an absent field, so this does not exclude_none either.
        self._entities.document(entity.slug).set(entity.model_dump())

    def reports_since(self, corridor_id: str, since: datetime) -> list[dict[str, Any]]:
        """Every report on one corridor created at or after `since`, for surge detection.

        Needs the composite index `corridor_id` asc + `created_at` desc
        (docs/data-model/firestore-schema.md); without it Firestore rejects the query.
        """
        query = self.collection.where(filter=FieldFilter("corridor_id", "==", corridor_id)).where(
            filter=FieldFilter("created_at", ">=", since)
        )
        return [data for doc in query.stream() if (data := doc.to_dict()) is not None]

    @property
    def _alerts(self) -> CollectionReference:
        return self._client.collection(ALERTS_COLLECTION)

    def _alert_current(self, corridor_id: str) -> CollectionReference:
        # DocumentReference.collection()'s stub returns Any.
        return self._alerts.document(corridor_id).collection(ALERTS_SUBCOLLECTION)  # type: ignore[no-any-return]

    def get_alert_header(self, corridor_id: str) -> dict[str, Any] | None:
        snapshot = self._alerts.document(corridor_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set_alert_header(self, header: RadarAlertHeader) -> None:
        self._alerts.document(header.corridor_id).set(header.model_dump())

    def get_active_alert(self, corridor_id: str, entity_slug: str) -> dict[str, Any] | None:
        """The entity's currently active alert on this corridor, if any (for dedup)."""
        query = (
            self._alert_current(corridor_id)
            .where(filter=FieldFilter("entity_slug", "==", entity_slug))
            .where(filter=FieldFilter("status", "==", "active"))
            .limit(1)
        )
        docs = list(query.stream())
        return docs[0].to_dict() if docs else None

    def new_alert_id(self, corridor_id: str) -> str:
        return str(self._alert_current(corridor_id).document().id)

    def create_alert(self, corridor_id: str, alert_id: str, alert: RadarAlert) -> None:
        self._alert_current(corridor_id).document(alert_id).set(alert.model_dump(exclude_none=True))

    def list_active_alerts(self, corridor_id: str) -> list[tuple[str, dict[str, Any]]]:
        """Every currently active alert on one corridor, for the expiry sweep."""
        query = self._alert_current(corridor_id).where(filter=FieldFilter("status", "==", "active"))
        return [(doc.id, data) for doc in query.stream() if (data := doc.to_dict()) is not None]

    def expire_alert(self, corridor_id: str, alert_id: str) -> None:
        self._alert_current(corridor_id).document(alert_id).update({"status": "expired"})

    def set_alert_notified(self, corridor_id: str, alert_id: str, notified_at: datetime) -> None:
        self._alert_current(corridor_id).document(alert_id).update({"notified_at": notified_at})


@lru_cache
def get_radar_repository() -> RadarRepository:
    return RadarRepository(get_firestore_client())
