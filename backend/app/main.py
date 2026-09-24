from __future__ import annotations

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.schemas.common import HealthResponse


def create_app() -> FastAPI:
    """Build the FastAPI application.

    Settings are resolved here so a missing required env var aborts startup
    instead of surfacing on the first request.
    """
    settings = get_settings()

    app = FastAPI(title=settings.app_name, version=settings.app_version)

    # Kept outside /api/v1 so Cloud Run and uptime checks have a stable, unversioned probe.
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=settings.app_version,
            environment=settings.app_env,
        )

    app.include_router(api_router, prefix="/api/v1")
    register_exception_handlers(app)
    return app


app = create_app()
