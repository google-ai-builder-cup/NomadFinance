from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.cloud.firestore import ArrayRemove, FieldFilter

from app.repositories.base import FirestoreRepository, get_firestore_client


class UserRepository(FirestoreRepository):
    """users/{uid}: the profile the worker filled in during onboarding (users.md).

    Read-only from the backend for the profile itself: the app writes it, the backend only
    deletes it (AccountService). The one exception is `remove_fcm_token` (NF-P3-004): FCM
    reporting a token invalid is a fact about delivery, not an edit to the worker's own
    choices, and the alternative is a growing list of dead tokens on every future push.
    """

    collection_name = "users"

    def get_profile(self, uid: str) -> dict[str, Any]:
        """The profile, or an empty dict before onboarding has created it."""
        return self.get(uid) or {}

    def list_user_ids(self) -> list[str]:
        """Every user id, for the weekly Financial Identity recompute (NF-P3-013).

        `select([])` reads the document ids only, not the profiles.
        """
        return [doc.id for doc in self.collection.select([]).stream()]

    def by_host_and_home(self, host_country: str, home_country: str) -> list[tuple[str, Any]]:
        """Profiles for one (host, home) pair, for a corridor's default-subscribed cohort
        (`host_and_home`, `utils/corridors.py`). Equality-only, no composite index needed."""
        query = self.collection.where(filter=FieldFilter("host_country", "==", host_country)).where(
            filter=FieldFilter("home_country", "==", home_country)
        )
        return [(doc.id, doc.to_dict()) for doc in query.stream()]

    def subscribed_to_corridor(self, corridor_id: str) -> list[tuple[str, Any]]:
        """Profiles that explicitly chose this corridor in `notification_prefs.radar_corridors`."""
        query = self.collection.where(
            filter=FieldFilter("notification_prefs.radar_corridors", "array_contains", corridor_id)
        )
        return [(doc.id, doc.to_dict()) for doc in query.stream()]

    def remove_fcm_token(self, uid: str, token: str) -> None:
        """Drop one push token FCM reported as no longer valid (unregistered/invalid)."""
        self.document(uid).update({"fcm_tokens": ArrayRemove([token])})

    def create_notification(self, uid: str, notification: dict[str, Any]) -> None:
        """Write one `users/{uid}/notifications/{id}` document (users.md)."""
        self.document(uid).collection("notifications").document().set(notification)


@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository(get_firestore_client())
