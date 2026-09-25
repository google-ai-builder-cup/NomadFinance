"""Firebase Authentication user management through the Admin SDK."""

from __future__ import annotations

from firebase_admin import auth as firebase_auth  # type: ignore[import-untyped]

from app.core.security import get_firebase_app


def delete_firebase_user(uid: str) -> bool:
    """Delete the sign-in account; return False when it was already gone."""
    try:
        firebase_auth.delete_user(uid, app=get_firebase_app())
    except firebase_auth.UserNotFoundError:
        return False
    return True
