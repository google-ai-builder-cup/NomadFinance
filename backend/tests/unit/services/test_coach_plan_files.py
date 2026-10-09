"""The plan in another language and as a PDF, through the service (NF-FC-014)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from app.integrations.gemini import GeminiUnavailableError
from app.schemas.coach_plan import CoachPlan
from app.services.coach import plan_files
from app.services.coach.plan_service import PlanNotFoundError
from app.services.coach.plan_translation_check import same_figures
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import (
    UID,
    FakeExportStore,
    TranslatingGemini,
    make_plans,
    reach_plan_stage,
)
from tests.fixtures.coach_sessions import NOW

pytestmark = pytest.mark.anyio

PERSONAS = load_personas().personas
MARICEL = PERSONAS[0]
LATER = NOW + timedelta(minutes=10)
LANGUAGES = ("hi", "tl", "id", "ne", "bn")


async def ready(persona=MARICEL, **options):  # type: ignore[no-untyped-def]
    plans, service, session_repo, plan_repo, gemini = make_plans(persona, **options)
    session_id = await reach_plan_stage(service, persona)
    return plans, plan_repo, gemini, session_id


async def test_a_new_plan_can_be_made_in_a_language_and_the_english_stays_stored() -> None:
    translator = TranslatingGemini()
    plans, plan_repo, _, session_id = await ready(translator=translator)

    result = await plans.create(UID, session_id, "hi", LATER)

    assert result.created and result.response.language == "hi"
    assert result.response.plan.summary.startswith("[Hindi]")
    assert result.response.available_languages == ["en", "hi"]
    stored = plan_repo.get(UID, result.response.id)
    assert not stored["plan"]["summary"].startswith("[")  # the parent plan is English
    saved = plan_repo.get_translation(UID, result.response.id, "hi")
    assert saved["language"] == "hi" and saved["prompt_version"] == 1 and saved["model"]
    assert saved["schema_version"] == 1 and saved["created_at"] == LATER
    assert len(translator.calls) == 1


async def test_a_language_is_translated_once_and_then_read_from_storage() -> None:
    translator = TranslatingGemini()
    plans, _, _, session_id = await ready(translator=translator)
    created = await plans.create(UID, session_id, "en", LATER)
    spent: list[int] = []

    async def spend() -> None:
        spent.append(1)

    first = await plans.get(UID, created.response.id, LATER, "tl", spend)
    again = await plans.get(UID, created.response.id, LATER, "tl", spend)
    english = await plans.get(UID, created.response.id, LATER, "en", spend)

    assert first.plan == again.plan and first.available_languages == ["en", "tl"]
    assert len(translator.calls) == 1 and spent == [1]  # the Gemini budget is spent once
    assert english.plan.summary == created.response.plan.summary
    assert english.available_languages == ["en", "tl"]


async def test_asking_again_in_a_new_language_is_200_and_translates_now() -> None:
    translator = TranslatingGemini()
    plans, _, _, session_id = await ready(translator=translator)
    await plans.create(UID, session_id, "en", LATER)

    again = await plans.create(UID, session_id, "id", LATER + timedelta(minutes=1))

    assert not again.created and again.response.language == "id"
    assert again.response.available_languages == ["en", "id"] and len(translator.calls) == 1


async def test_a_failed_translation_keeps_the_plan_and_the_retry_only_translates() -> None:
    translator = TranslatingGemini(GeminiUnavailableError("down"))
    plans, plan_repo, gemini, session_id = await ready(translator=translator)

    with pytest.raises(GeminiUnavailableError):
        await plans.create(UID, session_id, "ne", LATER)
    plan_id = next(iter(plan_repo.plans[UID]))[0]
    assert plan_repo.get_translation(UID, plan_id, "ne") is None  # nothing half-stored

    retry = await plans.create(UID, session_id, "ne", LATER + timedelta(seconds=30))

    assert not retry.created and retry.response.language == "ne"
    assert len(gemini.calls) == 1  # the English plan was not made twice


async def test_the_figures_are_byte_identical_in_every_language_for_every_persona() -> None:
    for persona in PERSONAS:
        plans, _, _, session_id = await ready(persona)
        english = (await plans.create(UID, session_id, "en", LATER)).response
        for language in LANGUAGES:
            other = await plans.get(UID, english.id, LATER, language)  # type: ignore[arg-type]

            assert same_figures(english.plan, other.plan), (persona.id, language)
            assert other.score == english.score and other.slots == english.slots
            assert other.rates_as_of == english.rates_as_of and other.id == english.id
            assert other.plan.summary != english.plan.summary


async def test_a_plan_that_does_not_exist_cannot_be_translated_or_printed() -> None:
    plans, _, _, _ = await ready()

    with pytest.raises(PlanNotFoundError):
        await plans.get(UID, "0" * 20, LATER, "hi")
    with pytest.raises(PlanNotFoundError):
        await plans.pdf(UID, "0" * 20, "en", LATER)


class Counting:
    """Replaces the renderer, to see how often a PDF is really made and for which plan."""

    def __init__(self) -> None:
        self.rendered: list[CoachPlan] = []

    def __call__(self, response: Any) -> bytes:
        self.rendered.append(response)
        return b"%PDF-1.7 fake " + response.language.encode()


async def test_a_pdf_is_made_once_per_language_then_read_from_cloud_storage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    render = Counting()
    monkeypatch.setattr(plan_files, "render_plan_pdf", render)
    store = FakeExportStore()
    plans, plan_repo, _, session_id = await ready(store=store)
    plan_id = (await plans.create(UID, session_id, "en", LATER)).response.id

    first = await plans.pdf(UID, plan_id, "en", LATER)
    second = await plans.pdf(UID, plan_id, "en", LATER)
    hindi = await plans.pdf(UID, plan_id, "hi", LATER)

    assert first == second == b"%PDF-1.7 fake en" and hindi == b"%PDF-1.7 fake hi"
    assert [r.language for r in render.rendered] == ["en", "hi"]
    assert sorted(store.files) == [
        f"exports/{UID}/coach-plan-{plan_id}-en.pdf",
        f"exports/{UID}/coach-plan-{plan_id}-hi.pdf",
    ]
    stored = plan_repo.get(UID, plan_id)
    assert stored["pdf"]["hi"] == {
        "storage_path": f"exports/{UID}/coach-plan-{plan_id}-hi.pdf",
        "created_at": LATER,
    }
    assert render.rendered[1].plan.summary.startswith("[Hindi]")  # the PDF is of the translation


async def test_a_pdf_missing_from_storage_is_made_again(monkeypatch: pytest.MonkeyPatch) -> None:
    render = Counting()
    monkeypatch.setattr(plan_files, "render_plan_pdf", render)
    store = FakeExportStore()
    plans, _, _, session_id = await ready(store=store)
    plan_id = (await plans.create(UID, session_id, "en", LATER)).response.id
    await plans.pdf(UID, plan_id, "en", LATER)
    store.files.clear()  # deleted by hand

    again = await plans.pdf(UID, plan_id, "en", LATER)

    assert again == b"%PDF-1.7 fake en" and len(render.rendered) == 2
