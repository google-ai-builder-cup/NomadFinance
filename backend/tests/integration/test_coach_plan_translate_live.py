"""Real Gemini (Flash-Lite), the real prompt: does a plan translate with every figure intact
(NF-FC-014).

Opt-in, like the other live tests: it needs GEMINI_API_KEY in .env.local or the shell and makes
one call per language:

    RUN_LIVE_GEMINI=1 python -m pytest tests/integration/test_coach_plan_translate_live.py -v -s

The plan is persona 1's (a worker with a costly debt, so there are warnings), worded by the
offline stand-in. PLAN_PDF_DIR=path keeps each language's PDF there to look at;
LIVE_SPACING_SECONDS pauses between languages for a free-tier key.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.schemas.coach_plan import CoachPlanResponse
from app.services.coach import plan_translator
from app.services.coach.plan_document import build_document, to_response
from app.services.coach.plan_generator import CoachPlanWriter
from app.services.coach.plan_pdf import render_plan_pdf
from app.services.coach.plan_translation_check import narrative_of, same_figures
from app.services.coach.plan_translator import CoachPlanTranslator
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import WritingGemini, persona_context

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_GEMINI") != "1", reason="live Gemini test; set RUN_LIVE_GEMINI=1"
    ),
]

LANGUAGES = ("hi", "tl", "id", "ne", "bn")
SPACING = float(os.environ.get("LIVE_SPACING_SECONDS", "0"))
PDF_DIR = os.environ.get("PLAN_PDF_DIR")


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"


async def english_plan() -> CoachPlanResponse:
    from datetime import UTC, datetime

    persona = load_personas().personas[0]
    _, _, ctx = await persona_context(persona)
    plan = await CoachPlanWriter(WritingGemini()).write(ctx)  # type: ignore[arg-type]
    now = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)
    document = build_document(
        profile=persona.expected_slots,
        session_id="s",
        home_country="PH",
        corridor_id="SG-PH",
        score=ctx.score,
        plan=plan,
        grounding={},
        rates_as_of=now,
        models={},
        prompt_versions={},
        now=now,
    )
    return to_response(document["slot_hash"][:20], document, session_id="s")


def save(language: str, data: bytes) -> None:
    Path(PDF_DIR or ".").mkdir(parents=True, exist_ok=True)
    (Path(PDF_DIR or ".") / f"plan-{language}.pdf").write_bytes(data)


async def translate_one(gemini: GeminiClient, english: CoachPlanResponse, language: str) -> None:
    calls = 0
    real = gemini.generate_structured

    async def counting(**kwargs):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return await real(**kwargs)

    gemini.generate_structured = counting  # type: ignore[method-assign]
    real_check = plan_translator.check_translation

    def showing(*args, **kwargs):  # type: ignore[no-untyped-def]
        found = real_check(*args, **kwargs)
        for problem in found:
            print(f"  rejected: {problem}")
        return found

    plan_translator.check_translation = showing  # type: ignore[assignment]
    try:
        translated = await CoachPlanTranslator(gemini).translate(english.plan, language)  # type: ignore[arg-type]
    finally:
        plan_translator.check_translation = real_check  # type: ignore[assignment]
        gemini.generate_structured = real  # type: ignore[method-assign]

    assert same_figures(english.plan, translated), language
    assert narrative_of(translated) != narrative_of(english.plan), language
    print(f"\n{language}: {calls} call(s)")
    print(translated.summary)
    if translated.warnings:
        print(translated.warnings[0].text)
    if PDF_DIR:
        response = english.model_copy(
            update={
                "language": language,
                "plan": translated,
                "available_languages": ["en", language],
            }
        )
        await asyncio.to_thread(save, language, render_plan_pdf(response))


async def test_the_plan_translates_into_every_language_with_every_figure_intact() -> None:
    english = await english_plan()
    gemini = GeminiClient(get_settings())
    for language in LANGUAGES:
        await translate_one(gemini, english, language)
        await asyncio.sleep(SPACING)
