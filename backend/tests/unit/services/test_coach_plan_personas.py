"""The 90-day plan for the twelve personas, offline (NF-FC-012).

Real cost baselines, real labor-law files, the World Bank corridors and the personas' fixed rates;
only Gemini is a stand-in that writes sentences from the facts. Every plan must validate as the
contract's `CoachPlanResponse`, hold the figures worked out in code, and pass the validator.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.coach.plan_document import build_document, to_response
from app.services.coach.plan_generator import CoachPlanWriter
from app.services.coach.plan_validator import check_figures
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_plan_data import (
    WritingGemini,
    persona_context,
)

pytestmark = pytest.mark.anyio

PERSONAS = load_personas().personas
NOW = datetime(2026, 10, 9, 8, 0, tzinfo=UTC)


async def make_plan(persona: Persona):  # type: ignore[no-untyped-def]
    data, quote, ctx = await persona_context(persona)
    plan = await CoachPlanWriter(WritingGemini()).write(ctx)  # type: ignore[arg-type]
    return persona.expected_slots, data, ctx.inputs, ctx.figures, ctx.score, plan, quote


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
async def test_every_persona_gets_a_plan_that_matches_the_contract_and_the_checks(
    persona: Persona,
) -> None:
    profile, data, inputs, figures, score, plan, quote = await make_plan(persona)

    assert quote is not None, "every persona is on one of the six corridors with a price"
    document = build_document(
        profile=profile,
        session_id="s_01",
        home_country=persona.corridor.split("-")[1],
        corridor_id=persona.corridor,  # type: ignore[arg-type]
        score=score,
        plan=plan,
        grounding={},
        rates_as_of=NOW,
        models={"plan": "m"},
        prompt_versions={"coach.plan": 1},
        now=NOW,
    )
    response = to_response(document["slot_hash"][:20], document, session_id="s_01")

    assert check_figures(plan, figures) == []
    assert response.plan.remittance.provider is not None
    assert response.plan.remittance.provider.receives.currency in ("PHP", "INR", "IDR")
    assert score.total == persona.expected_score.total
    assert [w.week for w in plan.weeks] == list(range(1, 14))
    assert 3 <= len(plan.checklist) <= 10 and len(plan.warnings) <= 8
    assert plan.disclaimer
    assert inputs.recruitment_fee == pytest.approx(
        persona.expected_score.amounts_in_host_currency["fee"], abs=0.01
    )
    assert data.baseline["currency"] == response.reporting_currency


@pytest.mark.parametrize("persona", PERSONAS, ids=[p.id for p in PERSONAS])
async def test_the_budget_adds_up_from_the_personas_hand_worked_amounts(persona: Persona) -> None:
    _, data, _, figures, _, _, _ = await make_plan(persona)
    amounts = persona.expected_score.amounts_in_host_currency
    budget = figures.budget
    deductions = (
        amounts["salary"] * data.baseline["categories"]["mandatory_deductions"]["typical"] / 100
    )
    costs = sum(line.amount.amount for line in budget.costs)

    assert budget.income.amount == pytest.approx(amounts["salary"], abs=0.01)
    assert figures.remittance.monthly_amount.amount == pytest.approx(
        amounts["remittance"], abs=0.01
    )
    assert costs == pytest.approx(amounts["essentials"] + deductions, abs=0.06)
    assert figures.available == pytest.approx(
        amounts["salary"] - costs - amounts["remittance"], abs=0.03
    )
    assert figures.emergency_fund.target.amount == pytest.approx(3 * costs, abs=0.01)
    if figures.available > 0:
        assert budget.left_over.amount >= 0


async def test_maricels_plan_by_hand() -> None:
    """SG domestic worker: pay 650, costs 112, sending 400, a 60%-a-year debt of 2,380.95."""
    persona = next(p for p in PERSONAS if p.id == "p01_sg_ph_maricel")
    _, _, _, figures, _, plan, _ = await make_plan(persona)
    goals = {line.id: line.amount.amount for line in figures.budget.goals}

    assert figures.available == 138.0  # 650 - 112 - 400
    assert goals == {"remittance": 400.0, "debt_payment": 96.0, "emergency_fund": 34.0}
    assert figures.budget.left_over.amount == 8.0
    assert figures.emergency_fund.target.amount == 336.0
    assert figures.emergency_fund.weeks_to_target == 43  # 336 / 34 x 52/12 = 42.8, up
    assert figures.debt is not None and figures.debt.months_to_clear is None  # 96 < the interest
    ids = [w.id for w in plan.warnings]
    assert ids[:3] == ["fee_above_legal_limit", "high_interest_debt", "debt_not_covered"]
    assert "thin_emergency_fund" in ids and "no_pay_account" not in ids  # she has a GCash wallet


async def test_a_worker_with_no_debt_and_a_bank_account_gets_a_calm_plan() -> None:
    quiet = [
        p
        for p in PERSONAS
        if p.expected_slots.debt_outstanding and p.expected_slots.debt_outstanding.amount == 0
    ]
    assert quiet, "the personas include workers with no debt"
    for persona in quiet:
        _, _, _, figures, _, plan, _ = await make_plan(persona)

        assert figures.debt is None and plan.debt is None
        assert "high_interest_debt" not in {w.id for w in plan.warnings}
