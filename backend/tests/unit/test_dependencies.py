from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.security import InvalidTokenError
from app.dependencies import get_current_user

pytestmark = pytest.mark.anyio


async def test_get_current_user_returns_user_for_valid_token() -> None:
    claims = {
        "uid": "user-123",
        "email": "worker@example.com",
        "email_verified": True,
        "phone_number": "+6591234567",
        "name": "Priya",
        "picture": None,
    }
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="a-valid-token")

    with patch("app.dependencies.verify_id_token", return_value=claims):
        user = await get_current_user(credentials)

    assert user.uid == "user-123"
    assert user.email == "worker@example.com"
    assert user.email_verified is True


async def test_get_current_user_rejects_missing_credentials() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(None)

    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_invalid_token() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="a-bad-token")

    with patch("app.dependencies.verify_id_token", side_effect=InvalidTokenError("bad")):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

    assert exc_info.value.status_code == 401
