from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_account_service, get_current_user
from app.main import create_app
from app.schemas.user import AuthenticatedUser
from app.services.auth_service import AccountDeletionError, DeletionResult

URL = "/api/v1/users/me"


class _FakeService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.deleted: list[str] = []

    def delete_account(self, uid: str) -> DeletionResult:
        if self.fail:
            raise AccountDeletionError("boom") from RuntimeError("backing service")
        self.deleted.append(uid)
        return DeletionResult(2, 1, True)


def _user(auth_time: int | None) -> AuthenticatedUser:
    return AuthenticatedUser(uid="uid-from-token", auth_time=auth_time)


@pytest.fixture
def service() -> _FakeService:
    return _FakeService()


def _client(service: _FakeService, user: AuthenticatedUser | None) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_account_service] = lambda: service
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client


@pytest.fixture
def signed_in_now(service: _FakeService) -> Iterator[TestClient]:
    yield from _client(service, _user(int(time.time()) - 30))


def test_it_needs_a_token(service: _FakeService) -> None:
    for client in _client(service, None):
        response = client.delete(URL)

    assert response.status_code == 401
    assert service.deleted == []


def test_it_deletes_the_callers_own_account_and_returns_204(
    signed_in_now: TestClient, service: _FakeService
) -> None:
    response = signed_in_now.delete(URL)

    assert response.status_code == 204
    assert response.content == b""
    assert service.deleted == ["uid-from-token"]


def test_there_is_no_way_to_name_another_user(
    signed_in_now: TestClient, service: _FakeService
) -> None:
    for path in ("/api/v1/users/someone-else", "/api/v1/users/someone-else/me"):
        assert signed_in_now.delete(path).status_code in (404, 405)

    assert service.deleted == []


@pytest.mark.parametrize("auth_time", [None, int(time.time()) - 3600, int(time.time()) - 301])
def test_an_old_sign_in_is_refused_and_nothing_is_deleted(
    service: _FakeService, auth_time: int | None
) -> None:
    for client in _client(service, _user(auth_time)):
        response = client.delete(URL)

    assert response.status_code == 403
    assert response.json() == {"detail": "recent_login_required"}
    assert service.deleted == []


def test_a_sign_in_a_few_seconds_in_the_future_is_clock_skew_not_an_error(
    service: _FakeService,
) -> None:
    for client in _client(service, _user(int(time.time()) + 20)):
        response = client.delete(URL)

    assert response.status_code == 204


def test_a_backing_service_failure_is_a_503_without_internals(service: _FakeService) -> None:
    service.fail = True
    for client in _client(service, _user(int(time.time()))):
        response = client.delete(URL)

    assert response.status_code == 503
    assert response.json() == {
        "detail": "We couldn't finish deleting the account. Please try again."
    }
    assert "backing service" not in response.text
    assert "Traceback" not in response.text
