"""The scorer that reads the stored data (NF-FC-011): what it needs, and what it does without."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from app.schemas.coach_profile import CoachProfile
from app.services.coach.coach_scorer import CoachScorer
from app.services.coach.scoring_inputs import ScoreUnavailableError
from tests.fixtures.coach_personas import Persona, load_personas
from tests.fixtures.coach_scoring_data import FakeBaselines, FakeLaws, FakeRates

pytestmark = pytest.mark.anyio

PERSONAS = {p.id: p for p in load_personas().personas}
MARICEL = PERSONAS["p01_sg_ph_maricel"]  # SGD pay, PHP debts: needs one rate
ANIL = PERSONAS["p06_au_in_anil"]


def rates_of(persona: Persona) -> dict[str, float]:
    return {persona.expected_score.rate_pair: persona.expected_score.rate}


def scorer(
    persona: Persona = MARICEL,
    *,
    rates: dict[str, float] | None = None,
    baselines: FakeBaselines | None = None,
    laws: FakeLaws | None = None,
) -> CoachScorer:
    return CoachScorer(
        baselines or FakeBaselines(),  # type: ignore[arg-type]
        laws or FakeLaws(),  # type: ignore[arg-type]
        FakeRates(rates_of(persona) if rates is None else rates),  # type: ignore[arg-type]
    )


async def test_a_complete_profile_gets_the_personas_score() -> None:
    result = await scorer().score(MARICEL.expected_slots)

    assert (result.total, result.band) == (22, "needs_work")


@pytest.mark.parametrize("persona", PERSONAS.values(), ids=list(PERSONAS))
async def test_every_persona_scores_through_the_stored_data(persona: Persona) -> None:
    result = await scorer(persona)(persona.expected_slots)

    assert result is not None
    assert (result.total, result.band) == (
        persona.expected_score.total,
        persona.expected_score.band,
    )


async def test_pay_in_the_host_currency_needs_no_rate() -> None:
    profile = MARICEL.expected_slots.model_copy(
        update={
            "recruitment_fee_paid": MARICEL.expected_slots.monthly_salary,
            "debt_outstanding": MARICEL.expected_slots.monthly_salary,
            "savings": MARICEL.expected_slots.monthly_salary,
        }
    )

    assert await scorer(rates={})(profile) is not None


@pytest.mark.parametrize(
    ("label", "build", "reason"),
    [
        ("no rate", lambda: scorer(rates={}), "no_rate:SGD_PHP"),
        ("no baseline", lambda: scorer(baselines=FakeBaselines(missing=("SG",))), "no_baseline:SG"),
        ("no fee rule", lambda: scorer(laws=FakeLaws(without_fee_rule=("SG",))), "no_fee_rule:SG"),
        ("a rate of zero", lambda: scorer(rates={"SGD_PHP": 0.0}), "no_rate:SGD_PHP"),
    ],
)
async def test_missing_data_makes_the_score_unavailable_and_says_why(
    label: str, build: Any, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    with pytest.raises(ScoreUnavailableError, match=reason):
        await build().score(MARICEL.expected_slots)

    with caplog.at_level(logging.WARNING):
        assert await build()(MARICEL.expected_slots) is None
    assert f"coach_score_unavailable reason={reason}" in caplog.text


async def test_the_log_never_holds_the_workers_figures(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        await scorer(rates={})(MARICEL.expected_slots)

    assert "650" not in caplog.text and "Maricel" not in caplog.text


async def test_an_incomplete_profile_is_unavailable() -> None:
    profile = CoachProfile(destination_country="SG", job_type="domestic_worker")

    with pytest.raises(ScoreUnavailableError, match="incomplete"):
        await scorer().score(profile)


async def test_pay_of_zero_is_unavailable_not_an_error() -> None:
    zero = MARICEL.expected_slots.monthly_salary.model_copy(update={"amount": 0.0})  # type: ignore[union-attr]
    profile = MARICEL.expected_slots.model_copy(update={"monthly_salary": zero})

    assert await scorer()(profile) is None


async def test_a_baseline_in_another_currency_is_refused() -> None:
    class Wrong(FakeBaselines):
        def get_baseline(self, host: str) -> dict[str, Any] | None:
            return {**(super().get_baseline(host) or {}), "currency": "USD"}

    with pytest.raises(ScoreUnavailableError, match="baseline_currency:SG"):
        await scorer(baselines=Wrong()).score(MARICEL.expected_slots)


async def test_a_nepali_or_bangladeshi_amount_has_no_rate_and_is_not_guessed() -> None:
    profile = ANIL.expected_slots.model_copy(
        update={
            "debt_outstanding": ANIL.expected_slots.debt_outstanding.model_copy(  # type: ignore[union-attr]
                update={"currency": "NPR"}
            )
        }
    )

    assert await scorer(ANIL)(profile) is None
