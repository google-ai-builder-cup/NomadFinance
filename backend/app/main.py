from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.api.v2.router import api_router as api_v2_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import REQUEST_ID_HEADER, configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.rate_limit import RateLimitMiddleware
from app.schemas.common import HealthResponse


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Settings are resolved here so a missing required env var aborts startup
    instead of surfacing on the first request.
    """
    settings = get_settings()
    configure_logging(settings)

    # The interactive docs list every endpoint and field to anyone, signed in or not, so only
    # local development serves them (NF-P4-004).
    docs = settings.app_env == "local"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    # Kept outside /api/v1 so Cloud Run and uptime checks have a stable, unversioned probe.
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=settings.app_version,
            environment=settings.app_env,
        )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(api_v2_router, prefix="/api/v2")
    register_exception_handlers(app)

    # The last middleware added is the outermost. Order of a request, outside in:
    # logging -> security headers -> CORS -> rate limit -> body size -> app. CORS wraps the two
    # that can refuse a request, so a 429 or 413 still carries CORS headers; without them the
    # browser hides the status and the app can only say "network error".
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.request_max_bytes)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        # Bearer tokens, never cookies, so no credentials mode.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER, "Idempotency-Key"],
        expose_headers=[
            REQUEST_ID_HEADER,
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            # Set by /api/v2 routes (docs/api/v2-conventions.md, sections 5 and 6).
            "Idempotency-Replayed",
            "Deprecation",
            "Sunset",
        ],
        # Browsers cache the preflight answer for up to this long (Chrome caps it at 2 h).
        max_age=3600,
    )
    # Added last so it is the outermost layer: it also times and logs whatever other
    # middleware answers or rejects a request.
    # Outside CORS, so a 413 or 429 from a middleware inside it carries the headers too.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    return app


app = create_app()
