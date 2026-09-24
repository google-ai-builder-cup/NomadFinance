from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# Must be set before app.main is imported: the module builds the app, and settings
# fail fast without APP_ENV.
os.environ.setdefault("APP_ENV", "local")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
