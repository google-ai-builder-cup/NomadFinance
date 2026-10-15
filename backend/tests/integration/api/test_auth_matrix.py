"""Authentication bypass tests (NF-P4-004).

Unlike the endpoint tests, nothing here replaces `get_current_user`: every request goes through
the real bearer check and the real `firebase_admin` token verification. Only the two network
calls are faked, so the tests run offline: Google's signing certificates (replaced by a
throwaway key pair made in this file) and the user lookup behind revocation checks.

Every bad token must end in 401 on every route behind sign-in, and none may reach a handler.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Annotated, Any

import firebase_admin  # type: ignore[import-untyped]
import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from firebase_admin import auth as firebase_auth
from google.auth import credentials as google_credentials
from starlette.routing import BaseRoute

from app.config import get_settings
from app.dependencies import get_current_user, require_cloud_scheduler
from app.main import create_app
from app.schemas.user import AuthenticatedUser

KID = "test-key-1"
CRON_EMAIL = "scheduler@nomadfinance-prod.iam.gserviceaccount.com"
CRON_AUDIENCE = "https://api.example.test"


# --- a throwaway Google: keys, certificates, tokens ---------------------------------------


def _make_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _certificate_pem(key: rsa.RSAPrivateKey) -> str:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


def _private_pem(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


class Google:
    """The signing side of Google for these tests: one trusted key, one attacker key."""

    def __init__(self) -> None:
        self.key = _make_key()
        self.attacker_key = _make_key()
        self.certificate = _certificate_pem(self.key)
        # Set per test: what the "user lookup" behind check_revoked answers.
        self.user = SimpleNamespace(disabled=False, tokens_valid_after_timestamp=0)
        self.user_missing = False

    def sign(
        self,
        claims: dict[str, Any],
        *,
        key: rsa.RSAPrivateKey | None = None,
        kid: str | None = KID,
    ) -> str:
        headers = {"kid": kid} if kid else {}
        return jwt.encode(claims, _private_pem(key or self.key), algorithm="RS256", headers=headers)


@pytest.fixture(scope="module")
def google() -> Google:
    return Google()


def _project() -> str:
    return get_settings().firebase_project_id


def id_token_claims(**override: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": f"https://securetoken.google.com/{_project()}",
        "aud": _project(),
        "sub": "alice",
        "user_id": "alice",
        "iat": now - 10,
        "auth_time": now - 10,
        "exp": now + 3600,
        "firebase": {"sign_in_provider": "phone", "identities": {}},
        "phone_number": "+6581230700",
    }
    claims.update(override)
    return {k: v for k, v in claims.items() if v is not None}


def oidc_claims(**override: Any) -> dict[str, Any]:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CRON_AUDIENCE,
        "sub": "1234567890",
        "email": CRON_EMAIL,
        "email_verified": True,
        "iat": now - 10,
        "exp": now + 3600,
    }
    claims.update(override)
    return claims


def _hs256_with_public_certificate(claims: dict[str, Any], certificate: str) -> str:
    """The classic key-confusion token: HMAC-signed with the public RSA certificate as the secret.

    Built by hand because PyJWT refuses to make it.
    """

    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    signing_input = f"{part({'alg': 'HS256', 'typ': 'JWT', 'kid': KID})}.{part(claims)}"
    signature = hmac.new(certificate.encode(), signing_input.encode(), hashlib.sha256).digest()
    return signing_input + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def _unsigned(claims: dict[str, Any]) -> str:
    def part(data: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT', 'kid': KID})}.{part(claims)}."


@pytest.fixture(autouse=True)
def real_verification(
    monkeypatch: pytest.MonkeyPatch, google: Google, _fresh_rate_limits: None
) -> Iterator[None]:
    """Run the real verification code with Google's network calls replaced."""
    # With this set, firebase-admin skips signature checks: the first thing a test must rule out.
    for name in ("FIREBASE_AUTH_EMULATOR_HOST", "FIRESTORE_EMULATOR_HOST"):
        monkeypatch.delenv(name, raising=False)
    # The budgets run before authentication and would answer 429 to a long list of probes;
    # they are tested on their own (test_rate_limit_verification.py).
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("CRON_SERVICE_ACCOUNT", CRON_EMAIL)
    monkeypatch.setenv("CRON_AUDIENCE", CRON_AUDIENCE)
    get_settings.cache_clear()

    monkeypatch.setattr(
        "google.oauth2.id_token._fetch_certs", lambda request, certs_url: {KID: google.certificate}
    )

    class _NoCredentials(firebase_admin.credentials.Base):  # type: ignore[misc]
        def get_credential(self) -> google_credentials.Credentials:
            return google_credentials.AnonymousCredentials()

    app_name = f"auth-matrix-{id(google)}"
    try:
        fake_app = firebase_admin.get_app(app_name)
    except ValueError:
        fake_app = firebase_admin.initialize_app(
            _NoCredentials(), options={"projectId": _project()}, name=app_name
        )
    monkeypatch.setattr("app.core.security.get_firebase_app", lambda: fake_app)

    def get_user(self: object, uid: str) -> SimpleNamespace:
        if google.user_missing:
            raise firebase_auth.UserNotFoundError("no user")
        return google.user

    monkeypatch.setattr("firebase_admin._auth_client.Client.get_user", get_user)
    google.user = SimpleNamespace(disabled=False, tokens_valid_after_timestamp=0)
    google.user_missing = False
    yield
    get_settings.cache_clear()


# --- the routes ---------------------------------------------------------------------------


def _routes(routes: list[BaseRoute]) -> Iterator[Any]:
    """Every endpoint with its full path. Included routers expose one context per endpoint."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "effective_route_contexts"):
            yield from route.effective_route_contexts()


def _dependency_names(route: Any) -> set[str]:
    names: set[str] = set()

    def walk(dependant: Any) -> None:
        for sub in dependant.dependencies:
            names.add(getattr(sub.call, "__name__", str(sub.call)))
            walk(sub)

    walk(route.dependant)
    return names


def _all_routes() -> list[tuple[str, str, Any]]:
    app = create_app()
    found = []
    for route in _routes(app.routes):
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            found.append((method, route.path, route))
    return found


ROUTES = _all_routes()

# The only endpoints without a user token, and why. A new route must either use
# `get_current_user` or be added here on purpose.
PUBLIC = {("GET", "/health"), ("GET", "/api/v1/public/stats")}
INTERNAL_PREFIX = "/api/v1/internal/"
INTERNAL = [(m, p) for m, p, _ in ROUTES if p.startswith(INTERNAL_PREFIX)]
USER_ROUTES = [(m, p) for m, p, r in ROUTES if "get_current_user" in _dependency_names(r)]

# Endpoints that call Gemini and so carry the stricter budget (limit_ai_calls). Listed so
# that adding an AI endpoint without a budget, or removing one, is a deliberate edit.
AI_LIMITED = {
    ("POST", "/api/v1/contracts/extract"),
    ("POST", "/api/v1/contracts/detect"),
    ("POST", "/api/v1/contracts/compare"),
    ("POST", "/api/v1/contracts/translate"),
    ("POST", "/api/v1/contracts/complaint"),
    ("POST", "/api/v1/contracts"),
    ("POST", "/api/v1/contracts/{contract_id}/analyze"),
    ("POST", "/api/v1/contracts/{contract_id}/reports/{language}"),
    ("POST", "/api/v1/fib/bill/scan"),
    ("POST", "/api/v1/fib/categorize"),
    # The report text of a score worked out on request: one reasoning-tier call.
    ("POST", "/api/v1/fib/profile/refresh"),
    ("POST", "/api/v1/radar/report"),
    ("POST", "/api/v1/remittance/recommend"),
    # Embeds the report text (a Gemini call) before it writes the Radar report (NF-SA-013).
    ("POST", "/api/v2/scam/checks/{check_id}/report"),
    # One turn of the Financial Coach: a streamed Gemini reply (NF-FC-009, 10 a minute).
    ("POST", "/api/v2/coach/sessions/{session_id}/messages"),
    # The 90-day plan: one reasoning-tier call whose sentences are checked (NF-FC-012).
    ("POST", "/api/v2/coach/sessions/{session_id}/plan"),
}

# Calls Gemini but spends its own budget inside the handler (20 an hour per worker, and only for
# a check that needs a model, NF-SA-012). `limit_ai_calls` runs before the message is looked up,
# so it would also count a repeat answered from storage, which the contract says is free.
OWN_HOURLY_BUDGET = {("POST", "/api/v2/scam/analyze")}

_PATH_VALUES = {"language": "en", "host_country": "SG", "slug": "example-agency"}


def _url(path: str) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: _PATH_VALUES.get(m.group(1), "A" * 20), path)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


def _call(client: TestClient, method: str, path: str, headers: dict[str, str]) -> int:
    return client.request(method, _url(path), headers=headers).status_code


def _offenders(
    client: TestClient, routes: list[tuple[str, str]], headers: dict[str, str], expected: set[int]
) -> list[str]:
    bad = []
    for method, path in routes:
        status = _call(client, method, path, headers)
        if status not in expected:
            bad.append(f"{method} {path} -> {status}")
    return bad


# --- 1. the route table -------------------------------------------------------------------


def test_every_route_needs_a_user_token_except_the_listed_ones() -> None:
    unprotected = [
        f"{m} {p}"
        for m, p, r in ROUTES
        if (m, p) not in PUBLIC
        and not p.startswith(INTERNAL_PREFIX)
        and "get_current_user" not in _dependency_names(r)
    ]
    assert unprotected == [], f"routes without get_current_user: {unprotected}"


def test_internal_routes_are_checked_as_cloud_scheduler_and_not_as_users() -> None:
    assert INTERNAL, "no internal routes found"
    for method, path, route in ROUTES:
        if path.startswith(INTERNAL_PREFIX):
            names = _dependency_names(route)
            assert "require_cloud_scheduler" in names, f"{method} {path}"
            assert "get_current_user" not in names, f"{method} {path}"


def test_the_public_routes_are_exactly_the_listed_ones() -> None:
    public = {
        (m, p)
        for m, p, r in ROUTES
        if not p.startswith(INTERNAL_PREFIX) and "get_current_user" not in _dependency_names(r)
    }
    assert public == PUBLIC


def test_ai_endpoints_carry_the_stricter_budget() -> None:
    limited = {(m, p) for m, p, r in ROUTES if "limit_ai_calls" in _dependency_names(r)}
    assert limited == AI_LIMITED
    assert not limited & OWN_HOURLY_BUDGET


# --- 2. bad tokens on every route behind sign-in ------------------------------------------


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bad_tokens(google: Google) -> dict[str, dict[str, str]]:
    now = int(time.time())
    return {
        "no header": {},
        "empty bearer": {"Authorization": "Bearer "},
        "wrong scheme": {"Authorization": f"Basic {base64.b64encode(b'alice:pw').decode()}"},
        "not a jwt": _bearer("not-a-jwt"),
        "three junk parts": _bearer("a.b.c"),
        "unsigned (alg none) with valid claims": _bearer(_unsigned(id_token_claims())),
        "HS256 signed with the public certificate": _bearer(
            _hs256_with_public_certificate(id_token_claims(), google.certificate)
        ),
        "signed by another key, right kid": _bearer(
            google.sign(id_token_claims(), key=google.attacker_key)
        ),
        "signed by another key, unknown kid": _bearer(
            google.sign(id_token_claims(), key=google.attacker_key, kid="other")
        ),
        "no kid": _bearer(google.sign(id_token_claims(), kid=None)),
        "expired": _bearer(google.sign(id_token_claims(exp=now - 60, iat=now - 3600))),
        "issued in the future": _bearer(google.sign(id_token_claims(iat=now + 3600))),
        "another project's audience": _bearer(google.sign(id_token_claims(aud="other-project"))),
        "another project's issuer": _bearer(
            google.sign(id_token_claims(iss="https://securetoken.google.com/other-project"))
        ),
        "wrong issuer host": _bearer(google.sign(id_token_claims(iss="https://evil.example"))),
        "no subject": _bearer(google.sign(id_token_claims(sub=None))),
        "empty subject": _bearer(google.sign(id_token_claims(sub=""))),
        "subject over 128 characters": _bearer(google.sign(id_token_claims(sub="a" * 129))),
        "custom token audience": _bearer(
            google.sign(
                id_token_claims(
                    aud="https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit"
                )
            )
        ),
        "a cron (OIDC) token": _bearer(google.sign(oidc_claims())),
        "a token with a null byte": _bearer("abc\x00def.ghi.jkl"),
    }


def test_every_bad_token_is_a_401_on_every_user_route(client: TestClient, google: Google) -> None:
    failures = {}
    for label, headers in _bad_tokens(google).items():
        bad = _offenders(client, USER_ROUTES, headers, {401})
        if bad:
            failures[label] = bad
    assert failures == {}


def test_a_valid_token_for_a_revoked_session_is_a_401(client: TestClient, google: Google) -> None:
    now = int(time.time())
    # `tokens_valid_after` is when the user last signed out everywhere (milliseconds).
    google.user = SimpleNamespace(disabled=False, tokens_valid_after_timestamp=(now + 5) * 1000)
    headers = _bearer(google.sign(id_token_claims()))

    assert _offenders(client, USER_ROUTES, headers, {401}) == []


def test_a_valid_token_for_a_disabled_user_is_a_401(client: TestClient, google: Google) -> None:
    google.user = SimpleNamespace(disabled=True, tokens_valid_after_timestamp=0)
    headers = _bearer(google.sign(id_token_claims()))

    assert _offenders(client, USER_ROUTES, headers, {401}) == []


def test_a_valid_token_for_a_deleted_user_is_a_401(client: TestClient, google: Google) -> None:
    # After account deletion (DELETE /users/me) the old token stays valid for up to an hour.
    google.user_missing = True
    headers = _bearer(google.sign(id_token_claims()))

    assert _offenders(client, USER_ROUTES, headers, {401}) == []


@pytest.mark.parametrize(
    "headers",
    [
        {"X-User-Id": "alice"},
        {"X-Uid": "alice"},
        {"X-Forwarded-User": "alice"},
        {"X-Goog-Authenticated-User-Email": "accounts.google.com:alice@example.com"},
        {"X-Firebase-AppCheck": "anything"},
        {"Cookie": "session=alice; __session=alice"},
        {"Authorization": "alice"},
        {"Proxy-Authorization": "Bearer x"},
    ],
    ids=lambda h: next(iter(h)),
)
def test_identity_claims_outside_the_bearer_token_are_ignored(
    client: TestClient, headers: dict[str, str]
) -> None:
    assert _offenders(client, USER_ROUTES, headers, {401}) == []


def test_a_token_in_the_query_string_is_not_accepted(client: TestClient, google: Google) -> None:
    token = google.sign(id_token_claims())
    for method, path in USER_ROUTES:
        status = client.request(
            method, _url(path), params={"access_token": token, "token": token, "uid": "alice"}
        ).status_code
        assert status == 401, f"{method} {path} -> {status}"


def test_a_401_does_not_say_why_in_a_way_that_helps_an_attacker(
    client: TestClient, google: Google
) -> None:
    response = client.get("/api/v1/remittance/trends", headers=_bearer("a.b.c"))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    # No stack trace or library internals in the body.
    assert set(response.json()) == {"detail"}
    assert "Traceback" not in response.text
    assert "firebase" not in response.text.lower()


# --- 3. the positive control: the same checks let a good token through --------------------


@pytest.fixture
def probe() -> Iterator[TestClient]:
    app = FastAPI()

    @app.get("/probe")
    async def whoami(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    ) -> dict[str, str]:
        return {"uid": user.uid}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_a_good_token_is_accepted_and_identifies_the_caller(
    probe: TestClient, google: Google
) -> None:
    # Without this, "everything is a 401" would pass even if the verifier were simply broken.
    response = probe.get("/probe", headers=_bearer(google.sign(id_token_claims(sub="alice"))))

    assert response.status_code == 200
    assert response.json() == {"uid": "alice"}


def test_the_caller_is_the_verified_subject_not_a_header(probe: TestClient, google: Google) -> None:
    headers = _bearer(google.sign(id_token_claims(sub="alice"))) | {"X-User-Id": "bob"}

    assert probe.get("/probe", headers=headers).json() == {"uid": "alice"}


# --- 4. Cloud Scheduler endpoints ---------------------------------------------------------


@pytest.fixture
def scheduler_probe() -> Iterator[TestClient]:
    app = FastAPI()

    @app.post("/internal-probe")
    async def run(
        caller: Annotated[str, Depends(require_cloud_scheduler)],
    ) -> dict[str, str]:
        return {"caller": caller}

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_the_scheduler_is_let_in(scheduler_probe: TestClient, google: Google) -> None:
    response = scheduler_probe.post("/internal-probe", headers=_bearer(google.sign(oidc_claims())))

    assert response.status_code == 200
    assert response.json() == {"caller": CRON_EMAIL}


def _scheduler_rejections(google: Google) -> dict[str, tuple[dict[str, str], set[int]]]:
    now = int(time.time())
    return {
        "no token": ({}, {401}),
        "junk": (_bearer("a.b.c"), {401}),
        "unsigned": (_bearer(_unsigned(oidc_claims())), {401}),
        "signed by another key": (
            _bearer(google.sign(oidc_claims(), key=google.attacker_key)),
            {401},
        ),
        "a signed-in worker's own token": (_bearer(google.sign(id_token_claims())), {401}),
        "wrong audience": (_bearer(google.sign(oidc_claims(aud="https://evil.example"))), {401}),
        "expired": (_bearer(google.sign(oidc_claims(exp=now - 60, iat=now - 3600))), {401}),
        "another service account": (
            _bearer(google.sign(oidc_claims(email="other@project.iam.gserviceaccount.com"))),
            {403},
        ),
        "the right email, not verified": (
            _bearer(google.sign(oidc_claims(email_verified=False))),
            {403},
        ),
        "no email": (_bearer(google.sign(oidc_claims(email=None))), {403}),
        "wrong issuer": (_bearer(google.sign(oidc_claims(iss="https://evil.example"))), {401}),
    }


def test_nobody_but_the_scheduler_gets_past_the_internal_check(
    scheduler_probe: TestClient, google: Google
) -> None:
    unexpected = {}
    for label, (headers, expected) in _scheduler_rejections(google).items():
        status = scheduler_probe.post("/internal-probe", headers=headers).status_code
        if status not in expected:
            unexpected[label] = status
    assert unexpected == {}


def test_every_internal_route_rejects_everyone_but_the_scheduler(
    client: TestClient, google: Google
) -> None:
    unexpected = []
    for label, (headers, expected) in _scheduler_rejections(google).items():
        for method, path in INTERNAL:
            status = _call(client, method, path, headers)
            if status not in expected:
                unexpected.append(f"{label}: {method} {path} -> {status}")
    assert unexpected == []


def test_internal_routes_are_closed_when_the_scheduler_is_not_configured(
    monkeypatch: pytest.MonkeyPatch, google: Google
) -> None:
    monkeypatch.delenv("CRON_SERVICE_ACCOUNT")
    monkeypatch.delenv("CRON_AUDIENCE")
    get_settings.cache_clear()
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        for method, path in INTERNAL:
            status = _call(client, method, path, _bearer(google.sign(oidc_claims())))
            assert status == 503, f"{method} {path} -> {status}"


def test_a_user_token_never_opens_an_internal_route(client: TestClient, google: Google) -> None:
    headers = _bearer(google.sign(id_token_claims()))

    assert _offenders(client, INTERNAL, headers, {401}) == []
