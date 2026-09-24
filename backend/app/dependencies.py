from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import InvalidTokenError, verify_id_token
from app.schemas.user import AuthenticatedUser

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

    return AuthenticatedUser(
        uid=claims["uid"],
        email=claims.get("email"),
        email_verified=claims.get("email_verified", False),
        phone_number=claims.get("phone_number"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )
