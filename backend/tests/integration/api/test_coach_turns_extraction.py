"""NF-FC-010 through the turn route: the real extractor with a stand-in Gemini.

What the worker says is read, the answers stream before the words, and a gap (a missing money, an
amount out of range) is asked about instead of stored as a guess.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi.testclient import TestClient

from app.integrations.gemini import GeminiUnavailableError
from app.schemas.coach_extraction import SlotExtraction
from app.services.coach.slot_extractor import CoachSlotExtractor
from tests.fixtures.coach_turns import (
    ScriptedStream,
    StubGemini,
    make_turn_app,
    make_turns,
    parse_stream,
)
from tests.integration.api.test_coach_turns import SESSIONS, _post

TODAY = date(2026, 10, 20)


class ReadingGemini(StubGemini):
    """The turn's stub, plus the slot-extraction call: it answers with the readings queued."""

    def __init__(self, *readings: dict[str, Any] | Exception, stream: ScriptedStream | None = None):
        super().__init__(stream)
        self.readings = list(readings)

    async def generate_structured(self, **kwargs: Any) -> SlotExtraction:
        self.calls.append({"call": "generate_structured", **kwargs})
        reading = self.readings.pop(0)
        if isinstance(reading, Exception):
            raise reading
        return SlotExtraction.model_validate(reading)


def world(gemini: ReadingGemini) -> tuple[TestClient, str, Any]:
    extractor = CoachSlotExtractor(gemini, today=lambda: TODAY)  # type: ignore[arg-type]
    turns, service, repo, _ = make_turns(gemini, extractor=extractor)  # type: ignore[arg-type]
    api = TestClient(make_turn_app(turns, service), raise_server_exceptions=False)
    session_id = str(api.post(SESSIONS, json={"language": "en"}).json()["id"])
    return api, session_id, repo


def answer(*candidates: dict[str, Any], kind: str = "answer") -> dict[str, Any]:
    return {"message_kind": kind, "candidates": list(candidates)}


COUNTRY = {
    "slot": "destination_country",
    "evidence": "Singapore",
    "confidence": 0.97,
    "country": "SG",
}


def test_a_stated_answer_streams_before_the_reply_and_moves_the_interview_on() -> None:
    gemini = ReadingGemini(answer(COUNTRY), stream=ScriptedStream(["Thank you. ", "What work?"]))
    api, session_id, _ = world(gemini)

    events = parse_stream(_post(api, session_id, {"text": "Singapore", "language": "en"}).text)

    assert [name for name, _ in events] == ["slot_update", "token", "token", "done"]
    assert events[0][1] == {"slot": "destination_country", "value": "SG", "confirmed": True}
    assert events[-1][1]["next_slot"] == "job_type"
    stored = api.get(f"{SESSIONS}/{session_id}").json()["slots"]
    assert (
        stored["destination_country"]["value"] == "SG"
        and stored["destination_country"]["confirmed"]
    )


def test_a_missing_money_stores_nothing_and_the_reply_asks_for_it() -> None:
    salary = {
        "slot": "monthly_salary",
        "evidence": "168,000 po ang sahod ko kada buwan",
        "confidence": 0.95,
        "money": {"amount": 168000, "currency": "JPY", "period": "month"},
    }
    gemini = ReadingGemini(answer(COUNTRY), answer(salary))
    api, session_id, _ = world(gemini)
    _post(api, session_id, {"text": "Singapore", "language": "en"}, key="key-0123456789abcd01")

    events = parse_stream(
        _post(
            api,
            session_id,
            {"text": "168,000 po ang sahod ko kada buwan.", "language": "tl"},
            key="key-0123456789abcd02",
        ).text
    )

    assert "slot_update" not in [name for name, _ in events]
    asked = gemini.streams()[-1]["message"]
    assert "Which money is that in?" in asked
    assert "monthly_salary" not in api.get(f"{SESSIONS}/{session_id}").json()["slots"]


def test_an_amount_outside_the_usual_range_is_kept_unconfirmed_and_asked_about() -> None:
    fee = {
        "slot": "recruitment_fee_paid",
        "evidence": "800,000 pesos",
        "confidence": 0.95,
        "money": {"amount": 800000, "currency": "PHP", "period": "once"},
    }
    gemini = ReadingGemini(answer(fee))
    api, session_id, repo = world(gemini)
    repo.docs[("test-user", session_id)]["stage"] = "debt"

    events = parse_stream(
        _post(api, session_id, {"text": "Nagbayad ako ng 800,000 pesos.", "language": "tl"}).text
    )

    assert events[0][0] == "slot_update" and events[0][1]["confirmed"] is False
    assert "That amount looks very different" in gemini.streams()[-1]["message"]
    assert events[-1][1]["next_slot"] == "recruitment_fee_paid"


def test_a_gemini_failure_while_reading_is_an_ordinary_error_and_stores_nothing() -> None:
    gemini = ReadingGemini(GeminiUnavailableError("busy"))
    api, session_id, _ = world(gemini)

    response = _post(api, session_id, {"text": "Singapore", "language": "en"})

    assert response.status_code == 503
    assert api.get(f"{SESSIONS}/{session_id}").json()["slots"] == {}


def test_a_retry_with_the_same_key_does_not_read_the_message_again() -> None:
    gemini = ReadingGemini(answer(COUNTRY))
    api, session_id, _ = world(gemini)
    first = _post(api, session_id, {"text": "Singapore", "language": "en"})
    reads = [c for c in gemini.calls if c["call"] == "generate_structured"]

    again = _post(api, session_id, {"text": "Singapore", "language": "en"})

    assert again.headers["Idempotency-Replayed"] == "true" and first.status_code == 200
    assert len(reads) == 1
    assert len([c for c in gemini.calls if c["call"] == "generate_structured"]) == 1
