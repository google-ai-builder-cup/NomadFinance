from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from google.api_core.exceptions import NotFound
from google.cloud.firestore import SERVER_TIMESTAMP, Client, CollectionReference, DocumentReference

from app.repositories.base import get_firestore_client

SCHEMA_VERSION = 1
# Written into the profile by other features, so a recompute keeps them.
CARRIED_FIELDS = ("latest_export", "goals")

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

    def delete_entry(self, uid: str, kind: EntryKind, entry_id: str) -> None:
        self._entry(uid, kind, entry_id).delete()

    def update_entry(
        self, uid: str, kind: EntryKind, entry_id: str, fields: dict[str, Any]
    ) -> None:
        """Merge `fields` into an existing entry; raises NotFound if it is gone."""
        self._entry(uid, kind, entry_id).update(fields | {"updated_at": SERVER_TIMESTAMP})

    def save_profile(self, uid: str, profile: dict[str, Any]) -> None:
        """Overwrite `users/{uid}/financial_profile/current`: one document per user, never
        appended to (fib.md).

        `latest_export` (the PDF export, NF-P3-014) and `goals` (the Coach plan, NF-FC-015) are
        not the recompute's to change, since other features write them into this same document,
        so they are carried over instead of being wiped.
        """
        current = self.get_profile(uid) or {}
        carried = {key: current[key] for key in CARRIED_FIELDS if key in current}
        self._profile(uid).set(profile | carried | {"schema_version": SCHEMA_VERSION})

    def set_goals(self, uid: str, goals: dict[str, Any]) -> bool:
        """Record the Coach plan's goals on the profile; False if there is no profile yet (the
        next recompute then takes them from the newest plan)."""
        try:
            self._profile(uid).update({"goals": goals})
        except NotFound:
            return False
        return True

    def set_latest_export(self, uid: str, export: dict[str, Any]) -> None:
        """Record the newest PDF on the profile; raises NotFound if there is no profile."""
        self._profile(uid).update({"latest_export": export})

    def get_profile(self, uid: str) -> dict[str, Any] | None:
        snapshot = self._profile(uid).get()
        return snapshot.to_dict() if snapshot.exists else None

    def _profile(self, uid: str) -> DocumentReference:
        document: DocumentReference = (
            self._client.collection("users")
            .document(uid)
            .collection("financial_profile")
            .document("current")
        )
        return document


@lru_cache
def get_fib_repository() -> FibRepository:
    return FibRepository(get_firestore_client())
