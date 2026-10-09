from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.repositories.base import FirestoreRepository, get_firestore_client


class CostBaselineRepository(FirestoreRepository):
    """cost_baselines/{host}: monthly living costs of a host country (cost_baselines.md).

    Written by the data-scripts loader (`python -m src.loaders.cost_baselines`); the backend only
    reads it, for the preparedness score and the plan (NF-FC-011, NF-FC-012).
    """

    collection_name = "cost_baselines"

    def get_baseline(self, host: str) -> dict[str, Any] | None:
        """The country's document, or None if the loader has not run for it."""
        return self.get(host)


@lru_cache
def get_cost_baseline_repository() -> CostBaselineRepository:
    return CostBaselineRepository(get_firestore_client())
