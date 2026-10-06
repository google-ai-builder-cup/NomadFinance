from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client

from app.repositories.base import get_firestore_client


class ConfigRepository:
    """config/feature_flags: operator settings the backend reads at run time.

    See docs/data-model/collections/config.md. An operator writes this document in the
    Firebase console; nothing in the API changes it, so this repository only reads.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def get_feature_flags(self) -> dict[str, Any] | None:
        snapshot = self._client.collection("config").document("feature_flags").get()
        return snapshot.to_dict() if snapshot.exists else None


@lru_cache
def get_config_repository() -> ConfigRepository:
    return ConfigRepository(get_firestore_client())
