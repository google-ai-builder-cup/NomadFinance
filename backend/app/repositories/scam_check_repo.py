from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from google.cloud.firestore import (
    Client,
    CollectionReference,
    DocumentReference,
    Increment,
    Query,
)

from app.repositories.base import get_firestore_client


class ScamCheckRepository:
    """users/{uid}/scam_checks/{checkId}: one analysed message per worker (scam.md).

    The id is derived from the message's cache key, so a check is found by a direct read and a
    retried request writes the same document again instead of a second one. Only the backend
    writes here; the owner reads through the API. A document past `expires_at` may still exist
    for up to a day after the TTL policy should have deleted it, so readers treat it as absent.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def _checks(self, uid: str) -> CollectionReference:
        checks: CollectionReference = (
            self._client.collection("users").document(uid).collection("scam_checks")
        )
        return checks

    def ref(self, uid: str, check_id: str) -> DocumentReference:
        """The document, for a caller that writes it in a transaction (the report, NF-SA-013)."""
        return self._checks(uid).document(check_id)

    def get(self, uid: str, check_id: str) -> dict[str, Any] | None:
        snapshot = self.ref(uid, check_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def save(self, uid: str, check_id: str, data: dict[str, Any]) -> None:
        """Write the whole check, replacing any earlier one under this id."""
        self.ref(uid, check_id).set(data)

    def touch(
        self, uid: str, check_id: str, *, last_checked_at: datetime, expires_at: datetime
    ) -> None:
        """Count one more check of the same message and move its expiry (`check_count`, TTL)."""
        self.ref(uid, check_id).update(
            {
                "check_count": Increment(1),
                "last_checked_at": last_checked_at,
                "expires_at": expires_at,
            }
        )

    def list_newest(
        self, uid: str, limit: int, *, before: datetime | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        """Up to `limit` checks, newest `created_at` first, older than `before` when it is given."""
        query = self._checks(uid).order_by("created_at", direction=Query.DESCENDING)
        if before is not None:
            query = query.start_after({"created_at": before})
        return [(doc.id, doc.to_dict() or {}) for doc in query.limit(limit).stream()]

    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        """Checks last made on or after `since`, newest first, as `(id, fields)`.

        Only what the Financial Identity signal and the activity feed need (NF-HR-001): the
        dates and the verdict's flag, level and type, never the message, its indicators or the
        explainer. One range on one field, so it needs no composite index.
        """
        query = (
            self._checks(uid)
            .where("last_checked_at", ">=", since)
            .order_by("last_checked_at", direction=Query.DESCENDING)
            .select(
                [
                    "created_at",
                    "last_checked_at",
                    "verdict.is_scam",
                    "verdict.risk_level",
                    "verdict.scam_type",
                ]
            )
            .limit(limit)
        )
        return [(doc.id, doc.to_dict() or {}) for doc in query.stream()]


@lru_cache
def get_scam_check_repository() -> ScamCheckRepository:
    return ScamCheckRepository(get_firestore_client())
