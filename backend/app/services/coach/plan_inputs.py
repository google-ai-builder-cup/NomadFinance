"""The plan's inputs, from a profile and the stored data (NF-FC-012).

Reuses the score's conversion (`build_inputs`), so the plan and the score are worked out from
the same host-currency figures.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from app.schemas.coach_profile import CoachProfile, Currency
from app.services.coach.coach_scorer import ScoringData
from app.services.coach.plan_figures import PlanInputs
from app.services.coach.scoring import ScoreInputs
from app.services.coach.scoring_inputs import (
    HOST_CURRENCY,
    ScoreUnavailableError,
    build_inputs,
    essential_lines,
    fee_cap_months,
)


def deductions_percent(baseline: Mapping[str, Any]) -> float:
    """The typical share of pay taken in mandatory deductions, in percent."""
    figure = baseline.get("categories", {}).get("mandatory_deductions")
    if not isinstance(figure, Mapping) or figure.get("unit") != "pct_of_wage":
        raise ScoreUnavailableError("baseline_line:mandatory_deductions")
    return float(figure["typical"])


def setup_total(baseline: Mapping[str, Any]) -> float:
    """The typical one-off costs of the first month, summed."""
    lines = baseline.get("setup_costs") or {}
    return sum(float(line["typical"]) for line in lines.values() if isinstance(line, Mapping))


def score_inputs_of(profile: CoachProfile, data: ScoringData) -> ScoreInputs:
    """The rubric's inputs (the same call the score makes)."""
    return build_inputs(
        profile,
        essentials=sum(essential_lines(data.baseline, profile.job_type or "").values()),
        cap_months=fee_cap_months(data.rules),
        rates=data.rates,
    )


def plan_inputs(profile: CoachProfile, data: ScoringData) -> PlanInputs:
    """The plan's inputs in the host currency.

    Raises:
        ScoreUnavailableError: An answer, a baseline line or a rate is missing.
    """
    host = profile.destination_country
    if host is None or profile.job_type is None:
        raise ScoreUnavailableError("incomplete")
    scored = score_inputs_of(profile, data)
    lines = essential_lines(data.baseline, profile.job_type)
    deductions = scored.monthly_salary * deductions_percent(data.baseline) / 100
    return PlanInputs(
        currency=cast(Currency, HOST_CURRENCY[host]),
        salary=scored.monthly_salary,
        remittance=scored.remittance_target,
        recruitment_fee=scored.recruitment_fee,
        debt=scored.debt,
        savings=scored.savings,
        debt_rate_yearly_percent=scored.debt_rate_yearly_percent,
        costs=(*lines.items(), ("deductions", deductions)),
        setup_costs=setup_total(data.baseline),
        fee_cap_months=scored.fee_cap_months,
    )
