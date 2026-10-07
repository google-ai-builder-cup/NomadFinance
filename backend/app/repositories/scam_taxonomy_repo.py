from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client, FieldFilter

from app.repositories.base import FirestoreRepository, get_firestore_client


@dataclass(frozen=True)
class ScamTaxonomy:
    """The scam types and manipulation tactics at one taxonomy version, each keyed by id."""

    version: int
    types: dict[str, dict[str, Any]]
    tactics: dict[str, dict[str, Any]]


class ScamTaxonomyRepository(FirestoreRepository):
    """scam_taxonomy/{id} and scam_taxonomy/_meta (scam.md).

    Read-only from the backend: only the data-scripts loader (NF-SA-001) writes here.
    """

    collection_name = "scam_taxonomy"

    def __init__(self, client: Client | None = None) -> None:
        super().__init__(client)
        # The taxonomy changes only when the loader raises `_meta.version`, yet every check
        # reads all of it (14 documents). Kept while the version is unchanged, as the
        # labor-law rules are.
        self._cached: ScamTaxonomy | None = None

    def get_taxonomy(self) -> ScamTaxonomy | None:
        """The current taxonomy, or None when the loader has never run."""
        meta = self.get("_meta")
        if not meta:
            return None
        version = int(meta["version"])
        if self._cached is not None and self._cached.version == version:
            return self._cached

        types: dict[str, dict[str, Any]] = {}
        tactics: dict[str, dict[str, Any]] = {}
        # `in` on `kind` leaves `_meta` out, which has no such field.
        query = self.collection.where(filter=FieldFilter("kind", "in", ["type", "tactic"]))
        for doc in sorted(query.stream(), key=lambda d: (d.to_dict() or {}).get("order", 0)):
            data = doc.to_dict()
            if data is not None:
                (types if data["kind"] == "type" else tactics)[doc.id] = data
        if not types or not tactics:
            return None
        self._cached = ScamTaxonomy(version=version, types=types, tactics=tactics)
        return self._cached


@lru_cache
def get_scam_taxonomy_repository() -> ScamTaxonomyRepository:
    return ScamTaxonomyRepository(get_firestore_client())
