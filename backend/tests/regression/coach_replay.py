"""Plays one persona through the real routes, from a new session to a stored plan (NF-FC-024)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from tests.fixtures.coach_personas import Persona
from tests.regression import coach_checks as checks
from tests.regression.coach_client import CoachApi, Reply, SetupError, TurnFailed
from tests.regression.coach_dates import shift_text, shifted


@dataclass
class PersonaResult:
    persona: Persona
    problems: list[str] = field(default_factory=list)
    turn_count: int | None = None
    total: int | None = None
    band: str | None = None
    plan_ok: bool = False
    retries: int = 0
    seconds: float = 0.0
    first_token_s: list[float] = field(default_factory=list)
    request_ids: list[str] = field(default_factory=list)
    plan_request_id: str | None = None

    @property
    def passed(self) -> bool:
        return not self.problems


def script_for(persona: Persona, today: date) -> tuple[list[str], dict[str, Any]]:
    """The messages to type and the slots to expect, with the leaving date moved to `today`."""
    expected = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    stated = persona.expected_slots.departure_date
    original = date.fromisoformat(stated) if stated else None
    messages = [turn.say for turn in persona.script]
    if original is not None:
        at = next(i for i, t in enumerate(persona.script) if "departure_date" in t.fills)
        messages[at] = shift_text(messages[at], original, today)
        expected["departure_date"] = shifted(original, today).isoformat()
    return messages, expected


async def _fresh_session(api: CoachApi, persona: Persona) -> str:
    """Start a fresh session and clear what the account already lets the Coach offer.

    An offer (`known`) or a contract on file would change the questions asked, so the turn count
    would no longer be the persona's. The account used for the run should have neither.
    """
    try:
        created = await api.call(
            "POST", "/sessions", body={"language": persona.language, "restart": True}
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        raise SetupError(f"the server cannot be reached: {exc!r}") from exc
    if created.status in (401, 403, 404):
        raise SetupError(
            f"POST /sessions answered {created.status} {created.code}: check the token, the "
            "address, and that the coach flag is on for this account"
        )
    if not created.ok:
        raise TurnFailed(f"the session could not be started: HTTP {created.status} {created.code}")
    session_id = str(created.body["id"])
    if created.body.get("known"):
        cleared = await api.call("POST", f"/sessions/{session_id}/known", body={"keep": []})
        if not cleared.ok:
            raise TurnFailed(f"the offered answers could not be dropped: HTTP {cleared.status}")
    return session_id


async def replay_persona(
    api: CoachApi, persona: Persona, today: date, plan_language: str = "en"
) -> PersonaResult:
    """Run one persona. A problem with the Coach is recorded; a problem with the setup is raised.

    Raises:
        SetupError: The account cannot use the Coach at all (so every persona would fail).
    """
    result = PersonaResult(persona)
    started, first_id, first_retries = time.monotonic(), len(api.request_ids), api.retries
    messages, expected = script_for(persona, today)
    try:
        session_id = await _fresh_session(api, persona)
        opening = await api.turn(session_id, None, persona.language)  # the coach speaks first
        if opening.first_token_s is not None:
            result.first_token_s.append(opening.first_token_s)
        last_count: int | None = None
        for turn, say in zip(persona.script, messages, strict=True):
            sent = await api.turn(session_id, say, turn.language)
            last_count = sent.done["turn_count"] if sent.done else None
            if sent.first_token_s is not None:
                result.first_token_s.append(sent.first_token_s)
            result.problems += checks.follow_up_problems(
                turn.coach_follow_up, sent.slot_updates, say
            )
        session = await api.call("GET", f"/sessions/{session_id}")
        if not session.ok:
            raise TurnFailed(f"the session could not be read: HTTP {session.status} {session.code}")
        result.turn_count = last_count
        result.problems += checks.interview_problems(session.body, persona, last_count)
        result.problems += checks.slot_problems(session.body["slots"], expected)
        score = session.body.get("score") or {}
        result.total, result.band = score.get("total"), score.get("band")
        if session.body["stage"] == "plan":
            await _make_plan(api, session_id, persona, expected, plan_language, result)
    except (TurnFailed, httpx.HTTPError) as exc:
        result.problems.append(
            f"stopped: {exc}" if isinstance(exc, TurnFailed) else f"stopped: {exc!r}"
        )
    result.seconds = time.monotonic() - started
    result.retries = api.retries - first_retries
    result.request_ids = api.request_ids[first_id:]
    return result


async def _make_plan(
    api: CoachApi,
    session_id: str,
    persona: Persona,
    expected: dict[str, Any],
    language: str,
    result: PersonaResult,
) -> None:
    reply: Reply = await api.make_plan(session_id, language)
    result.plan_request_id = reply.request_id
    found = checks.plan_problems(reply.status, reply.code, reply.body, persona, expected, language)
    result.plan_ok = not found
    result.problems += found
