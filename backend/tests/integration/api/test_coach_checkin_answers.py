"""NF-FC-022 through the API: `PUT /api/v2/coach/plans/{id}/checkins/{milestone}`."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_feature_flag_service
from app.main import create_app
from app.repositories.coach_session_repo import get_coach_plan_repository
from app.schemas.coach_checkin import CheckinAnswerResponse
from app.schemas.errors import ErrorEnvelope
from app.schemas.user import AuthenticatedUser
from tests.fixtures.coach_checkins import DUE, PLAN_ID, FakeFlags, FakePlans, at

BODY = {"answers": {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"}}
URL = f"/api/v2/coach/plans/{PLAN_ID}/checkins/d30"


class _Clock:
    """What the service sees as now: the 30th day by default."""

    now = at(DUE["d30"], 9)


@pytest.fixture
def plans() -> FakePlans:
    store = FakePlans()
    store.add()
    return store


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> type[_Clock]:
    class FixedDatetime:
        @staticmethod
        def now(tz: Any = None) -> Any:
            return _Clock.now

    monkeypatch.setattr("app.api.v2.coach_checkins.datetime", FixedDatetime)
    return _Clock


def _app(plans: FakePlans, *, flag_on: bool = True, signed_in: bool = True) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_coach_plan_repository] = lambda: plans
    app.dependency_overrides[get_feature_flag_service] = lambda: FakeFlags(
        {"u1"} if flag_on else set()
    )
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid="u1")
    return app


@pytest.fixture
def api(plans: FakePlans, clock: type[_Clock]) -> TestClient:
    return TestClient(_app(plans), raise_server_exceptions=False)


def _error(response: Any, status: int, code: str) -> ErrorEnvelope:
    assert response.status_code == status, response.text
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == code and envelope.request_id == response.headers["X-Request-ID"]
    return envelope


def test_the_first_answer_is_200_with_the_stored_answers(api: TestClient, plans: FakePlans) -> None:
    response = api.put(URL, json=BODY)

    assert response.status_code == 200, response.text
    body = CheckinAnswerResponse.model_validate(response.json())
    assert body.already_answered is False and body.milestone == "d30" and body.plan_id == PLAN_ID
    assert body.answers.model_dump() == BODY["answers"]
    assert plans.marker()["d30"]["answers"] == BODY["answers"]


def test_sending_it_again_returns_the_first_answers_unchanged(api: TestClient) -> None:
    first = api.put(URL, json=BODY).json()
    other = {"answers": {"remittance": "not_yet", "savings": "not_yet", "pay": "not_paid"}}

    again = api.put(URL, json=other)

    assert again.status_code == 200
    assert again.json() == {**first, "already_answered": True}


def test_a_milestone_that_has_not_come_is_409_checkin_not_due(api: TestClient) -> None:
    response = api.put(f"/api/v2/coach/plans/{PLAN_ID}/checkins/d60", json=BODY)

    _error(response, 409, "checkin_not_due")


def test_a_plan_that_is_not_the_callers_or_does_not_exist_is_the_same_404(api: TestClient) -> None:
    missing = api.put(f"/api/v2/coach/plans/{'0' * 20}/checkins/d30", json=BODY)
    malformed = api.put("/api/v2/coach/plans/not-a-plan-id/checkins/d30", json=BODY)

    assert _error(missing, 404, "not_found").message == "Not Found"
    assert _error(malformed, 404, "not_found").message == "Not Found"


def test_a_bad_milestone_or_answer_is_422(api: TestClient) -> None:
    _error(
        api.put(f"/api/v2/coach/plans/{PLAN_ID}/checkins/d45", json=BODY), 422, "validation_failed"
    )
    bad = {"answers": {**BODY["answers"], "pay": "on_track"}}
    _error(api.put(URL, json=bad), 422, "validation_failed")
    extra = {"answers": {**BODY["answers"], "note": "typed text"}}
    _error(api.put(URL, json=extra), 422, "validation_failed")


def test_contention_is_409_request_in_progress_with_a_retry_after(
    api: TestClient, plans: FakePlans
) -> None:
    plans.contended = True

    response = api.put(URL, json=BODY)

    _error(response, 409, "request_in_progress")
    assert response.headers["Retry-After"] == "2"


def test_without_the_flag_it_is_the_404_of_an_unknown_path(
    plans: FakePlans, clock: type[_Clock]
) -> None:
    api = TestClient(_app(plans, flag_on=False), raise_server_exceptions=False)

    _error(api.put(URL, json=BODY), 404, "not_found")
    assert plans.marker() == {}


def test_without_a_token_it_is_401(plans: FakePlans, clock: type[_Clock]) -> None:
    api = TestClient(_app(plans, signed_in=False), raise_server_exceptions=False)

    assert api.put(URL, json=BODY).status_code == 401


def test_the_route_is_in_the_openapi_document_once(api: TestClient) -> None:
    paths = api.get("/openapi.json").json()["paths"]

    assert list(paths["/api/v2/coach/plans/{plan_id}/checkins/{milestone}"]) == ["put"]
