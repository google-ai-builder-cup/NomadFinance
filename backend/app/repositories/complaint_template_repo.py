from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.repositories.base import FirestoreRepository, get_firestore_client


class ComplaintTemplateRepository(FirestoreRepository):
    """complaint_templates/{country} and .../types/{type} (contracts.md).

    Read-only from the backend: only the data-scripts loader (NF-P2-006) writes here.
    """

    collection_name = "complaint_templates"

    def get_template(self, country: str, template_type: str) -> dict[str, Any] | None:
        """One letter frame of a country, or None if it was never loaded."""
        snapshot = self.document(country).collection("types").document(template_type).get()
        return snapshot.to_dict() if snapshot.exists else None


@lru_cache
def get_complaint_template_repository() -> ComplaintTemplateRepository:
    return ComplaintTemplateRepository(get_firestore_client())
