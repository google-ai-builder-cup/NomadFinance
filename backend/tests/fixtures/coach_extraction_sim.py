"""Plays a Financial Coach persona's messages through slot extraction (NF-FC-010).

The session is a plain dictionary kept the way `CoachSessions` keeps it: each answer a record
with `confirmed`, the stage settled by the state machine after every turn. Both the live run
(real Gemini) and the replay (recorded answers) use it, so they measure the same thing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.schemas.coach_profile import parse_slot_value
from app.schemas.contract import ReportLanguage
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_document import jsonable
from app.services.coach.session_machine import settle
from app.services.coach.turn_types import Understanding
from tests.fixtures.coach_personas import Persona

# Fixed, so a persona's leaving date is as far from "today" on every run.
TODAY = date(2026, 10, 20)
BANK = load_question_bank()


def prompt_fingerprint() -> str:
    """A hash of the extraction prompt, so a recording says which prompt made it."""
    from app.services.coach.slot_extractor import EXTRACT_PROMPT

    text = EXTRACT_PROMPT.system + "\n---\n" + EXTRACT_PROMPT.user
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class Extractor(Protocol):
    async def extract(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> Understanding: ...


@dataclass
class TurnResult:
    say: str
    expected_fills: list[str]
    expected_follow_up: str | None
    new_confirmed: list[str]
    follow_up: str | None
    declined: list[str]


@dataclass
class PersonaResult:
    persona: str
    slots: dict[str, dict[str, Any]]
    declined: list[str]
    stage: str
    turns: list[TurnResult] = field(default_factory=list)

    def values(self) -> dict[str, Any]:
        return {name: record["value"] for name, record in self.slots.items() if record["confirmed"]}


def _same(expected: Any, got: Any) -> bool:
    if isinstance(expected, dict) and isinstance(got, dict):
        return set(expected) == set(got) and all(_same(expected[k], got[k]) for k in expected)
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(float(expected) - float(got)) < 1e-6
    return bool(expected == got)


def score(result: PersonaResult, persona: Persona) -> dict[str, Any]:
    """Slots right, slots wrong (a value the worker did not state) and follow-ups missed."""
    expected = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    got = result.values()
    right = [n for n, v in expected.items() if n in got and _same(v, got[n])]
    wrong = [n for n, v in got.items() if n not in expected or not _same(expected[n], v)]
    missed = [
        (t.say, t.expected_follow_up, t.follow_up)
        for t in result.turns
        if t.follow_up != t.expected_follow_up
    ]
    return {
        "expected": len(expected),
        "right": len(right),
        "wrong": wrong,
        "not_found": [n for n in expected if n not in right],
        "follow_up_mismatches": missed,
    }


async def run_persona(persona: Persona, extractor: Extractor) -> PersonaResult:
    document: dict[str, Any] = {
        "stage": "intro",
        "slots": {},
        "declined_slots": [],
        "messages": [],
        "language": persona.language,
    }
    result = PersonaResult(persona.id, document["slots"], document["declined_slots"], "intro")
    for turn in persona.script:
        understanding = await extractor.extract(document, turn.say, turn.language)  # type: ignore[arg-type]
        before = {n for n, r in document["slots"].items() if r["confirmed"]}
        for update in understanding.updates:
            value = jsonable(parse_slot_value(update.slot, update.value))
            document["slots"][update.slot] = {
                "value": value,
                "confidence": update.confidence,
                "confirmed": update.confirmed,
            }
        for name in understanding.declined:
            if name not in document["declined_slots"]:
                document["declined_slots"].append(name)
        document["stage"] = settle(
            BANK, document["stage"], document["slots"], document["declined_slots"]
        )
        document["messages"] += [
            {"role": "user", "text": turn.say},
            {"role": "coach", "text": "Next question."},
        ]
        after = {n for n, r in document["slots"].items() if r["confirmed"]}
        result.turns.append(
            TurnResult(
                say=turn.say,
                expected_fills=turn.fills,
                expected_follow_up=turn.coach_follow_up,
                new_confirmed=sorted(after - before),
                follow_up=understanding.clarify.trigger if understanding.clarify else None,
                declined=list(understanding.declined),
            )
        )
    result.stage = document["stage"]
    result.declined = document["declined_slots"]
    return result


class NoReview:
    """Reads nothing at the review step: the persona runs here judge the answers, and what a worker
    says at the review is read by `CoachReviewReader` (tested on its own, NF-FC-020)."""

    async def read(self, document: dict[str, Any], text: str) -> None:
        return None
