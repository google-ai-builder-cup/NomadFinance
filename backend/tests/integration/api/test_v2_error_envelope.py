from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.errors import ApiError
from app.integrations.gemini import (
    GeminiBudgetExhaustedError,
    GeminiRateLimitError,
    GeminiRequestError,
    GeminiResponseError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.main import create_app
from app.schemas.errors import ErrorEnvelope

SECRET = "secret-value-from-the-client"


class _Body(BaseModel):
    amount: float = Field(gt=0)
    note: str


class _Many(BaseModel):
    values: list[int]


def _probe_app() -> object:
    """The real app plus throwaway routes that fail in each way, once under v2 and once v1."""
    app = create_app()

    for prefix in ("/api/v2/_probe", "/api/v1/_probe"):

        @app.post(f"{prefix}/body")
        async def body(payload: _Body) -> dict[str, str]:
            return {"ok": "yes"}

        @app.post(f"{prefix}/many")
        async def many(payload: _Many) -> None: ...

        @app.get(f"{prefix}/forbidden")
        async def forbidden() -> None:
            raise HTTPException(403, "Not yours", headers={"X-Extra": "kept"})

        @app.get(f"{prefix}/conflict")
        async def conflict() -> None:
            raise ApiError(409, "request_in_progress", "Still running.", {"Retry-After": "2"})

        @app.get(f"{prefix}/boom")
        async def boom() -> None:
            raise RuntimeError(SECRET)

        @app.get(f"{prefix}/gemini/{{kind}}")
        async def gemini(kind: str) -> None:
            raise {
                "busy": GeminiRateLimitError("quota " + SECRET),
                "daily": GeminiRateLimitError("daily " + SECRET, daily=True),
                "budget": GeminiBudgetExhaustedError(
                    "budget " + SECRET, source="budget", retry_after_seconds=4321
                ),
                "down": GeminiUnavailableError("503 " + SECRET),
                "slow": GeminiTimeoutError("timeout " + SECRET),
                "bad": GeminiResponseError("empty " + SECRET),
                "ours": GeminiRequestError("400 " + SECRET),
            }[kind]

    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(_probe_app(), raise_server_exceptions=False) as test_client:  # type: ignore[arg-type]
        yield test_client


def _envelope(response_json: dict[str, object], request_id_header: str) -> ErrorEnvelope:
    envelope = ErrorEnvelope.model_validate(response_json)
    assert envelope.request_id == request_id_header
    assert set(response_json) <= {"code", "message", "request_id", "details"}
    return envelope


def test_unknown_v2_path_is_a_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/v2/nothing-here")

    assert response.status_code == 404
    envelope = _envelope(response.json(), response.headers["x-request-id"])
    assert envelope.code == "not_found"
    assert envelope.details is None


def test_wrong_method_is_a_method_not_allowed_envelope(client: TestClient) -> None:
    response = client.get("/api/v2/_probe/body")

    assert response.status_code == 405
    assert _envelope(response.json(), response.headers["x-request-id"]).code == "method_not_allowed"


def test_http_exception_keeps_its_status_and_headers(client: TestClient) -> None:
    response = client.get("/api/v2/_probe/forbidden", headers={"X-Request-ID": "caller-id-12345"})

    assert response.status_code == 403
    assert response.headers["x-extra"] == "kept"
    envelope = _envelope(response.json(), "caller-id-12345")
    assert (envelope.code, envelope.message) == ("forbidden", "Not yours")


def test_api_error_carries_its_own_code(client: TestClient) -> None:
    response = client.get("/api/v2/_probe/conflict")

    assert response.status_code == 409
    assert response.headers["retry-after"] == "2"
    assert (
        _envelope(response.json(), response.headers["x-request-id"]).code == "request_in_progress"
    )


def test_validation_error_lists_fields_and_never_echoes_input(client: TestClient) -> None:
    response = client.post("/api/v2/_probe/body", json={"amount": -5, "note": 7, "x": SECRET})

    assert response.status_code == 422
    envelope = _envelope(response.json(), response.headers["x-request-id"])
    assert envelope.code == "validation_failed"
    assert envelope.details is not None
    assert {detail.field for detail in envelope.details} == {"body.amount", "body.note"}
    assert SECRET not in response.text
    assert "input" not in response.text


def test_nan_in_a_number_is_a_422_not_a_500(client: TestClient) -> None:
    # D-63: v1 echoes the rejected NaN, which cannot be written as JSON, and answers 500.
    response = client.post(
        "/api/v2/_probe/body",
        content=b'{"amount": NaN, "note": "x"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


def test_validation_details_are_capped(client: TestClient) -> None:
    response = client.post("/api/v2/_probe/many", json={"values": ["x"] * 40})

    assert response.status_code == 422
    assert len(response.json()["details"]) == 20


@pytest.mark.parametrize(
    ("kind", "status", "code", "retry_after"),
    [
        ("busy", 503, "ai_busy", "30"),
        ("down", 503, "ai_unavailable", "30"),
        ("slow", 504, "ai_timeout", None),
        ("bad", 502, "ai_bad_response", None),
        ("ours", 500, "internal_error", None),
    ],
)
def test_gemini_errors_map_to_ai_codes(
    client: TestClient, kind: str, status: int, code: str, retry_after: str | None
) -> None:
    response = client.get(f"/api/v2/_probe/gemini/{kind}")

    assert response.status_code == status
    assert response.headers.get("retry-after") == retry_after
    assert _envelope(response.json(), response.headers["x-request-id"]).code == code
    assert SECRET not in response.text


def test_uncaught_exception_is_an_internal_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v2/_probe/boom")

    assert response.status_code == 500
    envelope = _envelope(response.json(), response.headers["x-request-id"])
    assert envelope.code == "internal_error"
    assert SECRET not in response.text


# --- Errors built by middleware -------------------------------------------------------


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    def build(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        return TestClient(create_app(), raise_server_exceptions=False)

    yield build
    get_settings.cache_clear()


def test_rate_limit_answers_with_an_envelope_on_v2(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(RATE_LIMIT_DEFAULT="1/minute")
    client.get("/api/v2/anything")

    refused = client.get("/api/v2/anything")

    assert refused.status_code == 429
    assert int(refused.headers["retry-after"]) >= 1
    assert refused.headers["x-ratelimit-limit"] == "1"
    assert _envelope(refused.json(), refused.headers["x-request-id"]).code == "rate_limited"


def test_oversized_body_answers_with_an_envelope_on_v2(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(UPLOAD_MAX_BYTES="1000")

    response = client.post(
        "/api/v2/anything",
        content=b"x" * (1000 + 64 * 1024 + 1),
        headers={"Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 413
    assert _envelope(response.json(), response.headers["x-request-id"]).code == "payload_too_large"


# --- v1 does not change ---------------------------------------------------------------


def test_v1_errors_keep_their_old_shape(client: TestClient) -> None:
    unknown = client.get("/api/v1/nothing-here")
    forbidden = client.get("/api/v1/_probe/forbidden")
    invalid = client.post("/api/v1/_probe/body", json={"amount": -5, "note": "x"})
    gemini = client.get("/api/v1/_probe/gemini/busy")
    boom = client.get("/api/v1/_probe/boom")

    assert unknown.json() == {"detail": "Not Found"}
    assert forbidden.json() == {"detail": "Not yours"}
    assert forbidden.headers["x-extra"] == "kept"
    # FastAPI's own 422 body, which repeats the input.
    assert invalid.status_code == 422
    assert invalid.json()["detail"][0]["input"] == -5
    assert gemini.json() == {"detail": "The AI service is busy. Please try again in a minute."}
    assert boom.status_code == 500
    assert boom.text == "Internal Server Error"


def test_a_path_that_only_starts_like_v2_is_still_v1_behaviour(client: TestClient) -> None:
    assert client.get("/api/v20/x").json() == {"detail": "Not Found"}


@pytest.mark.parametrize("prefix", ["/api/v2/_probe", "/api/v1/_probe"])
def test_a_spent_daily_quota_says_try_later_with_the_time_it_comes_back(
    client: TestClient, prefix: str
) -> None:
    budget = client.get(f"{prefix}/gemini/budget")
    daily = client.get(f"{prefix}/gemini/daily")

    for response in (budget, daily):
        assert response.status_code == 503
        assert SECRET not in response.text
        body = response.json()
        message = body["message"] if prefix.startswith("/api/v2") else body["detail"]
        assert "today" in message and "minute" not in message
    # Refused here: the time is the budget's own. Refused by Google: the time to the next reset.
    assert budget.headers["Retry-After"] == "4321"
    assert 1 <= int(daily.headers["Retry-After"]) <= 86400
    if prefix.startswith("/api/v2"):
        assert budget.json()["code"] == daily.json()["code"] == "ai_busy"


def test_a_busy_model_still_says_try_again_in_a_minute(client: TestClient) -> None:
    response = client.get("/api/v2/_probe/gemini/busy")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert "minute" in response.json()["message"]
