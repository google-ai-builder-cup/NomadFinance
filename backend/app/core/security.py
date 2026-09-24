from __future__ import annotations

from functools import lru_cache
from typing import Any

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth as firebase_auth

from app.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a Firebase Auth ID token fails verification."""


@lru_cache
def get_firebase_app() -> firebase_admin.App:
    """Return the process-wide Firebase Admin app, initializing it on first use.

    No explicit credentials are passed: Cloud Run's attached service account
    supplies Application Default Credentials in prod, and local dev runs against
    the Firebase Emulator Suite via FIRESTORE_EMULATOR_HOST / FIREBASE_AUTH_EMULATOR_HOST.
    """
    settings = get_settings()
    return firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})


def verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Firebase Auth ID token and return its decoded claims.

    Wraps every Firebase-side failure (expired, revoked, malformed, wrong
    project, ...) into a single `InvalidTokenError` so callers don't need to
    know about firebase_admin's internal exception hierarchy.
    """
    # Ordered most-specific first: ExpiredIdTokenError and RevokedIdTokenError are
    # both subclasses of InvalidIdTokenError, so that catch-all must come last.
    try:
        return firebase_auth.verify_id_token(  # type: ignore[no-any-return]
            id_token, app=get_firebase_app(), check_revoked=True
        )
    except firebase_auth.ExpiredIdTokenError as exc:
        raise InvalidTokenError("Authentication token has expired") from exc
    except firebase_auth.RevokedIdTokenError as exc:
        raise InvalidTokenError("Authentication token has been revoked") from exc
    except firebase_auth.UserDisabledError as exc:
        raise InvalidTokenError("User account is disabled") from exc
    except firebase_auth.CertificateFetchError as exc:
        raise InvalidTokenError("Could not verify token signature") from exc
    except (firebase_auth.InvalidIdTokenError, ValueError) as exc:
        raise InvalidTokenError("Invalid authentication token") from exc
