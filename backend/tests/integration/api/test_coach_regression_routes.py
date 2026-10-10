"""The regression runner against the real Coach routes (NF-FC-024), with Gemini replaced.

The unit tests use a stand-in server that follows the contract. This one runs the same client
and checks against the application's own routes, so a route that does not behave as the runner
expects (the restart, the stream format, the fields it reads from a session) fails here.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.core.rate_limit import reset_rate_limits
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_turns import StubGemini, make_turn_app, make_turns
from tests.regression.coach_client import CoachApi, SetupError
from tests.regression.coach_replay import replay_persona

pytestmark = pytest.mark.anyio

PERSONA = load_personas().personas[0]
TODAY = date(2026, 10, 20)


async def _no_wait(_: float) -> None:
    # The turn limit is 10 a minute; letting "time pass" is clearing the counter.
    reset_rate_limits()


def _api(*, flag_on: bool = True) -> CoachApi:
    turns, service, _, _ = make_turns(StubGemini())
    app = make_turn_app(turns, service, flag_on=flag_on)
    transport = httpx.ASGITransport(app=app)
    return CoachApi("http://testserver", "token", transport=transport, sleep=_no_wait)


async def test_the_runner_drives_the_real_routes_from_a_new_session_to_the_last_message() -> None:
    api = _api()

    result = await replay_persona(api, PERSONA, TODAY)

    # No extractor reads the answers here, so the interview cannot finish and its slots stay
    # empty. What this shows is that every call the runner makes is understood by the routes.
    assert not [p for p in result.problems if p.startswith("stopped")]
    assert result.turn_count == PERSONA.expected_turn_count
    assert any("ended at stage intro" in p for p in result.problems)
    assert result.first_token_s and len(set(result.request_ids)) == len(result.request_ids)
    await api.aclose()


async def test_asking_for_a_restart_gives_a_new_session_each_time() -> None:
    api = _api()

    first = await api.call("POST", "/sessions", body={"language": "en", "restart": True})
    second = await api.call("POST", "/sessions", body={"language": "en", "restart": True})

    assert first.status == 201 and second.status == 201
    assert first.body["id"] != second.body["id"]
    await api.aclose()


async def test_an_account_without_the_coach_stops_the_run() -> None:
    api = _api(flag_on=False)

    with pytest.raises(SetupError, match="coach flag"):
        await replay_persona(api, PERSONA, TODAY)
    await api.aclose()
