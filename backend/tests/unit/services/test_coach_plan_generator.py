"""The model's part of the plan: what it is asked, what is checked, and the retry (NF-FC-012)."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from app.config import get_settings
from app.integrations.gemini.errors import GeminiResponseError
from app.schemas.coach_plan_text import PlanText
from app.services.coach.plan_facts import (
    PlanContext,
    build_facts,
    checklist_ids,
    warnings_for,
)
from app.services.coach.plan_figures import compute_figures
from app.services.coach.plan_generator import DISCLAIMER, PLAN_PROMPT, CoachPlanWriter
from app.services.coach.scoring import score_inputs
from tests.fixtures.coach_plan_data import WritingGemini, compliant_text
from tests.unit.services.test_coach_plan_figures import BASE, QUOTE
from tests.unit.services.test_coach_scoring import BASE as SCORE_BASE

pytestmark = pytest.mark.anyio


def context(**changes: object) -> PlanContext:
    inputs = replace(BASE, **changes)  # type: ignore[arg-type]
    figures = compute_figures(inputs, "AU-IN", QUOTE)
    return PlanContext(
        inputs, figures, score_inputs(SCORE_BASE), "bank_account", "care_worker", 3, "2026-12-01"
    )


def ids(ctx: PlanContext) -> list[str]:
    return [spec.id for spec in warnings_for(ctx)]


def invented(contents: str) -> PlanText:
    return compliant_text(contents).model_copy(update={"summary": "You will earn 99,999 AUD."})


async def test_the_prompt_gives_the_facts_and_asks_for_the_model_text_only() -> None:
    gemini = WritingGemini()
    ctx = context()

    plan = await CoachPlanWriter(gemini).write(ctx)  # type: ignore[arg-type]

    call = gemini.calls[0]
    assert call["response_model"] is PlanText and call["operation"] == "coach.plan"
    assert call["tier"].value == get_settings().gemini_coach_plan_tier
    assert call["system_instruction"] == PLAN_PROMPT.system
    assert json.dumps(build_facts(ctx), ensure_ascii=False) in call["contents"]
    assert "<fix_these>\nnone\n</fix_these>" in call["contents"]
    assert plan.disclaimer == DISCLAIMER
    assert plan.monthly_budget == ctx.figures.budget and plan.debt == ctx.figures.debt


async def test_the_facts_hold_no_text_the_worker_wrote() -> None:
    facts = json.dumps(build_facts(context()))

    assert "passport" not in facts and "agent" not in facts
    assert set(json.loads(facts)) >= {"currency", "monthly_budget", "remittance", "debt"}


async def test_a_rejected_answer_is_asked_again_with_the_reasons() -> None:
    gemini = WritingGemini(invented)

    plan = await CoachPlanWriter(gemini).write(context())  # type: ignore[arg-type]

    assert len(gemini.calls) == 2 and "99,999" not in plan.summary
    second = gemini.calls[1]["contents"]
    assert "<fix_these>\nsummary: the number 99,999 is not one of the given facts" in second


async def test_two_rejected_answers_are_a_bad_response() -> None:
    gemini = WritingGemini(invented, invented, invented)

    with pytest.raises(GeminiResponseError):
        await CoachPlanWriter(gemini).write(context())  # type: ignore[arg-type]
    assert len(gemini.calls) == 2


async def test_a_gemini_error_is_not_swallowed() -> None:
    from app.integrations.gemini import GeminiTimeoutError

    gemini = WritingGemini(GeminiTimeoutError("slow"))

    with pytest.raises(GeminiTimeoutError):
        await CoachPlanWriter(gemini).write(context())  # type: ignore[arg-type]
    assert len(gemini.calls) == 1


def test_the_warnings_follow_the_figures() -> None:
    assert ids(context()) == ["fee_above_legal_limit", "high_interest_debt", "thin_emergency_fund"]
    calm = context(recruitment_fee=0.0, debt=0.0, savings=99999.0)
    assert ids(calm) == []
    assert "fee_above_legal_limit" not in ids(context(recruitment_fee=0.0))
    assert "fee_above_legal_limit" not in ids(context(fee_cap_months=1.0, recruitment_fee=4200.0))
    assert "fee_above_legal_limit" in ids(context(fee_cap_months=1.0, recruitment_fee=4300.0))


def test_a_costly_debt_is_urgent_from_48_percent_a_year_and_a_warning_before() -> None:
    mid = {s.id: s.severity for s in warnings_for(context(debt_rate_yearly_percent=30.0))}
    high = {s.id: s.severity for s in warnings_for(context(debt_rate_yearly_percent=60.0))}
    low = ids(context(debt_rate_yearly_percent=12.0))

    assert mid["high_interest_debt"] == "warning" and high["high_interest_debt"] == "urgent"
    assert "high_interest_debt" not in low


def test_a_gap_and_a_payment_that_does_not_cover_the_interest_are_urgent() -> None:
    gap = context(remittance=3000.0)
    stuck = context(debt=500000.0, debt_rate_yearly_percent=60.0)

    assert "budget_shortfall" in ids(gap)
    assert "debt_not_covered" in ids(stuck)
    assert {s.severity for s in warnings_for(gap) if s.id == "budget_shortfall"} == {"urgent"}


def test_the_most_serious_warning_comes_first_and_there_are_never_more_than_eight() -> None:
    order = {"urgent": 0, "warning": 1, "info": 2}
    ctx = context(remittance=3000.0, debt=500000.0, debt_rate_yearly_percent=60.0)
    severities = [order[s.severity] for s in warnings_for(ctx)]

    assert severities == sorted(severities) and len(severities) <= 8


def test_the_checklist_follows_the_worker() -> None:
    plain = checklist_ids(context(recruitment_fee=0.0, debt=0.0))
    costly = checklist_ids(context())

    assert plain == [
        "keep_documents",
        "compare_transfer_providers",
        "save_helpline_numbers",
        "track_spending",
    ]
    assert "keep_agent_receipts" in costly and "pay_costly_debt_first" in costly
    assert 3 <= len(costly) <= 10
