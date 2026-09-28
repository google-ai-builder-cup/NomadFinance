from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.repositories.base import FirestoreRepository, get_firestore_client


class LaborLawRepository(FirestoreRepository):
    """labor_laws/{country}, .../_meta/current and .../rules/{category} (labor_laws.md).

    Read-only from the backend: only the data-scripts loader (NF-P1-018) writes here.
    """

    collection_name = "labor_laws"

    def get_version(self, country: str) -> int | None:
        """The country's current `_meta/current.version`, or None if never loaded."""
        snapshot = self.document(country).collection("_meta").document("current").get()
        data = snapshot.to_dict()
        return int(data["version"]) if data else None

    def get_rules(self, country: str) -> dict[str, dict[str, Any]]:
        """Every curated rule of a country, keyed by category id; empty if none are loaded."""
        result: dict[str, dict[str, Any]] = {}
        for doc in self.document(country).collection("rules").stream():
            data = doc.to_dict()
            if data is not None:
                result[doc.id] = data
        return result


@lru_cache
def get_labor_law_repository() -> LaborLawRepository:
    return LaborLawRepository(get_firestore_client())
