from __future__ import annotations

from functools import lru_cache
from typing import Any

from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client, CollectionReference, DocumentReference

from app.core.security import get_firebase_app


@lru_cache
def get_firestore_client() -> Client:
    """Return the process-wide Firestore client.

    Respects FIRESTORE_EMULATOR_HOST when set, so local dev and tests hit the
    Firebase Emulator instead of live Firestore.
    """
    return firestore.client(app=get_firebase_app())  # type: ignore[no-any-return]


class FirestoreRepository:
    """Base class for Firestore-backed repositories.

    Subclasses set `collection_name` and build pillar-specific methods on top
    of these thin, typed wrappers over the raw Firestore SDK.
    """

    collection_name: str

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    @property
    def collection(self) -> CollectionReference:
        return self._client.collection(self.collection_name)

    def document(self, doc_id: str) -> DocumentReference:
        return self.collection.document(doc_id)

    def get(self, doc_id: str) -> dict[str, Any] | None:
        snapshot = self.document(doc_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def set(self, doc_id: str, data: dict[str, Any], *, merge: bool = False) -> None:
        self.document(doc_id).set(data, merge=merge)

    def delete(self, doc_id: str) -> None:
        self.document(doc_id).delete()
