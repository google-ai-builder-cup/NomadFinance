from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.repositories.base import FirestoreRepository, get_firestore_client


class UserRepository(FirestoreRepository):
    """users/{uid}: the profile the worker filled in during onboarding (users.md).

    Read-only from the backend here: the app writes the profile, the backend only deletes it
    (AccountService).
    """

    collection_name = "users"

    def get_profile(self, uid: str) -> dict[str, Any]:
        """The profile, or an empty dict before onboarding has created it."""
        return self.get(uid) or {}


@lru_cache
def get_user_repository() -> UserRepository:
    return UserRepository(get_firestore_client())
