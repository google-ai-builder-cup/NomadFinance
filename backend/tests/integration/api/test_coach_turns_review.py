"""NF-FC-020 through the API: the worker's reply at the review moves the interview on or back."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.services.coach.review_reader import ReviewMove
from app.services.coach.session_types import NewMessage, SlotUpdate
from app.services.coach.turn_types import Understanding
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_sessions import NOW
from tests.fixtures.coach_turns import StubExtractor, make_turn_app, make_turns, parse_stream

SESSIONS = "/api/v2/coach/sessions"
UID = "test-user"
KEY = "key-0123456789abcdef"


def world(move: ReviewMove | None) -> tuple[TestClient, str, Any]:
    turns, service, repo, _ = make_turns(extractor=StubExtractor(Understanding(review=move)))
    started = asyncio.run(service.start(UID, "en", restart=False, now=NOW))
    values = load_personas().personas[0].expected_slots.model_dump(mode="json", exclude_none=True)
    asyncio.run(
        service.record_turn(
            UID,
            started.session.id,
            language="en",
            now=NOW + timedelta(minutes=1),
            updates=[SlotUpdate(n, v, 0.95, True) for n, v in values.items()],  # type: ignore[arg-type]
            messages=[NewMessage("user", "that is all", "en")],
        )
    )
    api = TestClient(make_turn_app(turns, service), raise_server_exceptions=False)
    return api, started.session.id, repo


def say(api: TestClient, session_id: str, text: str) -> list[tuple[str, Any]]:
    response = api.post(
        f"{SESSIONS}/{session_id}/messages",
        json={"text": text, "language": "en"},
        headers={"Accept": "text/event-stream", "Idempotency-Key": KEY},
    )
    assert response.status_code == 200, response.text
    return parse_stream(response.text)


def done(events: list[tuple[str, Any]]) -> dict[str, Any]:
    return next(data for name, data in events if name == "done")


def test_a_yes_at_the_review_ends_the_turn_at_the_plan_stage() -> None:
    api, session_id, repo = world(ReviewMove("confirm"))

    finished = done(say(api, session_id, "Yes, that is right"))

    assert finished["stage"] == "plan" and finished["next_slot"] is None
    session = api.get(f"{SESSIONS}/{session_id}").json()
    assert session["stage"] == "plan" and all(s["confirmed"] for s in session["slots"].values())
    assert repo.docs[(UID, session_id)]["stage"] == "plan"


def test_a_wish_to_change_the_pay_goes_back_to_its_question() -> None:
    api, session_id, _ = world(ReviewMove("change", "monthly_salary"))

    finished = done(say(api, session_id, "My pay is wrong"))

    assert finished["stage"] == "income" and finished["next_slot"] == "monthly_salary"
    session = api.get(f"{SESSIONS}/{session_id}").json()
    assert session["slots"]["monthly_salary"]["confirmed"] is False


def test_a_reply_that_moves_nothing_leaves_the_review() -> None:
    api, session_id, _ = world(None)

    finished = done(say(api, session_id, "Why do you ask?"))

    assert finished["stage"] == "review" and finished["next_slot"] is None
