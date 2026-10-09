"""The plan validator rejects any figure that cannot be worked out from the inputs (NF-FC-012)."""

from __future__ import annotations

from typing import Any

import pytest

from app.schemas.coach_plan_text import NoteText, PlanText, WeekText
from app.services.coach.plan_validator import Numbers, check_figures, check_text, number_problems
from tests.fixtures.coach_plan_data import compliant_text
from tests.unit.services.test_coach_plan_figures import BASE, QUOTE, compute_figures

FACTS: dict[str, Any] = {
    "currency": "AUD",
    "worker": {"dependents": 3, "departure_date": "2026-12-01", "savings_now": 454.0},
    "monthly_budget": {"income": 4200.0, "left_over": 58.0, "goals": {"remittance": 900.0}},
    "debt": {"outstanding": 2177.07, "monthly_payment": 801.0, "months_to_clear": 3},
    "warning_facts": {"high_interest_debt": {"interest_percent_per_month": 3.0}},
    "fee": {"fee_paid": 2721.43},
    "remittance": {"monthly_amount": 900.0},
}
NUMBERS = Numbers(FACTS)


def problems(text: str) -> list[str]:
    return number_problems(text, NUMBERS, "t")


@pytest.mark.parametrize(
    "text",
    [
        "You will earn about 4,200 AUD a month.",
        "Your fee was about 2,721 AUD.",  # 2,721.43 rounded
        "Your fee was 2,721.43 AUD.",
        "Your debt is 2,177 AUD.",
        "You pay 801 AUD each month for 3 months.",
        "The debt costs 3% each month.",
        "In week 5 send 900 AUD.",
        "You have 3 people who depend on you.",
        "Your plan leaves for 1 December 2026.",
        "Check again at 30, 60 and 90 days.",
        "AUD 58 is left over.",
        "Pay 801 AUD for 5 weeks.",  # 5 is within the weeks 1 to 13 a plan may name
        "You have 454 AUD saved.",
    ],
)
def test_a_sentence_using_only_the_given_numbers_passes(text: str) -> None:
    assert problems(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "Your fee was 3,000 AUD.",  # not a fact
        "Send 9 AUD to your family.",  # 9 is a week number but this is an amount
        "You can save 5,000 AUD.",
        "Your debt costs 4% each month.",
        "Your debt costs 4 percent each month.",  # the digits could pass as a week number
        "It costs 6 percent a year.",
        "Call 1800 123 456 for help.",
        "Your debt and fee are 4,898.5 AUD together.",  # a sum nobody gave
        "You will earn 4,200.5 AUD.",  # more precision than the fact has
        "You will save 4,201 AUD.",
    ],
)
def test_a_sentence_with_a_number_that_was_not_given_is_rejected(text: str) -> None:
    assert problems(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Talk to a worker support group to see if you can get a safer loan.",
        "You could borrow money from a friend.",
        "Take out a new loan to pay the old one.",
        "Look at a cheaper lender.",
        "Invest your savings.",
        "Buy insurance for the trip.",
    ],
)
def test_advice_to_borrow_or_invest_is_rejected(text: str) -> None:
    assert problems(text), text


@pytest.mark.parametrize(
    "text",
    [
        "Your debt costs 3 percent each month.",
        "Talk to a worker support group about your debt.",
        "Your loan from the agent costs a lot.",
        "Do not take on more debt.",
    ],
)
def test_describing_the_debt_is_not_advice(text: str) -> None:
    assert problems(text) == [], text


@pytest.mark.parametrize(
    "text",
    [
        "You will earn about four thousand dollars.",
        "You owe 2 lakh rupees.",
        "Read https://example.org for help.",
        "Write to help@example.org.",
    ],
)
def test_scale_words_and_links_are_rejected(text: str) -> None:
    assert problems(text)


def test_the_writer_stub_passes_for_a_real_plan() -> None:
    figures = compute_figures(BASE, "AU-IN", QUOTE)
    assert figures.budget.income.amount == 4200.0
    text = compliant_text(_prompt(FACTS, [], []))

    assert check_text(text, FACTS, [], []) == []


def _prompt(
    facts: dict[str, Any], warnings: list[dict[str, Any]], checklist: list[dict[str, Any]]
) -> str:
    import json

    return (
        f"<facts>\n{json.dumps(facts)}\n</facts>\n<warnings_to_write>\n{json.dumps(warnings)}\n"
        f"</warnings_to_write>\n<checklist_to_write>\n{json.dumps(checklist)}\n</checklist_to_write>"
    )


def _good() -> PlanText:
    return compliant_text(
        _prompt(
            FACTS,
            [{"id": "high_interest_debt", "about": "x"}],
            [{"id": "keep_documents", "about": "Keep copies."}],
        )
    )


def test_the_ids_of_warnings_and_checklist_must_be_the_ones_asked_for() -> None:
    text = _good()

    assert check_text(text, FACTS, ["high_interest_debt"], ["keep_documents"]) == []
    assert check_text(text, FACTS, ["other"], ["keep_documents"])
    assert check_text(text, FACTS, ["high_interest_debt"], ["keep_documents", "track_spending"])


def test_the_plan_must_have_weeks_1_to_13_in_order_with_one_to_four_actions() -> None:
    text = _good()
    missing = text.model_copy(update={"weeks": text.weeks[:12]})
    shuffled = text.model_copy(update={"weeks": [text.weeks[1], text.weeks[0], *text.weeks[2:]]})
    many = text.weeks[0].model_copy(update={"actions": ["a"] * 5})
    too_many = text.model_copy(update={"weeks": [many, *text.weeks[1:]]})
    empty = text.model_copy(update={"summary": ""})

    for bad in (missing, shuffled, too_many, empty):
        assert check_text(bad, FACTS, ["high_interest_debt"], ["keep_documents"])


def test_a_made_up_number_in_any_part_of_the_text_is_found() -> None:
    text = _good()
    in_week = text.weeks[3].model_copy(update={"actions": ["Send 777 AUD now."]})
    for bad in (
        text.model_copy(update={"summary": "You will earn 9,999 AUD."}),
        text.model_copy(update={"weeks": [*text.weeks[:3], in_week, *text.weeks[4:]]}),
        text.model_copy(
            update={"warnings": [NoteText(id="high_interest_debt", text="Pay 1,234 AUD.")]}
        ),
        text.model_copy(
            update={"checklist": [NoteText(id="keep_documents", text="Call 5551234.")]}
        ),
    ):
        assert check_text(bad, FACTS, ["high_interest_debt"], ["keep_documents"]), bad


def test_a_plan_whose_figures_were_edited_is_rejected() -> None:
    from app.schemas.coach_plan import CoachPlan

    figures = compute_figures(BASE, "AU-IN", QUOTE)
    text = compliant_text(_prompt(FACTS, [], []))
    weeks = [w.model_dump() for w in text.weeks]
    plan = CoachPlan.model_validate(
        {
            "summary": "s",
            "monthly_budget": figures.budget.model_dump(),
            "remittance": figures.remittance.model_dump(),
            "debt": figures.debt.model_dump() if figures.debt else None,
            "emergency_fund": figures.emergency_fund.model_dump(),
            "weeks": weeks,
            "warnings": [],
            "checklist": [{"id": f"item_{i}", "text": "t"} for i in range(3)],
            "disclaimer": "d",
        }
    )
    assert check_figures(plan, figures) == []

    tampered = plan.model_copy(deep=True)
    assert tampered.debt is not None
    tampered.debt.monthly_payment.amount += 50
    other = plan.model_copy(deep=True)
    other.remittance.monthly_amount.amount = 1.0

    assert check_figures(tampered, figures) == ["debt differs from the worked-out figures"]
    assert check_figures(other, figures) == ["remittance differs from the worked-out figures"]
    assert WeekText  # imported for the shape of the weeks above
