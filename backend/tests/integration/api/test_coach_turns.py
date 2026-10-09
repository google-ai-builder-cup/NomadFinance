"""NF-FC-009 through the API: the stream, its headers, retries and every refusal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.integrations.gemini import GeminiTimeoutError, GeminiUnavailableError
from app.schemas.coach_session import CoachDoneEvent, CoachTokenEvent
from app.schemas.errors import ErrorEnvelope
from app.services.coach.session_types import SlotUpdate
from app.services.coach.turn_types import Understanding
from tests.fixtures.coach_mocks import MOCKS, stream_events
from tests.fixtures.coach_turns import (
    OPENING,
    ScriptedStream,
    StubExtractor,
    StubGemini,
    make_turn_app,
    make_turns,
    parse_stream,
    reply_text,
)

SESSIONS = "/api/v2/coach/sessions"
UID = "test-user"
KEY = "key-0123456789abcdef"


class World:
    """An app with its fake Gemini and storage in reach, and a session already started."""

    def __init__(self, gemini: StubGemini | None = None, extractor: StubExtractor | None = None):
        self.turns, self.service, self.repo, self.gemini = make_turns(gemini, extractor)

    def client(self, **options: Any) -> TestClient:
        app = make_turn_app(self.turns, self.service, **options)
        return TestClient(app, raise_server_exceptions=False)

    def start(self, api: TestClient, language: str = "en") -> str:
        return str(api.post(SESSIONS, json={"language": language}).json()["id"])


def _post(api: TestClient, session_id: str, body: dict[str, Any], key: str | None = KEY) -> Any:
    headers = {"Accept": "text/event-stream"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return api.post(f"{SESSIONS}/{session_id}/messages", json=body, headers=headers)


def _envelope(response: Any, status: int, code: str) -> ErrorEnvelope:
    assert response.status_code == status, response.text
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == code and envelope.request_id == response.headers["X-Request-ID"]
    return envelope


def test_the_coach_speaks_first_as_an_event_stream_with_the_headers_of_the_conventions() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)

    response = _post(api, session_id, {"language": "en"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["x-request-id"] and "idempotency-replayed" not in response.headers
    events = parse_stream(response.text)
    assert [name for name, _ in events] == ["token", "token", "done"]
    assert reply_text(events) == "".join(OPENING)
    for name, data in events:
        model = CoachTokenEvent if name == "token" else CoachDoneEvent
        assert model.model_validate(data).model_dump() == data


def test_the_events_have_the_shape_of_the_sample_stream() -> None:
    world = World()
    api = world.client()
    events = parse_stream(_post(api, world.start(api), {"language": "en"}).text)
    sample = stream_events(MOCKS / "turn-01-start.sse")

    assert events[-1][0] == sample[-1][0] == "done"
    assert set(events[-1][1]) == set(sample[-1][1])
    assert events[-1][1]["stage"] == sample[-1][1]["stage"]
    assert events[-1][1]["next_slot"] == sample[-1][1]["next_slot"]


def test_an_answer_streams_the_fact_before_the_words_and_the_next_question_follows() -> None:
    update = SlotUpdate("destination_country", "AU", 1.0, True)
    world = World(
        StubGemini(ScriptedStream(["Australia, thank you. ", "What work will you do?"])),
        StubExtractor(Understanding(updates=[update])),
    )
    api = world.client()
    session_id = world.start(api)

    events = parse_stream(_post(api, session_id, {"text": "Australia", "language": "en"}).text)

    assert [name for name, _ in events] == ["slot_update", "token", "token", "done"]
    assert events[-1][1]["next_slot"] == "job_type" and events[-1][1]["turn_count"] == 1
    session = api.get(f"{SESSIONS}/{session_id}").json()
    assert session["slots"]["destination_country"]["value"] == "AU"
    assert [m["role"] for m in session["messages"]] == ["user", "coach"]
    assert session["turn_count"] == 1 and session["language"] == "en"


def test_a_retry_with_the_same_key_replays_the_turn_and_runs_nothing() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    first = _post(api, session_id, {"language": "en"})
    calls = len(world.gemini.calls)

    again = _post(api, session_id, {"language": "en"})

    assert again.status_code == 200 and again.headers["Idempotency-Replayed"] == "true"
    assert reply_text(parse_stream(again.text)) == reply_text(parse_stream(first.text))
    assert parse_stream(again.text)[-1] == parse_stream(first.text)[-1]
    assert len(world.gemini.calls) == calls
    assert again.headers["x-request-id"] != first.headers["x-request-id"]
    assert len(api.get(f"{SESSIONS}/{session_id}").json()["messages"]) == 1


def test_the_same_key_with_another_body_is_a_422() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    _post(api, session_id, {"language": "en"})

    response = _post(api, session_id, {"text": "something else", "language": "en"})

    _envelope(response, 422, "idempotency_key_reused")


@pytest.mark.parametrize("key", [None, "short", "has spaces 0123456789", "x" * 65])
def test_a_missing_or_malformed_key_is_a_400_before_anything_runs(key: str | None) -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)

    response = _post(api, session_id, {"language": "en"}, key=key)

    _envelope(response, 400, "idempotency_key_invalid")
    assert world.gemini.calls == []


def test_the_text_is_trimmed_and_must_be_one_to_a_thousand_characters() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)

    for body in (
        {"text": "   ", "language": "en"},
        {"text": "x" * 1001, "language": "en"},
        {"language": "fr"},
        {"text": "hi"},
    ):
        _envelope(_post(api, session_id, body), 422, "validation_failed")
    assert world.gemini.calls == []
    ok = _post(api, session_id, {"text": "x" * 1000, "language": "en"})
    assert ok.status_code == 200


def test_the_coach_may_not_speak_again_without_text_unless_the_language_changed() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    _post(api, session_id, {"language": "en"})

    envelope = _envelope(
        _post(api, session_id, {"language": "en"}, key="key-second-0123456789"),
        422,
        "validation_failed",
    )
    assert envelope.details is not None and envelope.details[0].field == "body.text"
    switched = _post(api, session_id, {"language": "hi"}, key="key-third-0123456789")
    assert switched.status_code == 200
    assert api.get(f"{SESSIONS}/{session_id}").json()["language"] == "hi"


def test_a_session_that_is_not_the_callers_or_does_not_exist_is_the_same_404() -> None:
    world = World()
    mine = world.client(uid="alice")
    other = world.client(uid="bob")
    session_id = world.start(mine)

    stranger = _post(other, session_id, {"language": "en"})
    missing = _post(other, "s_99", {"language": "en"})
    odd = _post(other, "__bad__", {"language": "en"})

    assert {stranger.status_code, missing.status_code, odd.status_code} == {404}
    assert stranger.json()["code"] == missing.json()["code"] == "not_found"
    assert world.gemini.calls == []


def test_without_a_token_it_is_a_401_and_with_the_flag_off_the_404_of_an_unknown_path() -> None:
    world = World()
    session_id = world.start(world.client())

    _envelope(
        _post(world.client(signed_in=False), session_id, {"language": "en"}), 401, "unauthenticated"
    )
    _envelope(_post(world.client(flag_on=False), session_id, {"language": "en"}), 404, "not_found")
    assert world.gemini.calls == []


def test_a_finished_session_takes_no_turns() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    world.repo.docs[(UID, session_id)]["status"] = "abandoned"

    _envelope(_post(api, session_id, {"language": "en"}), 409, "session_not_active")


def test_a_full_transcript_is_a_409() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    world.repo.docs[(UID, session_id)]["messages"] = [
        {
            "id": f"m{i:03d}-u",
            "role": "user",
            "text": "x",
            "language": "en",
            "at": datetime.now(UTC),
        }
        for i in range(199)
    ]

    _envelope(_post(api, session_id, {"text": "Japan", "language": "en"}), 409, "session_full")


def _running(world: World, session_id: str, key: str, body: dict[str, Any]) -> None:
    from app.schemas.coach_session import CoachTurnRequest
    from app.services.coach.turn_replay import body_hash

    world.repo.docs[(UID, session_id)]["last_turn"] = {
        "key": key,
        "body_hash": body_hash(CoachTurnRequest.model_validate(body)),
        "state": "running",
        "started_at": datetime.now(UTC) - timedelta(seconds=5),
        "turn": 0,
    }


def test_a_turn_still_running_is_a_409_with_retry_after_for_its_own_key_and_for_another() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    body = {"language": "en"}
    _running(world, session_id, KEY, body)

    same = _post(api, session_id, body)
    other = _post(api, session_id, body, key="other-key-0123456789")

    _envelope(same, 409, "request_in_progress")
    _envelope(other, 409, "turn_in_progress")
    assert same.headers["Retry-After"] == other.headers["Retry-After"] == "2"
    assert world.gemini.calls == []


def test_a_turn_running_for_over_ninety_seconds_does_not_lock_the_session() -> None:
    world = World()
    api = world.client()
    session_id = world.start(api)
    _running(world, session_id, "other-key-0123456789", {"language": "en"})
    world.repo.docs[(UID, session_id)]["last_turn"]["started_at"] = datetime.now(UTC) - timedelta(
        seconds=120
    )

    assert _post(api, session_id, {"language": "en"}).status_code == 200


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (GeminiUnavailableError("down"), 503, "ai_unavailable"),
        (GeminiTimeoutError("slow"), 504, "ai_timeout"),
    ],
)
def test_a_gemini_failure_before_the_first_piece_is_an_ordinary_http_error(
    error: Exception, status: int, code: str
) -> None:
    stub = StubGemini()
    stub.open_error = error
    world = World(stub)
    api = world.client()
    session_id = world.start(api)

    _envelope(_post(api, session_id, {"language": "en"}), status, code)

    assert api.get(f"{SESSIONS}/{session_id}").json()["messages"] == []
    stub.open_error = None
    assert _post(api, session_id, {"language": "en"}).status_code == 200  # the same key may retry


def test_a_failure_after_the_stream_began_is_an_error_event_in_a_200() -> None:
    stream = ScriptedStream(["Half of "], error=GeminiUnavailableError("dropped"))
    world = World(StubGemini(stream))
    api = world.client()
    session_id = world.start(api)

    response = _post(api, session_id, {"language": "en"})

    assert response.status_code == 200
    events = parse_stream(response.text)
    assert [name for name, _ in events] == ["token", "error"]
    error = ErrorEnvelope.model_validate(events[-1][1])
    assert error.code == "ai_unavailable" and error.request_id == response.headers["x-request-id"]
    assert api.get(f"{SESSIONS}/{session_id}").json()["messages"] == []


def test_the_route_is_held_to_the_gemini_budget_of_ten_a_minute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AI", "2/minute")
    get_settings.cache_clear()
    try:
        world = World()
        api = world.client()
        session_id = world.start(api)
        codes = [
            _post(api, session_id, {"language": "en"}, key=f"key-{n}-0123456789abcdef").status_code
            for n in range(3)
        ]
        refused = _post(api, session_id, {"language": "en"}, key="key-9-0123456789abcdef")
    finally:
        get_settings.cache_clear()

    assert codes[:2] == [200, 422] and codes[2] == 429
    assert refused.status_code == 429 and int(refused.headers["retry-after"]) >= 1
    assert refused.json()["code"] == "rate_limited"
