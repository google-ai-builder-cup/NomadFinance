from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from google.cloud.firestore import SERVER_TIMESTAMP, Client, CollectionReference, DocumentReference

from app.repositories.base import get_firestore_client

SCHEMA_VERSION = 1

# The four activity types the Financial Identity Builder logs (docs/data-model/collections/fib.md).
# NF-P2-017 is the first writer, for `transfers` only; NF-P3-010 adds the rest.
EntryKind = Literal["transfers", "income", "bills", "savings"]


class FibRepository:
    """users/{uid}/{transfers,income,bills,savings}/{id}: the Financial Identity activity log.

    See docs/data-model/collections/fib.md. Every entry type shares `entry_date`, `notes`,
    `source`, timestamps and `schema_version`; only the backend writes here.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def _entries(self, uid: str, kind: EntryKind) -> CollectionReference:
        entries: CollectionReference = (
            self._client.collection("users").document(uid).collection(kind)
        )
        return entries

    def _entry(self, uid: str, kind: EntryKind, entry_id: str) -> DocumentReference:
        return self._entries(uid, kind).document(entry_id)

    def new_id(self, uid: str, kind: EntryKind) -> str:
        return str(self._entries(uid, kind).document().id)

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        """Write one activity entry, replacing anything already stored at that id."""
        self._entry(uid, kind, entry_id).set(
            data
            | {
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
                "schema_version": SCHEMA_VERSION,
            }
        )

    def get_entry(self, uid: str, kind: EntryKind, entry_id: str) -> dict[str, Any] | None:
        snapshot = self._entry(uid, kind, entry_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        """Every entry of one kind as `(id, data)`. A user's log is a few dozen entries."""
        return [(doc.id, doc.to_dict() or {}) for doc in self._entries(uid, kind).stream()]

    def update_entry(
        self, uid: str, kind: EntryKind, entry_id: str, fields: dict[str, Any]
    ) -> None:
        """Merge `fields` into an existing entry; raises NotFound if it is gone."""
        self._entry(uid, kind, entry_id).update(fields | {"updated_at": SERVER_TIMESTAMP})


@lru_cache
def get_fib_repository() -> FibRepository:
    return FibRepository(get_firestore_client())
