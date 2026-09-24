from __future__ import annotations

from unittest.mock import patch

import pytest
from firebase_admin import auth as firebase_auth  # type: ignore[import-untyped]

from app.core.security import InvalidTokenError, verify_id_token


def test_verify_id_token_returns_claims_for_valid_token() -> None:
    claims = {"uid": "user-123", "email": "worker@example.com"}
    with patch("app.core.security.firebase_auth.verify_id_token", return_value=claims) as mocked:
        result = verify_id_token("a-valid-token")

    assert result == claims
    mocked.assert_called_once()
    assert mocked.call_args.kwargs["check_revoked"] is True


@pytest.mark.parametrize(
    "raised",
    [
        firebase_auth.InvalidIdTokenError("bad token"),
        firebase_auth.ExpiredIdTokenError("expired", cause=None),
        firebase_auth.RevokedIdTokenError("revoked"),
        firebase_auth.UserDisabledError("disabled"),
        firebase_auth.CertificateFetchError("cert fetch failed", cause=None),
        ValueError("malformed"),
    ],
)
def test_verify_id_token_wraps_firebase_failures(raised: Exception) -> None:
    with patch("app.core.security.firebase_auth.verify_id_token", side_effect=raised):
        with pytest.raises(InvalidTokenError):
            verify_id_token("some-token")
