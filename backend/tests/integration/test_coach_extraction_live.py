"""Real Gemini, the real prompt: do the 12 personas' words become the right answers (NF-FC-010).

Opt-in, like the other live tests: it needs GEMINI_API_KEY in .env.local or the shell and makes
about 130 calls on the classification tier (a free-tier key needs the pacing below):

    RUN_LIVE_GEMINI=1 python -m pytest tests/integration/test_coach_extraction_live.py -v -s

Each persona's messages (`tests/fixtures/coach_personas.json`) are played in order through
`CoachSlotExtractor`, the session kept as the real one is. Two things are scored, as the tracker
asks: at least 95% of the expected answers end up right, and **no answer is a value the worker did
not state** (an answer that is there and wrong, or there and not expected). The follow-ups the
personas expect (a missing currency, an unclear period, an out-of-range fee) are reported too.

LIVE_SPACING_SECONDS (default 6) is the pause between calls; EXTRACTION_RECORD=path writes the
model's raw readings, the fixture the free replay test (`test_coach_extraction_replay.py`) uses.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.services.coach.slot_extractor import EXTRACT_PROMPT, CoachSlotExtractor
from tests.fixtures.coach_extraction_sim import (
    TODAY,
    NoReview,
    prompt_fingerprint,
    run_persona,
    score,
)
from tests.fixtures.coach_personas import Persona, load_personas

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
    ),
]

PERSONAS = load_personas().personas
SPACING = float(os.environ.get("LIVE_SPACING_SECONDS", "6"))
RECORD = os.environ.get("EXTRACTION_RECORD")


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


class PacedRecordingGemini:
    """The real client, one call at a time and `SPACING` seconds apart; keeps every raw answer."""

    def __init__(self, inner: GeminiClient) -> None:
        self._inner = inner
        self._lock = asyncio.Lock()
        self.recorded: dict[str, list[dict[str, Any]]] = {}
        self.current = ""

    async def generate_structured(self, **kwargs: Any) -> Any:
        async with self._lock:
            result = await self._inner.generate_structured(**kwargs)
            self.recorded.setdefault(self.current, []).append(result.model_dump(mode="json"))
            await asyncio.sleep(SPACING)
            return result


@pytest.fixture(scope="module")
async def gemini() -> AsyncIterator[PacedRecordingGemini]:
    yield PacedRecordingGemini(GeminiClient(get_settings()))


RESULTS: dict[str, dict[str, Any]] = {}


def _show(text: str) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write((text + "\n").encode("utf-8"))
        buffer.flush()
    else:
        print(text.encode("ascii", "backslashreplace").decode())


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
async def test_a_persona_is_read_right(gemini: PacedRecordingGemini, persona: Persona) -> None:
    gemini.current = persona.id
    extractor = CoachSlotExtractor(gemini, today=lambda: TODAY, reviewer=NoReview())  # type: ignore[arg-type]

    result = await run_persona(persona, extractor)
    scored = score(result, persona)
    RESULTS[persona.id] = scored

    _show(
        f"\n{persona.id}: {scored['right']}/{scored['expected']} right, wrong {scored['wrong']}, "
        f"not found {scored['not_found']}, follow-up differences {scored['follow_up_mismatches']}"
    )
    # No value the worker did not state, in any persona, ever.
    assert scored["wrong"] == [], scored


async def test_ninety_five_percent_of_the_answers_are_right_and_none_is_invented(
    gemini: PacedRecordingGemini,
) -> None:
    expected = sum(r["expected"] for r in RESULTS.values())
    right = sum(r["right"] for r in RESULTS.values())
    wrong = {pid: r["wrong"] for pid, r in RESULTS.items() if r["wrong"]}
    differences = {
        pid: r["follow_up_mismatches"] for pid, r in RESULTS.items() if r["follow_up_mismatches"]
    }
    _show(f"\n{right} of {expected} answers right ({right / expected:.1%}); invented: {wrong}")
    _show(f"follow-up differences: {differences}")
    if RECORD:
        recording = {
            "prompt": f"{EXTRACT_PROMPT.key} v{EXTRACT_PROMPT.version}",
            "prompt_sha256": prompt_fingerprint(),
            "model": get_settings().gemini_model_classification,
            "recorded_on": datetime.now(UTC).date().isoformat(),
            "readings": gemini.recorded,
        }
        await asyncio.to_thread(
            Path(RECORD).write_text,
            json.dumps(recording, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    assert len(RESULTS) == len(PERSONAS)
    assert wrong == {}
    assert right / expected >= 0.95
