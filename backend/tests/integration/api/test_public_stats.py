from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.public_stats_repo import get_public_stats_repository
from app.services import public_stats


class FakeRepository:
    def workers(self) -> int:
        return 5

    def contracts_checked(self) -> int:
        return 2

    def radar_reports(self) -> int:
        return 9

    def alerts_generated(self) -> int:
        return 1

    def scam_checks(self) -> tuple[int, int]:
        return 8, 6

    def coach_plans(self) -> int:
        return 0


@pytest.fixture
def stats_client() -> Iterator[TestClient]:
    public_stats.clear_cache()
    app = create_app()
    app.dependency_overrides[get_public_stats_repository] = FakeRepository
    yield TestClient(app)
    public_stats.clear_cache()


def test_anyone_can_read_the_totals_without_signing_in(stats_client: TestClient) -> None:
    response = stats_client.get("/api/v1/public/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["radar_reports"] == 9
    assert body["scam_messages_checked"] == 8
    assert body["scams_flagged"] == 6
    assert body["coach_plans"] == 0
    assert response.headers["cache-control"] == "public, max-age=300"


def test_the_answer_holds_counts_and_a_timestamp_only(stats_client: TestClient) -> None:
    body = stats_client.get("/api/v1/public/stats").json()

    assert set(body) == {
        "workers",
        "contracts_checked",
        "radar_reports",
        "alerts_generated",
        "scam_messages_checked",
        "scams_flagged",
        "coach_plans",
        "generated_at",
    }
