from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.cloud.firestore import Client

from app.repositories.base import get_firestore_client


class ScamIndicatorRepository:
    """scam_indicators/{id}: how often workers reported a number, address or account (scam.md).

    Read-only here. The report route (NF-SA-013) writes these in the transaction of the report,
    so until it exists no document does and every lookup is empty.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def get_many(self, doc_ids: list[str]) -> dict[str, dict[str, Any]]:
        """The documents that exist, by id, in one round trip."""
        if not doc_ids:
            return {}
        refs = [self._client.collection("scam_indicators").document(i) for i in doc_ids]
        return {
            snapshot.id: snapshot.to_dict() or {}
            for snapshot in self._client.get_all(refs)
            if snapshot.exists
        }


@lru_cache
def get_scam_indicator_repository() -> ScamIndicatorRepository:
    return ScamIndicatorRepository(get_firestore_client())
