from __future__ import annotations

import base64
import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.core.rate_limit import TOO_MANY_REQUESTS, rate_limit_key
from app.main import create_app

LOCAL_ORIGIN = "http://localhost:5173"
# Unauthenticated DELETE /users/me answers 401 without touching Firebase: a cheap counted path.
COUNTED = "/api/v1/users/me"


def _fake_token(sub: str) -> str:
    """A JWT-shaped string with this `sub`. Not signed: the app rejects it with 401."""

    def part(data: dict[str, str]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'RS256'})}.{part({'sub': sub})}.signature"


def _auth(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_fake_token(sub)}"}


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """Build the app with some settings overridden through the environment."""

    def build(**env: str) -> TestClient:
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        return TestClient(create_app())

    yield build
    get_settings.cache_clear()


@pytest.fixture
def client(make_client) -> TestClient:  # type: ignore[no-untyped-def]
    return make_client(RATE_LIMIT_DEFAULT="3/minute", RATE_LIMIT_AI="2/minute")  # type: ignore[no-any-return]


# --- CORS -----------------------------------------------------------------------------


def test_preflight_from_allowed_origin_is_accepted(client: TestClient) -> None:
    response = client.options(
        COUNTED,
        headers={
            "Origin": LOCAL_ORIGIN,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert "DELETE" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert response.headers["access-control-max-age"] == "3600"
    assert "access-control-allow-credentials" not in response.headers


def test_preflight_from_other_origin_is_refused(client: TestClient) -> None:
    response = client.options(
        COUNTED,
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "DELETE"},
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_response_exposes_request_id_and_rate_limit_headers(client: TestClient) -> None:
    response = client.delete(COUNTED, headers={"Origin": LOCAL_ORIGIN})

    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    exposed = response.headers["access-control-expose-headers"].lower()
    for name in ("x-request-id", "retry-after", "x-ratelimit-remaining"):
        assert name in exposed


def _settings(**values: object) -> Settings:
    base: dict[str, object] = {"gemini_api_key": "k", "_env_file": None}
    return Settings(**{**base, **values})  # type: ignore[arg-type]


def test_prod_defaults_to_the_firebase_hosting_origins() -> None:
    settings = _settings(app_env="prod", cron_service_account="s", cron_audience="a")

    assert settings.cors_allowed_origins == [
        "https://nomadfinance-prod.web.app",
        "https://nomadfinance-prod.firebaseapp.com",
    ]


def test_local_defaults_to_the_vite_origins() -> None:
    assert LOCAL_ORIGIN in _settings(app_env="local").cors_allowed_origins


def test_configured_origins_replace_the_defaults() -> None:
    settings = _settings(app_env="local", cors_allowed_origins=["https://demo.example"])

    assert settings.cors_allowed_origins == ["https://demo.example"]


@pytest.mark.parametrize("origin", ["*", "https://nomadfinance-prod.web.app/", "web.app"])
def test_malformed_origin_is_rejected(origin: str) -> None:
    with pytest.raises(ValidationError, match="is not an origin"):
        _settings(app_env="local", cors_allowed_origins=[origin])


def test_malformed_rate_limit_is_rejected() -> None:
    with pytest.raises(ValidationError, match="RATE_LIMIT_DEFAULT"):
        _settings(app_env="local", rate_limit_default="sixty a minute")


# --- API-wide rate limit --------------------------------------------------------------


def test_limit_answers_429_with_retry_after_and_cors(client: TestClient) -> None:
    for remaining in ("2", "1", "0"):
        response = client.delete(COUNTED, headers=_auth("alice"))
        assert response.status_code == 401
        assert response.headers["x-ratelimit-limit"] == "3"
        assert response.headers["x-ratelimit-remaining"] == remaining

    refused = client.delete(COUNTED, headers={**_auth("alice"), "Origin": LOCAL_ORIGIN})

    assert refused.status_code == 429
    assert refused.json() == {"detail": TOO_MANY_REQUESTS}
    assert 1 <= int(refused.headers["retry-after"]) <= 60
    assert refused.headers["access-control-allow-origin"] == LOCAL_ORIGIN
    assert refused.headers["x-request-id"]


def test_each_user_has_their_own_budget(client: TestClient) -> None:
    for _ in range(3):
        client.delete(COUNTED, headers=_auth("alice"))

    assert client.delete(COUNTED, headers=_auth("alice")).status_code == 429
    assert client.delete(COUNTED, headers=_auth("bob")).status_code == 401


def test_budget_is_shared_across_endpoints(client: TestClient) -> None:
    client.delete(COUNTED, headers=_auth("alice"))
    client.post("/api/v1/contracts/extract", headers=_auth("alice"))
    client.get("/api/v1/does-not-exist", headers=_auth("alice"))

    assert client.delete(COUNTED, headers=_auth("alice")).status_code == 429


def test_anonymous_callers_are_counted_by_the_last_forwarded_ip(client: TestClient) -> None:
    # A client can prepend anything to X-Forwarded-For; only the last hop is trusted.
    for forged in ("1.1.1.1", "2.2.2.2", "3.3.3.3"):
        client.delete(COUNTED, headers={"X-Forwarded-For": f"{forged}, 203.0.113.7"})

    same_ip = client.delete(COUNTED, headers={"X-Forwarded-For": "4.4.4.4, 203.0.113.7"})
    other_ip = client.delete(COUNTED, headers={"X-Forwarded-For": "203.0.113.8"})

    assert same_ip.status_code == 429
    assert other_ip.status_code == 401


def test_internal_cron_endpoints_are_never_limited(client: TestClient) -> None:
    for _ in range(6):
        response = client.post("/api/v1/internal/refresh-rates", headers=_auth("alice"))
        assert response.status_code != 429
        assert "x-ratelimit-limit" not in response.headers


def test_health_is_never_limited(client: TestClient) -> None:
    for _ in range(6):
        response = client.get("/health")
        assert response.status_code == 200
        assert "x-ratelimit-limit" not in response.headers


def test_rate_limiting_can_be_switched_off(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(RATE_LIMIT_DEFAULT="1/minute", RATE_LIMIT_ENABLED="false")

    codes = {client.delete(COUNTED).status_code for _ in range(4)}

    assert codes == {401}


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer not-a-jwt",
        "Bearer a.%%%.c",
        "Basic dXNlcjpwYXNz",
        f"Bearer {_fake_token('x' * 200)}",
    ],
)
def test_unusable_tokens_fall_back_to_the_ip(authorization: str) -> None:
    from starlette.datastructures import Headers

    headers = Headers({"authorization": authorization})

    assert rate_limit_key(headers, ("198.51.100.1", 1234)) == "ip:198.51.100.1"


def test_user_key_holds_a_hash_not_the_uid() -> None:
    from starlette.datastructures import Headers

    key = rate_limit_key(Headers(_auth("uid_priya_demo")), None)

    assert key.startswith("user:")
    assert "uid_priya_demo" not in key


# --- Gemini endpoints -----------------------------------------------------------------


def test_gemini_endpoint_has_a_stricter_budget(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(RATE_LIMIT_DEFAULT="10/minute", RATE_LIMIT_AI="2/minute")
    for _ in range(2):
        assert client.post("/api/v1/contracts/extract", headers=_auth("alice")).status_code == 401

    refused = client.post("/api/v1/contracts/extract", headers=_auth("alice"))

    assert refused.status_code == 429
    assert refused.json() == {"detail": TOO_MANY_REQUESTS}
    assert refused.headers["x-ratelimit-limit"] == "2"
    assert int(refused.headers["retry-after"]) >= 1
    # Other endpoints still work: the API-wide budget (10) is not used up.
    assert client.delete(COUNTED, headers=_auth("alice")).status_code == 401


# --- Request size (D-05) --------------------------------------------------------------


def test_declared_oversized_body_is_refused_before_reading(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(UPLOAD_MAX_BYTES="1000")
    body = b"x" * (1000 + 64 * 1024 + 1)

    response = client.post(
        "/api/v1/contracts/extract",
        content=body,
        headers={"Content-Type": "application/octet-stream", "Origin": LOCAL_ORIGIN},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The request is larger than 0 MB."}
    assert response.headers["access-control-allow-origin"] == LOCAL_ORIGIN


def test_streamed_oversized_upload_is_cut_off(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(UPLOAD_MAX_BYTES=str(1024 * 1024))
    boundary = "b0undary"

    def chunks() -> Iterator[bytes]:
        yield (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            'filename="big.pdf"\r\nContent-Type: application/pdf\r\n\r\n'
        ).encode()
        for _ in range(40):  # 2.5 MB, over the 1 MB (+64 KB) limit
            yield b"%" * 65536
        yield f"\r\n--{boundary}--\r\n".encode()

    response = client.post(
        "/api/v1/contracts/extract",
        content=chunks(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **_auth("a")},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "The request is larger than 1 MB."}


def test_body_within_the_limit_passes(client: TestClient) -> None:
    response = client.post(
        "/api/v1/contracts/extract",
        files={"file": ("c.pdf", b"%PDF-1.4 small", "application/pdf")},
        headers=_auth("alice"),
    )

    # Reaches the endpoint's own checks: the fake token is refused.
    assert response.status_code == 401
