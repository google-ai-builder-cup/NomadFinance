"""Slot extraction over the 12 personas, with no Gemini (NF-FC-010).

Two kinds of test. The cue rules are held against every persona message, so a persona the rules
could not read fails here and not in a live run. And a model that *invents* an answer for every
slot of every message must still get nothing through: the checks, not the model, are what keep
an unstated value out of the interview.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.schemas.coach_extraction import (
    ExtractedInterest,
    ExtractedMoney,
    SlotCandidate,
    SlotExtraction,
)
from app.services.coach.extraction_checks import ReadingContext, interpret
from app.services.coach.extraction_cues import (
    country_stated,
    currency_stated,
    number_stated,
    period_stated,
)
from tests.fixtures.coach_extraction_sim import BANK, TODAY
from tests.fixtures.coach_personas import load_personas

PERSONAS = load_personas().personas
MONEY_SLOTS = (
    "monthly_salary",
    "remittance_target",
    "recruitment_fee_paid",
    "debt_outstanding",
    "savings",
)
FLOW = ("monthly_salary", "remittance_target")


def _messages() -> list[tuple[str, int, list[str], str, list[str]]]:
    """(persona, index, earlier worker messages newest first, say, fills) for every message."""
    out = []
    for persona in PERSONAS:
        said: list[str] = []
        for index, turn in enumerate(persona.script):
            out.append((persona.id, index, said[::-1][:2], turn.say, turn.fills))
            said.append(turn.say)
    return out


MESSAGES = _messages()


def test_the_cue_rules_find_what_every_persona_says() -> None:
    """The money, the period and the country of each message that fills them are recognised."""
    missed: list[tuple[str, str]] = []
    for persona in PERSONAS:
        expected = persona.expected_slots.model_dump(mode="json", exclude_none=True)
        said: list[str] = []
        for turn in persona.script:
            texts = [turn.say, *said[::-1][:2]]
            for slot in turn.fills:
                value = expected[slot]
                if slot == "destination_country" and not country_stated(value, texts):
                    missed.append((persona.id, turn.say))
                if slot in MONEY_SLOTS:
                    if value["amount"] and not currency_stated(value["currency"], texts):
                        missed.append((persona.id, turn.say))
                    if slot in FLOW and not period_stated(value["period"], texts):
                        missed.append((persona.id, turn.say))
                    if value["amount"] and not number_stated(value["amount"], turn.say):
                        missed.append((persona.id, turn.say))
                if slot == "debt_interest":
                    if not period_stated(value["period"], texts):
                        missed.append((persona.id, turn.say))
                    if not number_stated(value["rate_percent"], turn.say):
                        missed.append((persona.id, turn.say))
            said.append(turn.say)
    assert missed == []


def _invent_everything(message: str, expected: dict[str, Any]) -> SlotExtraction:
    """A model that claims every answer on every message, sure of itself, quoting the message."""
    candidates: list[SlotCandidate] = []
    for slot, value in expected.items():
        fields: dict[str, Any] = {}
        if slot == "destination_country":
            fields["country"] = value
        elif slot == "dependents":
            fields["count"] = value
        elif slot in MONEY_SLOTS:
            fields["money"] = ExtractedMoney(**value)
        elif slot == "debt_interest":
            fields["interest"] = ExtractedInterest(**value)
        elif slot == "departure_date":
            fields["date"] = value
        else:
            continue  # a job or an account kind has no figure or name to check it against
        candidates.append(
            SlotCandidate(slot=slot, evidence=message, confidence=1.0, **fields)  # type: ignore[arg-type]
        )
    return SlotExtraction(message_kind="answer", candidates=candidates)


@pytest.mark.parametrize(
    ("persona_id", "index", "earlier", "say", "fills"),
    MESSAGES,
    ids=[f"{m[0][:3]}-{m[1]:02d}" for m in MESSAGES],
)
def test_a_model_that_invents_every_answer_gets_only_the_stated_ones_through(
    persona_id: str, index: int, earlier: list[str], say: str, fills: list[str]
) -> None:
    persona = next(p for p in PERSONAS if p.id == persona_id)
    expected = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    # Zeros are left out: "no" and "not" are words in every language, so a quoted whole message
    # can always be read as saying "nothing", which only the model's own reading can tell apart.
    claimed = {
        slot: value
        for slot, value in expected.items()
        if not (isinstance(value, dict) and value.get("amount") == 0) and value != 0
    }

    result = interpret(
        _invent_everything(say, claimed),
        ReadingContext(
            bank=BANK, slots={}, declined=[], asking=None, message=say, earlier=earlier, today=TODAY
        ),
    )

    kept = {u.slot for u in result.updates if u.confirmed}
    assert kept <= set(fills), (say, kept - set(fills))


def test_the_replay_of_a_persona_who_gives_no_figure_keeps_nothing() -> None:
    reading = _invent_everything(
        "Yes, that is correct.",
        {"monthly_salary": {"amount": 2400.0, "currency": "SGD", "period": "month"}},
    )

    result = interpret(
        reading,
        ReadingContext(
            bank=BANK,
            slots={},
            declined=[],
            asking=None,
            message="Yes, that is correct.",
            earlier=[],
            today=date(2026, 10, 20),
        ),
    )

    assert [u for u in result.updates if u.confirmed] == []
