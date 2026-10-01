from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import Settings
from app.core.security import InvalidTokenError, TokenVerificationUnavailableError
from app.dependencies import get_current_user, verify_app_check

pytestmark = pytest.mark.anyio


def _settings(**over: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "local",
        "gemini_api_key": "k",
        "radar_reporter_hash_secret": "s",
        "_env_file": None,
    }
    return Settings(**(values | over))  # type: ignore[arg-type]


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


# --- verify_app_check (NF-P3-025) ---------------------------------------------------------


async def test_verify_app_check_passes_through_when_disabled() -> None:
    # No token, and the verifier is never even called: disabled means disabled.
    with patch("app.dependencies.verify_app_check_token") as verify:
        await verify_app_check(None, _settings(app_check_enabled=False))

    verify.assert_not_called()


async def test_verify_app_check_rejects_a_missing_token_when_enabled() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await verify_app_check(None, _settings(app_check_enabled=True))

    assert exc_info.value.status_code == 403


async def test_verify_app_check_accepts_a_valid_token_when_enabled() -> None:
    with patch("app.dependencies.verify_app_check_token", return_value={"app_id": "a1"}):
        # No exception: that is the whole contract for a passing call.
        await verify_app_check("a-valid-token", _settings(app_check_enabled=True))


async def test_verify_app_check_rejects_an_invalid_token() -> None:
    with patch(
        "app.dependencies.verify_app_check_token", side_effect=InvalidTokenError("bad token")
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_app_check("a-bad-token", _settings(app_check_enabled=True))

    assert exc_info.value.status_code == 403


async def test_verify_app_check_returns_503_when_verification_is_unavailable() -> None:
    with patch(
        "app.dependencies.verify_app_check_token",
        side_effect=TokenVerificationUnavailableError("keys unreachable"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await verify_app_check("a-token", _settings(app_check_enabled=True))

    assert exc_info.value.status_code == 503
