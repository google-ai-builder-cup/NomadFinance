from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.core.logging import bind_user
from app.core.security import (
    InvalidTokenError,
    TokenVerificationUnavailableError,
    verify_app_check_token,
    verify_google_oidc_token,
    verify_id_token,
)
from app.integrations.cloud_storage import UserFileStore
from app.integrations.firebase_auth import delete_firebase_user
from app.repositories.base import get_firestore_client
from app.schemas.user import AuthenticatedUser
from app.services.auth_service import AccountService

# auto_error=False so a missing token becomes our own 401 instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    # FastAPI's own Depends()-in-default pattern; ruff's bugbear check doesn't know it.
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
) -> AuthenticatedUser:
    """Verify the request's Firebase Auth bearer token and return the caller's identity.

    Add `Depends(get_current_user)` to any endpoint that isn't public; endpoints
    that skip it must say so per the Backend Endpoint Definition of Done.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_id_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    bind_user(claims["uid"])
    return AuthenticatedUser(
        uid=claims["uid"],
        email=claims.get("email"),
        email_verified=claims.get("email_verified", False),
        phone_number=claims.get("phone_number"),
        name=claims.get("name"),
        picture=claims.get("picture"),
        auth_time=claims.get("auth_time"),
    )


async def verify_app_check(
    token: Annotated[str | None, Header(alias="X-Firebase-AppCheck")] = None,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    """Reject a call that isn't from a verified instance of the app (NF-P3-025).

    Add `Depends(verify_app_check)` to an endpoint worth protecting from scripted abuse,
    distinct from `get_current_user`: App Check attests to the calling app, not the signed-in
    person. Off by default (`Settings.app_check_enabled`) until a real reCAPTCHA v3 site key
    is wired through the frontend for a deployed domain — enforcing before then would reject
    every real submission, not just bots (see the NF-P3-025 runbook, "Before this works in
    production").
    """
    if not settings.app_check_enabled:
        return
    if token is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing App Check token")
    try:
        await run_in_threadpool(verify_app_check_token, token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except TokenVerificationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


async def require_cloud_scheduler(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> str:
    """Allow only Cloud Scheduler's signed calls to /api/v1/internal/* and return its email.

    The Cloud Run service is public (user endpoints check Firebase tokens themselves),
    so this check is the only gate in front of the internal endpoints.
    """
    if not (settings.cron_service_account and settings.cron_audience):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoints are not configured",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = await run_in_threadpool(
            verify_google_oidc_token, credentials.credentials, settings.cron_audience
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except TokenVerificationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if (
        claims.get("email") != settings.cron_service_account
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caller is not allowed")
    return settings.cron_service_account


@lru_cache
def get_account_service() -> AccountService:
    """The account-deletion service wired to real Firestore, Storage and Firebase Auth."""
    return AccountService(get_firestore_client(), UserFileStore(), delete_firebase_user)
