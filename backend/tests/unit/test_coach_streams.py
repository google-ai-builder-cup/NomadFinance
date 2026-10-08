"""The streams in docs/mocks/coach/ follow the event rules of the conventions (section 4).

Each `.sse` file is the raw body of a turn. They are written to the contract, not captured, so
this is what keeps them honest: the events are the four there are, the data fits its model, a
stream ends once and with the right event, and the review stream is the review session's last
message.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import BaseModel

from app.schemas.coach_session import CoachDoneEvent, CoachSlotUpdateEvent, CoachTokenEvent
from app.schemas.errors import ErrorEnvelope
from app.services.coach.question_bank import load_question_bank
from tests.fixtures.coach_mocks import MOCKS, SSE_FILES, sessions_by_id, stream_events


@pytest.mark.parametrize("path", SSE_FILES, ids=lambda path: path.name)
def test_a_stream_follows_the_event_rules_and_its_data_fits_the_models(path: Path) -> None:
    events = stream_events(path)
    names = [name for name, _ in events]
    models: dict[str, type[BaseModel]] = {
        "token": CoachTokenEvent,
        "slot_update": CoachSlotUpdateEvent,
        "done": CoachDoneEvent,
        "error": ErrorEnvelope,
    }

    assert set(names) <= set(models)
    for name, data in events:
        assert models[name].model_validate(data).model_dump(exclude_unset=True) == data
    if path.name == "turn-error-dropped.sse":
        # A connection that dropped: no terminal event, so the client must retry (conventions, 4).
        assert "done" not in names and "error" not in names
        return
    terminal = "error" if path.name.startswith("turn-error-") else "done"
    assert names[-1] == terminal
    assert names.count("done") + names.count("error") == 1
    assert "token" in names


@pytest.mark.parametrize(
    "path", [p for p in SSE_FILES if not p.name.startswith("turn-error-")], ids=lambda p: p.name
)
def test_the_stage_of_a_done_event_is_the_stage_of_its_next_question(path: Path) -> None:
    done = CoachDoneEvent.model_validate(stream_events(path)[-1][1])

    if done.next_slot is not None:
        assert load_question_bank().question(done.next_slot).stage == done.stage


def test_the_review_stream_is_the_last_message_of_the_review_session() -> None:
    session = sessions_by_id()["s_03"]
    events = stream_events(MOCKS / "turn-05-review.sse")
    text = "".join(data["text"] for name, data in events if name == "token")
    done = events[-1][1]
    update = next(data for name, data in events if name == "slot_update")

    assert text == session["messages"][-1]["text"]
    assert done["message_id"] == session["messages"][-1]["id"]
    assert (done["stage"], done["turn_count"]) == (session["stage"], session["turn_count"])
    assert update["value"] == session["slots"][update["slot"]]["value"]


def test_the_late_slot_update_stream_sends_the_fact_after_the_words() -> None:
    names = [name for name, _ in stream_events(MOCKS / "turn-06-late-slot-update.sse")]

    assert names.index("slot_update") > names.index("token")
    assert [name for name, _ in stream_events(MOCKS / "turn-02-answer.sse")][0] == "slot_update"


def test_a_stream_may_be_slow_to_start() -> None:
    text = (MOCKS / "turn-02-answer.sse").read_text(encoding="utf-8")

    assert "\n: ping\n\n" in text
