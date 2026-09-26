from __future__ import annotations

import base64
import binascii
import json
import math
import time

from fastapi import HTTPException, Request, status
from limits import RateLimitItem, parse_many
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings
from app.utils.hashing import hash_user_id

# Built on `limits`, the engine behind slowapi. slowapi 0.1.10's middleware cannot find
# routes inside FastAPI 0.141's included routers and silently skips every /api/v1 route.
# Memory storage: counted per Cloud Run instance, reset when an instance restarts.
_limiter = MovingWindowRateLimiter(MemoryStorage())

TOO_MANY_REQUESTS = "Too many requests. Please wait a minute and try again."
_LIMITED_PREFIX = "/api/"
# Only Cloud Scheduler can call these (OIDC check); a retried cron run must never be refused.
_EXEMPT_PREFIXES = ("/api/v1/internal/",)


def _unverified_uid(authorization: str | None) -> str | None:
    """The `sub` claim of a bearer token, read WITHOUT checking the signature.

    Only used to pick whose counter a request uses. The endpoint still verifies the token,
    so a forged `sub` only earns a fresh counter for a request that ends in 401.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    parts = authorization[7:].strip().split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (binascii.Error, ValueError):
        return None
    sub = payload.get("sub") if isinstance(payload, dict) else None
    # Firebase uids are at most 128 characters.
    return sub if isinstance(sub, str) and 0 < len(sub) <= 128 else None


def client_ip(headers: Headers, client: tuple[str, int] | None) -> str:
    """The caller's IP. On Cloud Run, Google's front end appends the address it saw to
    X-Forwarded-For, so the last entry is the real one; earlier entries are client-supplied
    and could be forged."""
    last_hop = headers.get("x-forwarded-for", "").rsplit(",", 1)[-1].strip()
    if last_hop:
        return last_hop
    return client[0] if client else "unknown"


def rate_limit_key(headers: Headers, client: tuple[str, int] | None) -> str:
    """Count signed-in requests per user and anonymous ones per IP.

    Per user because many workers share one IP (dormitory Wi-Fi, carrier NAT): a per-IP
    limit would block them together. The uid is hashed so it never sits in memory in clear.
    """
    uid = _unverified_uid(headers.get("authorization"))
    if uid is not None:
        return f"user:{hash_user_id(uid)}"
    return f"ip:{client_ip(headers, client)}"


class _Verdict:
    """Outcome of one check: allowed or not, and the numbers for the response headers."""

    def __init__(self, allowed: bool, item: RateLimitItem, remaining: int, reset_at: float):
        self.allowed = allowed
        self.item = item
        self.remaining = remaining
        self.reset_at = reset_at

    def headers(self) -> dict[str, str]:
        reset_in = max(1, math.ceil(self.reset_at - time.time()))
        headers = {
            "X-RateLimit-Limit": str(self.item.amount),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(reset_in),
        }
        if not self.allowed:
            headers["Retry-After"] = str(reset_in)
        return headers


def _check(limit: str, namespace: str, key: str) -> _Verdict:
    """Count one request against every item of `limit` ("60/minute;1000/day").

    All items are tested before any is counted, so a refused request uses up nothing. The
    verdict reports the item closest to running out.
    """
    items = parse_many(limit)
    for item in items:
        if not _limiter.test(item, namespace, key):
            stats = _limiter.get_window_stats(item, namespace, key)
            return _Verdict(False, item, 0, stats.reset_time)
    for item in items:
        _limiter.hit(item, namespace, key)
    tightest = min(items, key=lambda item: _limiter.get_window_stats(item, namespace, key)[1])
    stats = _limiter.get_window_stats(tightest, namespace, key)
    return _Verdict(True, tightest, stats.remaining, stats.reset_time)


def reset_rate_limits() -> None:
    """Forget every count (tests)."""
    _limiter.storage.reset()


class RateLimitMiddleware:
    """One budget per caller for the whole API (`RATE_LIMIT_DEFAULT`, 60 a minute).

    Only paths under /api/ count; internal cron endpoints and /health never do. Checked
    before the request body is read, so a refused upload costs almost nothing. Answers 429
    with Retry-After, and adds X-RateLimit-* to every counted response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        settings = get_settings()
        path: str = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not settings.rate_limit_enabled
            or not path.startswith(_LIMITED_PREFIX)
            or path.startswith(_EXEMPT_PREFIXES)
        ):
            await self.app(scope, receive, send)
            return

        key = rate_limit_key(Headers(scope=scope), scope.get("client"))
        verdict = _check(settings.rate_limit_default, "api", key)
        if not verdict.allowed:
            response = JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": TOO_MANY_REQUESTS},
                headers=verdict.headers(),
            )
            await response(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # A 429 from limit_ai_calls already carries the numbers of the limit it hit.
                for name, value in verdict.headers().items():
                    if name not in headers:
                        headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def limit_ai_calls(request: Request) -> None:
    """Stricter budget for endpoints that call Gemini (`RATE_LIMIT_AI`, 10 a minute).

    All users share one free-tier Gemini quota, so one person must not use it up. Add
    `dependencies=[Depends(limit_ai_calls)]` to every endpoint that calls Gemini. It is
    counted in addition to the API-wide budget.
    """
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return
    key = rate_limit_key(request.headers, (request.client.host, 0) if request.client else None)
    verdict = _check(settings.rate_limit_ai, "ai", key)
    if not verdict.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY_REQUESTS, headers=verdict.headers()
        )
