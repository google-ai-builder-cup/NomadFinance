from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_feature_flag_service, require_flag
from app.main import create_app
from app.schemas.errors import ErrorEnvelope
from app.schemas.user import AuthenticatedUser
from app.services.feature_flag_service import FeatureFlagService

DOCUMENT: dict[str, Any] = {
    "flags": {
        "coach": {"enabled": False, "allow_uids": ["tester"]},
        "scam": {"enabled": True, "allow_uids": []},
    }
}


class _FakeRepo:
    def get_feature_flags(self) -> dict[str, Any] | None:
        return DOCUMENT


def _app(uid: str | None) -> FastAPI:
    app = create_app()
    service = FeatureFlagService(_FakeRepo())  # type: ignore[arg-type]
    app.dependency_overrides[get_feature_flag_service] = lambda: service
    if uid is not None:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)

    # Throwaway guarded routes: the coach and scam routes do not exist yet. One under each
    # version, to show the guard follows the path's error format.
    for version in ("v1", "v2"):
        for flag in ("coach", "scam"):

            @app.get(f"/api/{version}/_probe/{flag}", dependencies=[Depends(require_flag(flag))])  # type: ignore[arg-type]
            async def guarded() -> dict[str, str]:
                return {"ok": "yes"}

    return app


def _client(uid: str | None) -> Iterator[TestClient]:
    with TestClient(_app(uid)) as client:
        yield client


@pytest.fixture
def worker() -> Iterator[TestClient]:
    yield from _client("someone")


@pytest.fixture
def tester() -> Iterator[TestClient]:
    yield from _client("tester")


@pytest.fixture
def signed_out() -> Iterator[TestClient]:
    yield from _client(None)


def test_flags_endpoint_reports_the_callers_own_flags(
    worker: TestClient, tester: TestClient
) -> None:
    assert worker.get("/api/v2/flags").json() == {"coach": False, "scam": True}
    assert tester.get("/api/v2/flags").json() == {"coach": True, "scam": True}


def test_flags_endpoint_never_lists_allow_listed_uids(tester: TestClient) -> None:
    response = tester.get("/api/v2/flags")

    assert set(response.json()) == {"coach", "scam"}
    assert "tester" not in response.text


def test_flags_endpoint_needs_a_token(signed_out: TestClient) -> None:
    assert signed_out.get("/api/v2/flags").status_code == 401


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_a_flag_that_is_on_lets_the_request_through(worker: TestClient, version: str) -> None:
    assert worker.get(f"/api/{version}/_probe/scam").json() == {"ok": "yes"}


def test_an_allow_listed_user_gets_in_while_the_flag_is_off_for_others(
    worker: TestClient, tester: TestClient
) -> None:
    assert tester.get("/api/v2/_probe/coach").status_code == 200
    assert worker.get("/api/v2/_probe/coach").status_code == 404


def test_a_flag_that_is_off_answers_in_the_v2_envelope_like_an_unknown_path(
    worker: TestClient,
) -> None:
    off = worker.get("/api/v2/_probe/coach")
    unknown = worker.get("/api/v2/no-such-route")

    assert off.status_code == unknown.status_code == 404
    envelope = ErrorEnvelope.model_validate(off.json())
    assert (envelope.code, envelope.message) == ("not_found", "Not Found")
    assert envelope.request_id == off.headers["X-Request-ID"]
    # The same code and message as a path that does not exist, so a disabled module cannot
    # be told from a missing one.
    assert off.json()["code"] == unknown.json()["code"]
    assert off.json()["message"] == unknown.json()["message"]


def test_a_flag_that_is_off_on_a_v1_path_keeps_the_v1_body(worker: TestClient) -> None:
    response = worker.get("/api/v1/_probe/coach")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_a_guarded_route_is_a_401_without_a_token_before_any_flag_check(
    signed_out: TestClient,
) -> None:
    assert signed_out.get("/api/v2/_probe/scam").status_code == 401
    assert signed_out.get("/api/v2/_probe/coach").status_code == 401
