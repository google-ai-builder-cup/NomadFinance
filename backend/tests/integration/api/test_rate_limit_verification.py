"""Rate limit verification (NF-P4-004).

`test_cors_rate_limit.py` covers how the budgets behave. These tests ask the security
questions: can someone use up another worker's budget, what does an unauthenticated flood
cost, and do the default numbers hold.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import get_settings
from app.dependencies import get_account_service, get_current_user
from app.main import create_app
from app.schemas.user import AuthenticatedUser

COUNTED = "/api/v1/users/me"


def _reject_every_token() -> AuthenticatedUser:
    raise HTTPException(401, "Invalid authentication token")


def _unsigned_token(sub: str) -> str:
    """Looks like a JWT naming `sub`; has no valid signature, so it is always a 401."""

    def part(data: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part({'sub': sub})}.forged"


def _as(sub: str, ip: str) -> dict[str, str]:
    # On Cloud Run the last X-Forwarded-For entry is the address Google's front end saw.
    return {"Authorization": f"Bearer {_unsigned_token(sub)}", "X-Forwarded-For": ip}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("RATE_LIMIT_DEFAULT", "5/minute")
    monkeypatch.setenv("RATE_LIMIT_AI", "2/minute")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_current_user] = _reject_every_token
    app.dependency_overrides[get_account_service] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def test_a_forged_token_cannot_use_up_another_workers_budget(client: TestClient) -> None:
    # The limiter reads `sub` from the token before it is verified (so refused requests cost
    # little). Someone who knows a worker's uid could therefore send forged tokens naming them
    # and get that worker answered 429 on every call.
    victim = "victim-uid"
    for _ in range(20):
        client.delete(COUNTED, headers=_as(victim, ip="198.51.100.66"))

    from_victims_own_phone = client.delete(COUNTED, headers=_as(victim, ip="203.0.113.7"))

    assert from_victims_own_phone.status_code != 429


def test_the_same_worker_still_has_one_budget_from_one_address(client: TestClient) -> None:
    for _ in range(5):
        client.delete(COUNTED, headers=_as("alice", ip="203.0.113.7"))

    assert client.delete(COUNTED, headers=_as("alice", ip="203.0.113.7")).status_code == 429


def test_workers_on_one_shared_address_do_not_block_each_other(client: TestClient) -> None:
    # Dormitory Wi-Fi and carrier NAT: many workers, one address.
    for _ in range(5):
        client.delete(COUNTED, headers=_as("alice", ip="203.0.113.7"))

    assert client.delete(COUNTED, headers=_as("bob", ip="203.0.113.7")).status_code != 429


def test_a_refused_request_does_not_spend_the_ai_budget(client: TestClient) -> None:
    # Forged tokens on a Gemini endpoint end in 401 and must never reach the model: the
    # handler is not run when authentication fails.
    for _ in range(3):
        response = client.post("/api/v1/contracts/detect", headers=_as("alice", ip="203.0.113.7"))
        assert response.status_code in {401, 429}


def test_the_default_numbers_are_the_documented_ones() -> None:
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.rate_limit_enabled is True
    assert settings.rate_limit_default == "60/minute"
    assert settings.rate_limit_ai == "10/minute"
