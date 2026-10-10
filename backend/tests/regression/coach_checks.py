"""What a persona's run is held to (NF-FC-024): slots, turn count, band and the plan.

Each function returns the problems it found, as sentences a person can act on, and an empty list
when the run agrees with the persona.
"""

from __future__ import annotations

import math
from typing import Any

from tests.fixtures.coach_personas import Persona

PLAN_WEEKS = 13


def same(expected: Any, got: Any) -> bool:
    """Equal, with money compared to the cent so `650` and `650.0` agree."""
    if isinstance(expected, dict) and isinstance(got, dict):
        return expected.keys() == got.keys() and all(same(expected[k], got[k]) for k in expected)
    numbers = (int, float)
    if isinstance(expected, numbers) and isinstance(got, numbers) and not isinstance(got, bool):
        return math.isclose(float(expected), float(got), rel_tol=0, abs_tol=0.005)
    return bool(expected == got)


def slot_problems(session_slots: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """The stored answers against what the persona states.

    A slot the persona never states (the interest of a debt of zero, a leaving date it does not
    know) must be empty: a value there is one the worker did not give.
    """
    problems: list[str] = []
    for name, want in expected.items():
        record = session_slots.get(name)
        if record is None:
            problems.append(f"slot {name} is empty, expected {want}")
        elif not same(want, record["value"]):
            problems.append(f"slot {name} is {record['value']}, expected {want}")
        elif not record["confirmed"]:
            problems.append(f"slot {name} was never confirmed")
    for name, record in session_slots.items():
        if name not in expected:
            problems.append(
                f"slot {name} was filled with {record['value']}, the persona never states it"
            )
    return problems


def interview_problems(
    session: dict[str, Any], persona: Persona, turn_count: int | None
) -> list[str]:
    """Turn count, where the interview stands and the score band, once the script has been sent."""
    problems: list[str] = []
    if turn_count != persona.expected_turn_count:
        problems.append(f"turn count is {turn_count}, expected {persona.expected_turn_count}")
    if session["stage"] != "plan":
        problems.append(f"the interview ended at stage {session['stage']}, expected plan")
    score = session.get("score")
    if score is None:
        problems.append("no score: the rates or the cost baselines it needs are missing")
    elif score["band"] != persona.expected_score.band:
        problems.append(
            f"band is {score['band']} ({score['total']}), expected {persona.expected_score.band} "
            f"({persona.expected_score.total})"
        )
    return problems


def follow_up_problems(follow_up: str | None, filled: list[dict[str, Any]], say: str) -> list[str]:
    """A message that needs a follow-up must store nothing: the coach asks, it does not guess."""
    if follow_up is None or not filled:
        return []
    slots = ", ".join(str(update["slot"]) for update in filled)
    return [f"{follow_up} was expected for {say!r} but the coach stored {slots}"]


def plan_problems(
    status: int,
    code: str | None,
    body: Any,
    persona: Persona,
    expected: dict[str, Any],
    language: str,
) -> list[str]:
    """The plan answer. A stored plan has already passed the server's figure and sentence checks:
    when they fail twice the route answers 502 `ai_bad_response` and stores nothing."""
    if status not in (200, 201):
        why = " (the plan validator rejected it twice)" if code == "ai_bad_response" else ""
        return [f"plan: HTTP {status} {code}{why}"]
    problems: list[str] = []
    plan = body.get("plan", {})
    if len(plan.get("weeks", [])) != PLAN_WEEKS:
        problems.append(f"plan has {len(plan.get('weeks', []))} weeks, expected {PLAN_WEEKS}")
    if not str(plan.get("disclaimer", "")).strip():
        problems.append("plan has no disclaimer")
    if body.get("language") != language:
        problems.append(f"plan is in {body.get('language')}, expected {language}")
    if body.get("corridor_id") != persona.corridor:
        problems.append(f"plan corridor is {body.get('corridor_id')}, expected {persona.corridor}")
    band = body.get("score", {}).get("band")
    if band != persona.expected_score.band:
        problems.append(f"plan band is {band}, expected {persona.expected_score.band}")
    if not same(expected, body.get("slots", {})):
        problems.append("the plan was made from answers that differ from the persona's")
    return problems
