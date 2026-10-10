"""The Coach regression runner (NF-FC-024), against a stand-in server that follows the contract.

The first test is the baseline: a faithful server passes all twelve personas. Every later test
breaks the server in one way and shows the runner notices, which is what a regression suite is
for. The real routes are covered in `tests/integration/api/test_coach_regression_routes.py`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from app.schemas.coach_profile import SlotName
from app.services.coach.question_bank import load_question_bank, range_issue
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_regression_server import FakeCoach
from tests.regression.coach_client import CoachApi, SetupError, TurnFailed
from tests.regression.coach_dates import shifted, spellings
from tests.regression.coach_replay import PersonaResult, replay_persona, script_for

pytestmark = pytest.mark.anyio

# Later than every date in the fixture: the case D-203 is about.
TODAY = date(2027, 6, 1)
PERSONAS = load_personas().personas


async def play(
    server: FakeCoach, *, rpm: int = 0, plan_language: str = "en"
) -> list[PersonaResult]:
    api = CoachApi("https://coach.test", "token", rpm=rpm, transport=server.transport())
    try:
        return [await replay_persona(api, p, TODAY, plan_language) for p in server.personas]
    finally:
        await api.aclose()


def one(results: list[PersonaResult], persona_id: str) -> PersonaResult:
    return next(r for r in results if r.persona.id == persona_id)


def problems_of(results: list[PersonaResult]) -> dict[str, list[str]]:
    return {r.persona.id: r.problems for r in results if not r.passed}


async def test_a_faithful_server_passes_all_twelve_personas() -> None:
    results = await play(FakeCoach(PERSONAS, TODAY))

    assert problems_of(results) == {}
    assert len(results) == 12
    assert all(r.turn_count == r.persona.expected_turn_count for r in results)
    assert all(r.plan_ok and r.band == r.persona.expected_score.band for r in results)


async def test_the_runner_types_every_message_in_order_after_the_coach_speaks_first() -> None:
    server = FakeCoach(PERSONAS[:1], TODAY)

    await play(server)

    sent = [(m, p.rsplit("/", 1)[-1], b.get("text")) for m, p, b in server.calls]
    assert sent[0][1] == "sessions" and server.calls[0][2]["restart"] is True
    assert server.calls[1][2] == {"language": PERSONAS[0].language}  # no text: the coach speaks
    typed = [b["text"] for _, p, b in server.calls if p.endswith("/messages") and "text" in b]
    assert typed == script_for(PERSONAS[0], TODAY)[0]


async def test_a_dropped_stream_is_sent_again_with_the_same_key_and_still_passes() -> None:
    server = FakeCoach(PERSONAS[:1], TODAY)
    server.drop_once = {(PERSONAS[0].id, 3)}

    results = await play(server)

    assert problems_of(results) == {}
    assert results[0].retries == 1
    assert len(server.keys) == len(set(server.keys)) + 1  # one key seen twice


async def test_a_wrong_slot_value_fails_that_persona_only() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.edit_session = lambda p, body: (
        body["slots"]["monthly_salary"]["value"].update(amount=6500)
        if p.id == "p01_sg_ph_maricel"
        else None
    )

    results = await play(server)

    assert list(problems_of(results)) == ["p01_sg_ph_maricel"]
    assert "slot monthly_salary is" in problems_of(results)["p01_sg_ph_maricel"][0]


async def test_a_slot_the_persona_never_states_fails() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.edit_session = lambda p, body: (
        body["slots"].update(debt_interest={"value": 0, "confirmed": True, "source": "user"})
        if p.id == "p10_jp_ph_miguel"
        else None
    )

    results = await play(server)

    assert "never states it" in " ".join(one(results, "p10_jp_ph_miguel").problems)


async def test_a_wrong_turn_count_fails() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.extra_turn_for = "p09_jp_ph_mark"

    results = await play(server)

    assert list(problems_of(results)) == ["p09_jp_ph_mark"]
    assert "turn count is 15, expected 14" in problems_of(results)["p09_jp_ph_mark"][0]


async def test_a_wrong_band_fails_and_names_both_bands() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.edit_session = lambda p, body: (
        body["score"].update(band="well_prepared", total=80)
        if p.id == "p05_au_in_gurpreet"
        else None
    )

    results = await play(server)

    (message,) = problems_of(results)["p05_au_in_gurpreet"]
    assert "well_prepared (80), expected getting_ready (75)" in message


async def test_a_message_that_needed_a_follow_up_but_filled_a_slot_fails() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.fill_on_follow_up = True

    results = await play(server)

    assert set(problems_of(results)) == {"p02_sg_ph_jun", "p09_jp_ph_mark"}
    assert "unclear_period was expected" in " ".join(one(results, "p02_sg_ph_jun").problems)


async def test_a_plan_the_validator_refused_fails_with_that_reason() -> None:
    server = FakeCoach(PERSONAS[:1], TODAY)
    server.plan_refusal = (502, "ai_bad_response")

    results = await play(server)

    assert results[0].plan_ok is False
    assert "validator rejected it twice" in results[0].problems[0]


async def test_a_plan_with_the_wrong_number_of_weeks_or_no_disclaimer_fails() -> None:
    server = FakeCoach(PERSONAS[:1], TODAY)

    def break_plan(_: Persona, plan: dict[str, Any]) -> None:
        plan["plan"] = {"weeks": [{"week": 1}], "disclaimer": " "}

    server.edit_plan = break_plan

    results = await play(server)

    assert results[0].problems == ["plan has 1 weeks, expected 13", "plan has no disclaimer"]


async def test_the_plan_is_asked_for_in_the_chosen_language() -> None:
    server = FakeCoach(PERSONAS[:1], TODAY)

    results = await play(server, plan_language="id")

    assert problems_of(results) == {}
    assert [b for _, p, b in server.calls if p.endswith("/plan")] == [{"language": "id"}]


async def test_no_access_stops_the_run_instead_of_failing_twelve_personas() -> None:
    server = FakeCoach(PERSONAS, TODAY)
    server.refuse_sessions = 404

    with pytest.raises(SetupError, match="coach flag"):
        await play(server)


async def test_a_turn_refused_for_good_is_not_retried() -> None:
    api = CoachApi(
        "https://coach.test",
        "token",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(409, json={"code": "session_not_active", "message": "x"})
        ),
    )

    with pytest.raises(TurnFailed, match="session_not_active"):
        await api.turn("s0", "hello", "en")
    await api.aclose()


async def test_a_busy_model_is_waited_for_and_asked_again() -> None:
    answers = iter([503, 503, 200])
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    def handler(_: httpx.Request) -> httpx.Response:
        if (status := next(answers)) == 200:
            done = 'event: done\ndata: {"turn_count": 1, "stage": "intro"}\n\n'
            return httpx.Response(200, content=done.encode())
        return httpx.Response(status, json={"code": "ai_busy"}, headers={"Retry-After": "3"})

    api = CoachApi("https://coach.test", "t", transport=httpx.MockTransport(handler), sleep=sleep)

    turn = await api.turn("s0", "hi", "en")

    assert turn.attempts == 3 and waits == [3.0, 3.0]
    await api.aclose()


async def test_calls_that_spend_gemini_are_spread_over_the_minute() -> None:
    waits: list[float] = []
    now = [0.0]

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    server = FakeCoach(PERSONAS[:1], TODAY)
    api = CoachApi(
        "https://coach.test",
        "t",
        rpm=6,
        transport=server.transport(),
        sleep=sleep,
        clock=lambda: now[0],
    )

    await replay_persona(api, PERSONAS[0], TODAY)

    assert waits and all(w == pytest.approx(10.0) for w in waits)  # 6 a minute is one per 10 s
    await api.aclose()


@pytest.mark.parametrize("persona", PERSONAS, ids=lambda p: p.id)
def test_the_leaving_date_follows_the_day_of_the_run(persona: Persona) -> None:
    bank = load_question_bank()
    stated = persona.expected_slots.departure_date
    original = date.fromisoformat(stated) if stated else None
    for today in (date(2026, 10, 9), TODAY, date(2028, 2, 29)):
        messages, expected = script_for(persona, today)
        if original is None:
            assert "departure_date" not in expected
            continue
        moved = shifted(original, today)
        assert expected["departure_date"] == moved.isoformat()
        assert (messages != [t.say for t in persona.script]) == (moved != original)
        assert any(spelled in " ".join(messages) for spelled in spellings(moved))
        slot: SlotName = "departure_date"
        assert range_issue(bank, slot, expected["departure_date"], today) is None


def test_the_gap_between_personas_is_kept_when_the_dates_move() -> None:
    old = [
        date.fromisoformat(p.expected_slots.departure_date)
        for p in PERSONAS
        if p.expected_slots.departure_date
    ]
    new = [shifted(d, TODAY) for d in old]

    assert [(b - new[0]).days for b in new] == [(a - old[0]).days for a in old]
