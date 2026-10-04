from __future__ import annotations

from functools import lru_cache
from typing import Any

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import app_check as firebase_app_check
from firebase_admin import auth as firebase_auth
from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from jwt import PyJWKClientError

from app.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a Firebase Auth ID token or a Google service token fails verification."""


class TokenVerificationUnavailableError(Exception):
    """Google's signing keys couldn't be fetched, so no token can be checked right now."""


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
    except firebase_auth.UserNotFoundError as exc:
        # An account deleted in the last hour: its token is still valid until it expires.
        raise InvalidTokenError("User account no longer exists") from exc
    except firebase_auth.CertificateFetchError as exc:
        raise InvalidTokenError("Could not verify token signature") from exc
    except (firebase_auth.InvalidIdTokenError, ValueError) as exc:
        raise InvalidTokenError("Invalid authentication token") from exc


def verify_app_check_token(token: str) -> dict[str, Any]:
    """Verify a Firebase App Check token and return its decoded claims (NF-P3-025).

    Every rejection the library raises for a bad token (expired, wrong signature, wrong
    project, malformed headers — see `firebase_admin.app_check`'s own source) surfaces as a
    plain `ValueError`, so there is nothing more specific to catch than that.

    Raises:
        InvalidTokenError: The token is missing, malformed, expired, or for another project.
        TokenVerificationUnavailableError: App Check's signing keys couldn't be fetched.
    """
    try:
        return firebase_app_check.verify_token(  # type: ignore[no-any-return]
            token, app=get_firebase_app()
        )
    except PyJWKClientError as exc:
        raise TokenVerificationUnavailableError(
            "Could not verify App Check token signature"
        ) from exc
    except ValueError as exc:
        raise InvalidTokenError("Invalid App Check token") from exc


def verify_google_oidc_token(token: str, audience: str) -> dict[str, Any]:
    """Verify a Google-signed OIDC token, such as Cloud Scheduler's, and return its claims.

    Blocking: fetches Google's public keys over HTTP, so call it from a thread pool.

    Raises:
        InvalidTokenError: Bad signature, wrong audience or issuer, or expired.
        TokenVerificationUnavailableError: Google's keys couldn't be downloaded.
    """
    try:
        return google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call,no-any-return]
            token, google_requests.Request(), audience
        )
    except google_auth_exceptions.TransportError as exc:
        raise TokenVerificationUnavailableError("Could not fetch Google signing keys") from exc
    except (google_auth_exceptions.GoogleAuthError, ValueError) as exc:
        # GoogleAuthError is what a wrong issuer raises; TransportError (a subclass) is above.
        raise InvalidTokenError("Invalid service token") from exc
