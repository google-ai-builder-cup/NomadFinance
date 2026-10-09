"""NF-FC-008 through the API: start or resume, read, overview, flag, ownership and shape."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.schemas.coach_session import CoachOverview, CoachSession, CoachSessionCreateResponse
from tests.fixtures.coach_sessions import (
    NOW,
    FakePlanRepo,
    FakeSessionRepo,
    make_coach_app,
    make_sessions,
)

SESSIONS = "/api/v2/coach/sessions"
OVERVIEW = "/api/v2/coach/overview"
MOCK_DIR = Path(__file__).resolve().parents[4] / "docs" / "mocks" / "coach"

# Never in an answer (docs/api/v2-coach.md, "What every route shares").
HIDDEN = {"revision", "models", "prompt_versions", "declined_slots", "question_bank_version"}


def _client(
    repo: FakeSessionRepo | None = None,
    plans: FakePlanRepo | None = None,
    uid: str = "test-user",
    **options: Any,
) -> tuple[TestClient, FakeSessionRepo, FakePlanRepo]:
    service, repo, plans = make_sessions(repo, plans)
    app = make_coach_app(service, uid=uid, **options)
    return TestClient(app, raise_server_exceptions=False), repo, plans


def _mock(name: str) -> dict[str, Any]:
    sample: dict[str, Any] = json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))
    return sample


def test_the_first_start_is_a_201_with_a_new_empty_session() -> None:
    api, repo, _ = _client()

    response = api.post(SESSIONS, json={"language": "hi"})

    assert response.status_code == 201
    body = response.json()
    created = CoachSessionCreateResponse.model_validate(body)
    assert created.resumed is False and created.stage == "intro"
    assert created.next_slot == "destination_country" and created.messages == []
    assert len(repo.docs) == 1
    assert response.headers["X-Request-ID"]


def test_asking_again_is_a_200_with_the_same_session_marked_resumed() -> None:
    api, repo, _ = _client()
    first = api.post(SESSIONS, json={"language": "hi"}).json()

    second = api.post(SESSIONS, json={"language": "en"})

    assert second.status_code == 200
    assert second.json()["id"] == first["id"] and second.json()["resumed"] is True
    assert second.json()["language"] == "hi"
    assert len(repo.docs) == 1


def test_restart_gives_a_new_201_session_and_closes_the_old_one() -> None:
    api, repo, _ = _client()
    first = api.post(SESSIONS, json={"language": "hi"}).json()

    second = api.post(SESSIONS, json={"language": "en", "restart": True})

    assert second.status_code == 201 and second.json()["id"] != first["id"]
    assert repo.docs[("test-user", first["id"])]["status"] == "abandoned"
    assert api.get(f"{SESSIONS}/{first['id']}").json()["status"] == "abandoned"


def test_the_answer_has_the_fields_of_the_samples_and_nothing_internal() -> None:
    api, _, _ = _client()
    body = api.post(SESSIONS, json={"language": "en"}).json()

    sample = _mock("sessions-create-01-new.json")["body"]
    assert set(body) == set(sample)
    assert not HIDDEN & set(body)
    got = api.get(f"{SESSIONS}/{body['id']}").json()
    assert set(got) == set(body) - {"resumed"}
    assert not HIDDEN & set(got)
    CoachSession.model_validate(got)


def test_a_session_is_read_by_its_owner_only() -> None:
    mine, repo, plans = _client(uid="alice")
    session = mine.post(SESSIONS, json={"language": "en"}).json()
    other, _, _ = _client(repo, plans, uid="bob")

    assert mine.get(f"{SESSIONS}/{session['id']}").status_code == 200
    stranger = other.get(f"{SESSIONS}/{session['id']}")
    missing = other.get(f"{SESSIONS}/s_99")

    assert stranger.status_code == missing.status_code == 404
    assert stranger.json()["code"] == missing.json()["code"] == "not_found"
    assert stranger.json()["message"] == missing.json()["message"]


def test_an_id_that_cannot_exist_is_the_same_404() -> None:
    api, _, _ = _client()

    for bad in ("__bad__", "a" * 200, "x.y"):
        response = api.get(f"{SESSIONS}/{bad}")
        assert response.status_code == 404 and response.json()["code"] == "not_found"


def test_a_language_outside_the_six_is_a_422_and_creates_nothing() -> None:
    api, repo, _ = _client()

    response = api.post(SESSIONS, json={"language": "fr"})

    assert response.status_code == 422 and response.json()["code"] == "validation_failed"
    assert repo.docs == {}


def test_a_missing_language_is_a_422() -> None:
    api, _, _ = _client()

    assert api.post(SESSIONS, json={}).status_code == 422


def test_without_a_token_every_route_is_a_401() -> None:
    api, _, _ = _client(signed_in=False)

    responses = [
        api.post(SESSIONS, json={"language": "en"}),
        api.get(f"{SESSIONS}/s_01"),
        api.get(OVERVIEW),
    ]

    for response in responses:
        assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


def test_with_the_flag_off_every_route_is_the_404_of_an_unknown_path() -> None:
    api, repo, _ = _client(flag_on=False)

    for response in (
        api.post(SESSIONS, json={"language": "en"}),
        api.get(f"{SESSIONS}/s_01"),
        api.get(OVERVIEW),
    ):
        assert response.status_code == 404 and response.json()["code"] == "not_found"
    assert repo.docs == {}


def test_a_session_idle_for_two_weeks_reads_as_abandoned_through_the_api() -> None:
    api, repo, _ = _client()
    session = api.post(SESSIONS, json={"language": "en"}).json()
    document = repo.docs[("test-user", session["id"])]
    long_ago = datetime.now(UTC) - timedelta(days=15)
    document["last_active"] = long_ago
    document["created_at"] = long_ago
    document["expires_at"] = datetime.now(UTC) + timedelta(days=15)

    response = api.get(f"{SESSIONS}/{session['id']}")

    assert response.status_code == 200 and response.json()["status"] == "abandoned"
    fresh = api.post(SESSIONS, json={"language": "en"})
    assert fresh.status_code == 201 and fresh.json()["id"] != session["id"]


def test_the_overview_of_a_new_worker_is_empty() -> None:
    api, repo, _ = _client()

    response = api.get(OVERVIEW)

    assert response.status_code == 200
    assert response.json() == _mock("overview-04-empty.json")["body"]
    assert repo.docs == {}


def test_the_overview_has_the_session_and_the_newest_plan_in_the_shape_of_the_samples() -> None:
    api, _, plans = _client()
    session = api.post(SESSIONS, json={"language": "hi"}).json()
    plans.add(
        "test-user",
        "9f3a1c5e7b2d4a60c8e1",
        {
            "created_at": NOW,
            "score": {"total": 57, "band": "getting_ready"},
            "departure_date": "2026-12-01",
        },
    )

    body = api.get(OVERVIEW).json()

    CoachOverview.model_validate(body)
    sample = _mock("overview-03-session-and-plan.json")["body"]
    assert set(body) == set(sample) and set(body["session"]) == set(sample["session"])
    assert set(body["plan"]) == set(sample["plan"])
    assert body["session"]["id"] == session["id"]
    assert body["plan"]["score_total"] == 57 and body["plan"]["band"] == "getting_ready"


def test_a_plan_without_a_departure_date_has_none_in_the_overview() -> None:
    api, _, plans = _client()
    plans.add(
        "test-user", "a" * 20, {"created_at": NOW, "score": {"total": 30, "band": "needs_work"}}
    )

    assert api.get(OVERVIEW).json()["plan"]["departure_date"] is None


def test_a_burst_of_starts_that_gives_up_is_a_409_with_retry_after() -> None:
    api, repo, _ = _client()
    repo.contended = True

    response = api.post(SESSIONS, json={"language": "en"})

    assert response.status_code == 409 and response.json()["code"] == "request_in_progress"
    assert response.headers["Retry-After"] == "2"
    assert repo.docs == {}
