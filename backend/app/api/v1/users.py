from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.dependencies import get_account_service, get_current_user
from app.schemas.user import AuthenticatedUser
from app.services.auth_service import AccountDeletionError, AccountService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])

# The frontend picks its "sign in again" screen by this exact string.
RECENT_LOGIN_REQUIRED = "recent_login_required"

_DELETE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    403: {"description": "The caller did not sign in recently (`detail`: `recent_login_required`)"},
    503: {"description": "A backing service failed part-way; call again to finish"},
}


def _signed_in_recently(auth_time: int | None, max_age_seconds: int) -> bool:
    if auth_time is None:
        return False
    age = time.time() - auth_time
    # A little negative age is clock skew between Google's servers and ours, not a problem.
    return -60 <= age <= max_age_seconds


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_DELETE_RESPONSES,
    summary="Delete my account and all my data",
)
async def delete_my_account(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[AccountService, Depends(get_account_service)],
) -> Response:
    """Delete the caller's profile and everything under it, their files, and their sign-in.

    The account is always the token's own: there is no way to name another user. The token
    must come from a sign-in in the last few minutes, because this cannot be undone.
    """
    if not _signed_in_recently(user.auth_time, settings.account_deletion_max_login_age_seconds):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RECENT_LOGIN_REQUIRED)
    try:
        await run_in_threadpool(service.delete_account, user.uid)
    except AccountDeletionError as exc:
        logger.error("account_deletion_failed cause=%s", type(exc.__cause__).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We couldn't finish deleting the account. Please try again.",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
