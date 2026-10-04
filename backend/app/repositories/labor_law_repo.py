from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client

from app.repositories.base import FirestoreRepository, get_firestore_client


class LaborLawRepository(FirestoreRepository):
    """labor_laws/{country}, .../_meta/current and .../rules/{category} (labor_laws.md).

    Read-only from the backend: only the data-scripts loader (NF-P1-018) writes here.
    """

    collection_name = "labor_laws"

    def __init__(self, client: Client | None = None) -> None:
        super().__init__(client)
        # Curated law changes only when the loader bumps `_meta.version`, yet every contract
        # analysis and comparison reads all of a country's rules (15 documents). Kept per
        # country for as long as the version is unchanged (NF-P4-003).
        self._rules_by_country: dict[str, tuple[int, dict[str, dict[str, Any]]]] = {}

    def get_version(self, country: str) -> int | None:
        """The country's current `_meta/current.version`, or None if never loaded."""
        snapshot = self.document(country).collection("_meta").document("current").get()
        data = snapshot.to_dict()
        return int(data["version"]) if data else None

    def get_rules(self, country: str, version: int | None = None) -> dict[str, dict[str, Any]]:
        """Every curated rule of a country, keyed by category id; empty if none are loaded.

        Args:
            country: Host country code.
            version: The `_meta.version` the caller just read. When it matches what this
                instance already fetched, the rules are served without touching Firestore.
        """
        cached = self._rules_by_country.get(country)
        if version is not None and cached is not None and cached[0] == version:
            return copy.deepcopy(cached[1])
        result: dict[str, dict[str, Any]] = {}
        for doc in self.document(country).collection("rules").stream():
            data = doc.to_dict()
            if data is not None:
                result[doc.id] = data
        if version is not None and result:
            self._rules_by_country[country] = (version, copy.deepcopy(result))
        return result


@lru_cache
def get_labor_law_repository() -> LaborLawRepository:
    return LaborLawRepository(get_firestore_client())
