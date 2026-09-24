from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    settings = get_settings()
    assert response.json() == {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.app_env,
    }


def test_health_is_listed_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
