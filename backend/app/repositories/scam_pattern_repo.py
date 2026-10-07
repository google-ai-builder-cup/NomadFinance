from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.repositories.base import FirestoreRepository, get_firestore_client


@dataclass(frozen=True)
class SimilarPattern:
    """One `scam_patterns` neighbour. `distance` is cosine distance (0 = identical).

    Carries the id and the type only: the template's text never leaves the repository, because
    a known template shown to a scammer's next victim, or to the scammer, is a gift (scam.md).
    """

    pattern_id: str
    scam_type: str
    distance: float


class ScamPatternRepository(FirestoreRepository):
    """scam_patterns/{id} (docs/data-model/collections/scam.md).

    Read-only from the backend: only the data-scripts loader (NF-SA-006) writes here.
    """

    collection_name = "scam_patterns"

    def find_similar(self, embedding: list[float], limit: int) -> list[SimilarPattern]:
        """The `limit` nearest templates of any type and language, closest first.

        Needs the flat vector index on `scam_patterns.embedding`, dimension 768
        (`frontend/firestore.indexes.json`). Without it, or with the collection empty, the
        caller gets a Firestore error or an empty list.
        """
        neighbours = self.collection.find_nearest(
            vector_field="embedding",
            query_vector=Vector(embedding),
            distance_measure=DistanceMeasure.COSINE,
            limit=limit,
            distance_result_field="distance",
        ).stream()
        return [
            SimilarPattern(
                pattern_id=doc.id,
                scam_type=str(doc.get("scam_type")),
                distance=float(doc.get("distance")),
            )
            for doc in neighbours
        ]


@lru_cache
def get_scam_pattern_repository() -> ScamPatternRepository:
    return ScamPatternRepository(get_firestore_client())
