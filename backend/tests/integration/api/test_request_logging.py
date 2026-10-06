from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app import dependencies
from app.dependencies import get_current_user
from app.main import create_app
from app.schemas.user import AuthenticatedUser
from app.utils.hashing import hash_user_id

SECRET_UID = "secret-uid-from-token"


def _app() -> FastAPI:
    app = create_app()

    @app.get("/probe/whoami")
    async def whoami(
        user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
    ) -> dict[str, str]:
        logging.getLogger("test.probe").info("inside the handler")
        return {"ok": "yes"}

    @app.get("/probe/boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def _completed(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    records = [r for r in caplog.records if r.getMessage().startswith("request_completed")]
    assert len(records) == 1
    return records[0]


def _field(record: logging.LogRecord, name: str) -> Any:
    """A field added through `extra=` or by the record factory; not known to the type checker."""
    return getattr(record, name)


def test_every_response_carries_a_generated_request_id(client: TestClient) -> None:
    first = client.get("/health").headers["X-Request-ID"]
    second = client.get("/health").headers["X-Request-ID"]

    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second


def test_a_well_formed_caller_id_is_reused_and_a_bad_one_replaced(client: TestClient) -> None:
    ok = client.get("/health", headers={"X-Request-ID": "trace-abc-12345"})
    bad = client.get("/health", headers={"X-Request-ID": "x\ninjected line"})

    assert ok.headers["X-Request-ID"] == "trace-abc-12345"
    assert re.fullmatch(r"[0-9a-f]{32}", bad.headers["X-Request-ID"])


def test_completion_line_has_status_latency_and_id(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = client.get("/api/v1/nope")

    record = _completed(caplog)
    assert record.levelno == logging.INFO
    assert [_field(record, n) for n in ("method", "path", "status")] == ["GET", "/api/v1/nope", 404]
    assert isinstance(_field(record, "latency_ms"), float) and _field(record, "latency_ms") >= 0
    assert _field(record, "request_id") == response.headers["X-Request-ID"]
    assert _field(record, "uid_hash") is None


def test_query_string_and_credentials_are_never_logged(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    client.get("/api/v1/nope?token=query-secret", headers={"Authorization": "Bearer header-secret"})

    # The test client itself logs its URL through httpx; that must be silenced too.
    assert "query-secret" not in caplog.text
    assert "header-secret" not in caplog.text


def test_health_probes_are_logged_at_debug_only(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    client.get("/health")
    assert not caplog.records

    caplog.set_level(logging.DEBUG)
    client.get("/health")
    assert _completed(caplog).levelno == logging.DEBUG


def test_signed_in_requests_carry_the_hashed_user_on_every_line(
    client: TestClient, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_verify(_token: str) -> dict[str, Any]:
        return {"uid": SECRET_UID}

    monkeypatch.setattr(dependencies, "verify_id_token", fake_verify)
    caplog.set_level(logging.INFO)

    response = client.get("/probe/whoami", headers={"Authorization": "Bearer t"})

    inside = next(r for r in caplog.records if r.getMessage() == "inside the handler")
    done = _completed(caplog)
    expected = hash_user_id(SECRET_UID)
    assert _field(inside, "uid_hash") == _field(done, "uid_hash") == expected
    request_id = response.headers["X-Request-ID"]
    assert _field(inside, "request_id") == _field(done, "request_id") == request_id
    assert SECRET_UID not in caplog.text


def test_an_unhandled_error_logs_the_traceback_but_not_to_the_client(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = client.get("/probe/boom")

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    record = _completed(caplog)
    assert record.levelno == logging.ERROR
    assert _field(record, "status") == 500
    assert record.exc_info is not None
    assert "secret internal detail" in caplog.text


def test_context_does_not_leak_into_the_next_request(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    client.get("/api/v1/nope")
    caplog.clear()

    logging.getLogger("test.after").info("outside any request")

    assert _field(caplog.records[0], "request_id") is None


@pytest.mark.parametrize(
    ("path", "feature"),
    [
        ("/api/v1/remittance/trends", "remittance"),
        ("/api/v1/contracts/extract", "contract"),
        ("/api/v1/radar/entities/x/reports", "radar"),
        ("/api/v1/fib/report/export", "fib"),
        ("/health", "platform"),
    ],
)
def test_every_request_line_names_its_feature(
    client: TestClient, caplog: pytest.LogCaptureFixture, path: str, feature: str
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
        client.get(path)

    assert _field(_completed(caplog), "feature") == feature


@pytest.mark.parametrize(
    ("path", "status_class"), [("/health", "2xx"), ("/api/v1/nope", "4xx")], ids=["ok", "missing"]
)
def test_every_request_line_has_its_status_class(
    client: TestClient, caplog: pytest.LogCaptureFixture, path: str, status_class: str
) -> None:
    with caplog.at_level(logging.DEBUG, logger="app.core.middleware"):
        client.get(path)

    record = _completed(caplog)
    assert _field(record, "status_class") == status_class
    assert "status_class" not in record.getMessage()
