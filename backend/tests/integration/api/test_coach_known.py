"""NF-FC-023 through the API: the offer in the session, and `POST /sessions/{id}/known`."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.schemas.coach_session import CoachSession, CoachSessionCreateResponse
from app.schemas.errors import ErrorEnvelope
from app.services.coach.known_details import Item, collect_known
from app.services.coach.prefill import Prefill
from tests.fixtures.coach_sessions import FakeSessionRepo, make_coach_app, make_sessions
from tests.unit.services.test_coach_known_details import TODAY, salary, saved, sent

SESSIONS = "/api/v2/coach/sessions"


def _offer() -> dict[str, Item]:
    return collect_known(
        profile={"host_country": "SG", "job_type": "domestic_worker"},
        contract=None,
        income=[salary()],
        savings=[saved(1200, account_type="bank")],
        transfers=[sent(500, "2026-09-26")],
        today=TODAY,
    )


def _client(
    offer: dict[str, Item] | None = None, repo: FakeSessionRepo | None = None, **options: Any
) -> tuple[TestClient, FakeSessionRepo]:
    service, repo, _ = make_sessions(repo)

    async def find(uid: str, contract: Prefill | None) -> dict[str, Item]:
        return _offer() if offer is None else offer

    service._known = find  # noqa: SLF001
    return TestClient(make_coach_app(service, **options), raise_server_exceptions=False), repo


def _start(api: TestClient) -> dict[str, Any]:
    body: dict[str, Any] = api.post(SESSIONS, json={"language": "en"}).json()
    return body


def test_a_new_session_carries_the_offer_with_each_answers_source_and_date() -> None:
    api, _ = _client()

    body = _start(api)

    created = CoachSessionCreateResponse.model_validate(body)
    assert created.known is not None
    first = body["known"]["items"][0]
    assert first == {
        "slot": "destination_country",
        "value": "SG",
        "source": "profile",
        "as_of": None,
    }
    pay = next(item for item in body["known"]["items"] if item["slot"] == "monthly_salary")
    assert pay["source"] == "income" and pay["as_of"] == "2026-09-25"
    # Not an answer yet: nothing is stored, and the next question is still the first one.
    assert body["slots"] == {} and body["next_slot"] == "destination_country"


def test_the_read_shows_the_same_offer_until_the_worker_answers() -> None:
    api, _ = _client()
    session = _start(api)

    got = api.get(f"{SESSIONS}/{session['id']}").json()

    assert got["known"] == session["known"]
    CoachSession.model_validate(got)


def test_a_session_with_nothing_known_has_no_known_field_at_all() -> None:
    api, _ = _client({})

    body = _start(api)

    assert "known" not in body


def test_keeping_some_answers_stores_them_and_the_offer_leaves_the_answer() -> None:
    api, repo = _client()
    session = _start(api)

    response = api.post(
        f"{SESSIONS}/{session['id']}/known", json={"keep": ["destination_country", "savings"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert "known" not in body
    assert set(body["slots"]) == {"destination_country", "savings"}
    assert body["slots"]["savings"] == {
        "value": {"amount": 1200.0, "currency": "SGD", "period": "once"},
        "confirmed": True,
        "source": "identity_prefill",
    }
    assert body["next_slot"] == "job_type"
    CoachSession.model_validate(body)
    assert api.get(f"{SESSIONS}/{session['id']}").json() == body
    assert len(repo.docs) == 1


def test_keeping_nothing_is_a_200_and_everything_is_asked() -> None:
    api, _ = _client()
    session = _start(api)

    body = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": []}).json()

    assert body["slots"] == {} and body["next_slot"] == "destination_country"


def test_a_second_request_after_answering_changes_nothing() -> None:
    api, _ = _client()
    session = _start(api)
    first = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": ["job_type"]}).json()

    second = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": ["savings"]})

    assert second.status_code == 200 and second.json() == first


def test_a_slot_that_was_not_offered_is_a_422_in_the_standard_envelope() -> None:
    api, _ = _client({"destination_country": _offer()["destination_country"]})
    session = _start(api)

    response = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": ["savings"]})

    assert response.status_code == 422
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == "validation_failed" and envelope.details


def test_a_name_that_is_not_a_slot_or_a_missing_list_is_a_422() -> None:
    api, _ = _client()
    session = _start(api)

    for body in ({"keep": ["salary"]}, {}, {"keep": "job_type"}):
        response = api.post(f"{SESSIONS}/{session['id']}/known", json=body)
        assert response.status_code == 422, body


def test_an_ended_session_is_a_409_session_not_active() -> None:
    api, repo = _client()
    session = _start(api)
    repo.docs[("test-user", session["id"])]["status"] = "abandoned"

    response = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": []})

    assert response.status_code == 409 and response.json()["code"] == "session_not_active"


def test_another_workers_session_and_a_made_up_id_are_the_same_404() -> None:
    mine, repo = _client(uid="alice")
    session = _start(mine)
    other, _ = _client(repo=repo, uid="bob")

    stranger = other.post(f"{SESSIONS}/{session['id']}/known", json={"keep": []})
    missing = other.post(f"{SESSIONS}/s_99/known", json={"keep": []})
    odd = other.post(f"{SESSIONS}/__bad__/known", json={"keep": []})

    assert stranger.status_code == missing.status_code == odd.status_code == 404
    assert stranger.json()["code"] == missing.json()["code"] == "not_found"


def test_two_requests_at_once_give_a_409_that_says_to_retry() -> None:
    api, repo = _client()
    session = _start(api)
    repo.stale_next_write = True

    response = api.post(f"{SESSIONS}/{session['id']}/known", json={"keep": ["job_type"]})

    assert response.status_code == 409 and response.json()["code"] == "request_in_progress"
    assert response.headers["Retry-After"] == "2"


def test_it_needs_a_sign_in_and_the_coach_flag_like_every_route() -> None:
    signed_out, _ = _client(signed_in=False)
    flag_off, _ = _client(flag_on=False)

    assert signed_out.post(f"{SESSIONS}/s_01/known", json={"keep": []}).status_code == 401
    assert flag_off.post(f"{SESSIONS}/s_01/known", json={"keep": []}).status_code == 404
