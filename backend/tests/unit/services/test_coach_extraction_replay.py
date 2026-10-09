"""The 12 personas through slot extraction, from recorded model answers (NF-FC-010).

`tests/fixtures/coach_extraction_recordings.json` holds what the real model returned for every
message of every persona, from `tests/integration/test_coach_extraction_live.py`. Replaying it
runs the whole extractor (the prompt's inputs, the checks, the state machine) in CI with no
Gemini, and holds it to the tracker's acceptance: at least 95% of the answers right and none
invented. When the prompt changes the recording is stale and these tests say so: record again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.coach_extraction import SlotExtraction
from app.services.coach.slot_extractor import EXTRACT_PROMPT, CoachSlotExtractor
from tests.fixtures.coach_extraction_sim import TODAY, prompt_fingerprint, run_persona, score
from tests.fixtures.coach_personas import load_personas

pytestmark = pytest.mark.anyio

RECORDING = Path(__file__).resolve().parents[2] / "fixtures" / "coach_extraction_recordings.json"
PERSONAS = load_personas().personas


def _recording() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(RECORDING.read_text(encoding="utf-8"))
    return data


class ReplayGemini:
    """Answers each persona's extraction calls with the recorded readings, in order."""

    def __init__(self, readings: dict[str, list[dict[str, Any]]]) -> None:
        self._left = {pid: list(items) for pid, items in readings.items()}
        self.current = ""

    async def generate_structured(self, **kwargs: Any) -> SlotExtraction:
        assert kwargs["operation"] == EXTRACT_PROMPT.key
        return SlotExtraction.model_validate(self._left[self.current].pop(0))


def test_the_recording_was_made_with_this_prompt() -> None:
    recording = _recording()

    assert recording["prompt"] == f"{EXTRACT_PROMPT.key} v{EXTRACT_PROMPT.version}"
    assert recording["prompt_sha256"] == prompt_fingerprint(), (
        "the extraction prompt changed since the recording: run the live test with "
        "EXTRACTION_RECORD=backend/tests/fixtures/coach_extraction_recordings.json"
    )


def test_every_persona_has_exactly_the_readings_its_messages_need() -> None:
    readings = _recording()["readings"]

    assert set(readings) == {p.id for p in PERSONAS}
    for persona in PERSONAS:
        asked = persona.expected_turn_count - 1  # the message at the review is not read
        assert len(readings[persona.id]) == asked, persona.id


@pytest.fixture(scope="module")
async def results() -> dict[str, dict[str, Any]]:
    gemini = ReplayGemini(_recording()["readings"])
    extractor = CoachSlotExtractor(gemini, today=lambda: TODAY)  # type: ignore[arg-type]
    scored: dict[str, dict[str, Any]] = {}
    for persona in PERSONAS:
        gemini.current = persona.id
        scored[persona.id] = score(await run_persona(persona, extractor), persona)
    return scored


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


async def test_at_least_ninety_five_percent_of_the_answers_are_right(
    results: dict[str, dict[str, Any]],
) -> None:
    expected = sum(r["expected"] for r in results.values())
    right = sum(r["right"] for r in results.values())

    assert expected == 128
    assert right / expected >= 0.95, {
        p: r["not_found"] for p, r in results.items() if r["not_found"]
    }


async def test_no_answer_is_a_value_the_worker_did_not_state(
    results: dict[str, dict[str, Any]],
) -> None:
    assert {p: r["wrong"] for p, r in results.items() if r["wrong"]} == {}


async def test_the_follow_ups_the_personas_expect_are_the_ones_asked(
    results: dict[str, dict[str, Any]],
) -> None:
    assert {
        p: r["follow_up_mismatches"] for p, r in results.items() if r["follow_up_mismatches"]
    } == {}
