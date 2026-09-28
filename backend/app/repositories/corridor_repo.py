from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.repositories.base import FirestoreRepository, get_firestore_client


class CorridorRepository(FirestoreRepository):
    """corridors/{corridor_id}: the surveyed providers of one corridor (corridors.md).

    Read-only from the backend: only the data-scripts loader (NF-P1-016) writes here. The
    providers sit inside the document, so one read returns everything a comparison needs.
    """

    collection_name = "corridors"

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        """The corridor document, or None if it was never loaded."""
        return self.get(corridor_id)


@lru_cache
def get_corridor_repository() -> CorridorRepository:
    return CorridorRepository(get_firestore_client())
