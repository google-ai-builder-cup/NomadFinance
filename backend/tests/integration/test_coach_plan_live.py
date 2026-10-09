"""Real Gemini, the real prompt: the model words a plan with only the given numbers (NF-FC-012).

Opt-in, like the other live tests: it needs GEMINI_API_KEY in .env.local or the shell and makes
one reasoning-tier call per persona (5 to 15 seconds each in practice):

    RUN_LIVE_GEMINI=1 python -m pytest tests/integration/test_coach_plan_live.py -v -s

PLAN_LIVE_PERSONAS (default: three) names the personas to run, `all` runs the twelve;
LIVE_SPACING_SECONDS pauses after each persona for a free-tier key. The figures are code's; what
is judged here is the model's sentences against `plan_validator.check_text`, and how many calls
(1 or 2) it took.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from app.integrations.gemini import GeminiClient
from app.services.coach.plan_generator import CoachPlanWriter
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_plan_data import persona_context

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
    ),
]

DEFAULT = ("p01_sg_ph_maricel", "p07_my_id_slamet", "p11_au_ph_jenny")
CHOSEN = os.environ.get("PLAN_LIVE_PERSONAS", ",".join(DEFAULT))
# A free-tier key allows only a few reasoning-tier calls a minute: pause after each persona.
SPACING = float(os.environ.get("LIVE_SPACING_SECONDS", "0"))
PERSONAS = [p for p in load_personas().personas if CHOSEN == "all" or p.id in CHOSEN.split(",")]


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
async def test_the_model_words_a_plan_with_only_the_given_numbers(persona: Persona) -> None:
    from app.config import get_settings

    _, _, ctx = await persona_context(persona)
    gemini = GeminiClient(get_settings())
    calls = 0
    real = gemini.generate_structured

    async def counting(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return await real(**kwargs)

    gemini.generate_structured = counting  # type: ignore[method-assign]
    from app.services.coach import plan_generator

    real_check = plan_generator.check_text

    def showing(*args, **kwargs):  # type: ignore[no-untyped-def]
        found = real_check(*args, **kwargs)
        for problem in found:
            print(f"  rejected: {problem}")
        return found

    plan_generator.check_text = showing  # type: ignore[assignment]
    started = time.monotonic()

    try:
        plan = await CoachPlanWriter(gemini).write(ctx)
    finally:
        plan_generator.check_text = real_check  # type: ignore[assignment]

    seconds = time.monotonic() - started
    print(f"\n{persona.id}: {calls} call(s), {seconds:.0f}s, {len(plan.warnings)} warnings")
    print(plan.summary)
    for week in plan.weeks[:2]:
        print(f"  week {week.week}: {week.title} | {' / '.join(week.actions)}")
    for warning in plan.warnings:
        print(f"  [{warning.severity}] {warning.id}: {warning.text}")
    assert len(plan.weeks) == 13
    await asyncio.sleep(SPACING)
