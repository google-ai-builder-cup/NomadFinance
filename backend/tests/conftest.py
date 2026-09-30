from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Must be set before app.main is imported: the module builds the app, and settings
# fail fast without APP_ENV.
os.environ.setdefault("APP_ENV", "local")
# Live tests read the real key from .env.local; an env var would shadow it.
if os.environ.get("RUN_LIVE_GEMINI") != "1":
    os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("RADAR_REPORTER_HASH_SECRET", "test-reporter-hash-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.rate_limit import reset_rate_limits  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    # The limiter keeps counts in process memory; without this, tests would share budgets.
    reset_rate_limits()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def anyio_backend() -> str:
    """Run `@pytest.mark.anyio` async tests on asyncio only (no trio in this project)."""
    return "asyncio"
