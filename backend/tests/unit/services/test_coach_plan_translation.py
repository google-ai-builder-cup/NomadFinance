"""The translation of a plan: the numbers check and the translator (NF-FC-014)."""

from __future__ import annotations

import json

import pytest

from app.integrations.gemini import GeminiTimeoutError
from app.integrations.gemini.errors import GeminiResponseError
from app.schemas.coach_plan import CoachPlan
from app.schemas.coach_plan_text import NoteText, PlanTranslation
from app.services.coach.plan_translation_check import (
    apply_narrative,
    check_translation,
    figures_fingerprint,
    narrative_of,
    same_figures,
)
from app.services.coach.plan_translator import CoachPlanTranslator
from tests.fixtures.coach_mocks import MOCKS
from tests.fixtures.coach_plan_data import TranslatingGemini, translated_text

pytestmark = pytest.mark.anyio


def english() -> CoachPlan:
    body = json.loads((MOCKS / "plan-01-created.json").read_text(encoding="utf-8"))["body"]
    return CoachPlan.model_validate(body["plan"])


def faithful() -> PlanTranslation:
    return translated_text("Translate this plan into Hindi.\n<plan>\n" + _plan_json() + "\n</plan>")


def _plan_json() -> str:
    return json.dumps(narrative_of(english()).model_dump(), ensure_ascii=False)


def test_a_faithful_translation_has_no_problems() -> None:
    assert check_translation(narrative_of(english()), faithful()) == []


def test_the_narrative_round_trips_and_leaves_the_figures_alone() -> None:
    plan = english()
    translated = apply_narrative(plan, faithful())

    assert narrative_of(translated) == faithful()
    assert same_figures(plan, translated)
    assert translated.monthly_budget == plan.monthly_budget
    assert translated.remittance == plan.remittance and translated.debt == plan.debt


def test_the_fingerprint_changes_when_a_figure_or_an_id_changes_but_not_for_words() -> None:
    plan = english()
    same = apply_narrative(plan, faithful())
    figure = plan.model_copy(deep=True)
    figure.monthly_budget.income.amount += 1
    ident = plan.model_copy(deep=True)
    ident.warnings[0].id = "something_else"
    severity = plan.model_copy(deep=True)
    severity.warnings[0].severity = "info"

    assert same_figures(plan, same)
    assert not same_figures(plan, figure) and not same_figures(plan, ident)
    assert not same_figures(plan, severity)
    assert figures_fingerprint(plan) == figures_fingerprint(same)


def bad(**changes: object) -> PlanTranslation:
    return faithful().model_copy(update=changes)


@pytest.mark.parametrize(
    "summary",
    [
        "आप हर महीने लगभग 4,300 AUD कमाएँगे।",  # a number changed
        "आप हर महीने लगभग AUD कमाएँगे।",  # a number dropped
        "आप हर महीने लगभग 4,200 AUD और 900 AUD कमाएँगे। 5",  # numbers added
        "आप हर महीने लगभग ४,२०० AUD कमाएँगे।",  # digits of another script
        "आप हर महीने लगभग 4,200 SGD कमाएँगे।",  # a currency code changed
        "आप हर महीने लगभग 4.200 AUD कमाएँगे।",  # another separator
        "",
        "Visit www.example.org 4,200 AUD 900 AUD 5 3%",
    ],
)
def test_a_summary_that_changes_a_number_or_code_is_rejected(summary: str) -> None:
    source = narrative_of(english())

    assert check_translation(source, bad(summary=summary)), summary


def test_the_numbers_may_move_within_a_sentence() -> None:
    source = narrative_of(english())
    own = source.summary
    reordered = " ".join(reversed(own.split(" ")))

    assert check_translation(source, bad(summary=reordered)) == []


def test_a_runaway_answer_is_rejected() -> None:
    source = narrative_of(english())
    long = "word " * 2000 + source.summary

    assert check_translation(source, bad(summary=long))


def test_the_structure_must_be_the_same() -> None:
    source = narrative_of(english())
    target = faithful()
    fewer = target.model_copy(update={"weeks": target.weeks[:12]})
    swapped = target.model_copy(
        update={"weeks": [target.weeks[1], target.weeks[0], *target.weeks[2:]]}
    )
    fewer_actions = target.weeks[0].model_copy(update={"actions": target.weeks[0].actions[:1]})
    actions = target.model_copy(update={"weeks": [fewer_actions, *target.weeks[1:]]})
    ids = target.model_copy(update={"warnings": [NoteText(id="x", text="t"), *target.warnings[1:]]})
    checklist = target.model_copy(update={"checklist": target.checklist[:-1]})

    for broken in (fewer, swapped, actions, ids, checklist):
        assert check_translation(source, broken), broken


def test_a_made_up_figure_in_any_part_is_found() -> None:
    source = narrative_of(english())
    target = faithful()
    week = target.weeks[3].model_copy(update={"actions": ["Send 777 AUD now."]})
    for broken in (
        target.model_copy(update={"weeks": [*target.weeks[:3], week, *target.weeks[4:]]}),
        target.model_copy(
            update={
                "warnings": [NoteText(id=target.warnings[0].id, text="Pay 1,234 AUD.")]
                + target.warnings[1:]
            }
        ),
        target.model_copy(update={"disclaimer": target.disclaimer + " 24x7"}),
    ):
        assert check_translation(source, broken)


async def test_the_translator_returns_the_plan_with_only_its_words_changed() -> None:
    gemini = TranslatingGemini()
    plan = english()

    translated = await CoachPlanTranslator(gemini).translate(plan, "hi")  # type: ignore[arg-type]

    assert same_figures(plan, translated) and translated.summary.startswith("[Hindi]")
    call = gemini.calls[0]
    assert call["response_model"] is PlanTranslation and call["operation"] == "coach.translate_plan"
    assert call["tier"].value == "classification" and call["temperature"] == 0.0
    # Only sentences are sent: no figure structure, no ids of the budget or the provider quote.
    assert "monthly_budget" not in call["contents"] and "fx_rate" not in call["contents"]
    assert "<fix_these>\nnone\n</fix_these>" in call["contents"]


async def test_a_rejected_translation_is_asked_again_with_the_reasons() -> None:
    def wrong(contents: str) -> PlanTranslation:
        return translated_text(contents).model_copy(update={"summary": "लगभग 4,300 AUD"})

    gemini = TranslatingGemini(wrong)

    translated = await CoachPlanTranslator(gemini).translate(english(), "tl")  # type: ignore[arg-type]

    assert len(gemini.calls) == 2 and "4,300" not in translated.summary
    assert "summary: numbers and currency codes must be exactly" in gemini.calls[1]["contents"]


async def test_two_rejected_translations_are_a_bad_response() -> None:
    def wrong(contents: str) -> PlanTranslation:
        return translated_text(contents).model_copy(update={"summary": "x"})

    gemini = TranslatingGemini(wrong, wrong, wrong)

    with pytest.raises(GeminiResponseError):
        await CoachPlanTranslator(gemini).translate(english(), "id")  # type: ignore[arg-type]
    assert len(gemini.calls) == 2


async def test_english_is_not_translated_and_gemini_errors_pass_through() -> None:
    with pytest.raises(ValueError):
        await CoachPlanTranslator(TranslatingGemini()).translate(english(), "en")  # type: ignore[arg-type]
    with pytest.raises(GeminiTimeoutError):
        await CoachPlanTranslator(TranslatingGemini(GeminiTimeoutError("slow"))).translate(  # type: ignore[arg-type]
            english(), "bn"
        )
