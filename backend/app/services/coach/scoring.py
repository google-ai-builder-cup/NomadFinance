"""The preparedness score: the rubric of `docs/features/coach-scoring.md`, version 1 (NF-FC-011).

Pure arithmetic on numbers already in one currency. No model, no clock, no I/O: the same inputs
always give the same score. What goes in (the amounts in the host currency, the essential costs,
the legal fee cap) is gathered and converted elsewhere (`scoring_inputs.py`, `coach_scorer.py`).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.coach_plan import CoachScore, ScoreFactor
from app.schemas.coach_profile import AccountKind

RUBRIC_VERSION = 1

WEIGHTS: dict[str, float] = {
    "debt_to_income": 0.30,
    "emergency_buffer": 0.25,
    "remittance_ratio": 0.15,
    "recruitment_fee_vs_cap": 0.20,
    "banked_status": 0.10,
}

# (figure, points) anchors; the points between two anchors are on a straight line.
DEBT_MONTHS: tuple[tuple[float, float], ...] = ((0, 100), (1, 85), (3, 60), (6, 30), (12, 0))
BUFFER_MONTHS: tuple[tuple[float, float], ...] = ((0, 0), (1, 35), (3, 75), (6, 100))
REMITTANCE_SHARE: tuple[tuple[float, float], ...] = (
    (0, 100),
    (0.3, 100),
    (0.5, 70),
    (0.7, 30),
    (0.9, 0),
)
FEE_EXCESS_MONTHS: tuple[tuple[float, float], ...] = (
    (0, 100),
    (0.25, 75),
    (0.5, 55),
    (1, 30),
    (2, 0),
)
BANKED: dict[str, tuple[float, int]] = {
    "both": (1.0, 100),
    "bank_account": (1.0, 90),
    "mobile_wallet": (0.5, 55),
    "none": (0.0, 0),
}

HIGH_INTEREST_YEARLY = 24.0  # percent a year: 10 points off the debt factor
VERY_HIGH_INTEREST_YEARLY = 48.0  # 20 points off
SHORTFALL_CAP_POINTS = 25.0
MIN_OUTGOINGS_SHARE = 0.25  # of pay: so a worker who spends nothing does not divide by zero
NEEDS_WORK_BELOW = 40
WELL_PREPARED_FROM = 70
FLOOR_POINTS = 20  # a factor under this keeps the band at `getting_ready`


@dataclass(frozen=True)
class ScoreInputs:
    """Everything the rubric reads. Every amount is in the host currency, per month or a total."""

    monthly_salary: float
    remittance_target: float  # per month
    recruitment_fee: float  # a total
    debt: float  # a total
    savings: float  # a total
    debt_rate_yearly_percent: float | None  # None when no rate was given
    account: AccountKind
    essentials: float  # typical accommodation, food, transport and phone for a month
    fee_cap_months: float  # the most an agent may charge, in months of pay


class NotScorableError(ValueError):
    """The inputs cannot be scored (no pay to measure against)."""


def half_up(number: float) -> int:
    """90.5 is 91; the built-in `round` would give 90. The tiny add keeps 59.25 stable."""
    return math.floor(number + 0.5 + 1e-9)


def interpolate(anchors: Sequence[tuple[float, float]], figure: float) -> float:
    """Points for `figure`: first anchor's below it, the last's above it, a line between."""
    if figure <= anchors[0][0]:
        return float(anchors[0][1])
    for (x0, p0), (x1, p1) in zip(anchors, anchors[1:], strict=False):
        if figure <= x1:
            return p0 + (p1 - p0) * (figure - x0) / (x1 - x0)
    return float(anchors[-1][1])


def band_of(total: int, points: Sequence[int]) -> str:
    """The band of a total, held at `getting_ready` when any single factor is under 20."""
    if total < NEEDS_WORK_BELOW:
        return "needs_work"
    if total < WELL_PREPARED_FROM or min(points) < FLOOR_POINTS:
        return "getting_ready"
    return "well_prepared"


def _debt(inputs: ScoreInputs) -> tuple[float, float]:
    months = inputs.debt / inputs.monthly_salary
    points = interpolate(DEBT_MONTHS, months)
    rate = inputs.debt_rate_yearly_percent
    if inputs.debt > 0 and rate is not None:
        if rate >= VERY_HIGH_INTEREST_YEARLY:
            points -= 20
        elif rate >= HIGH_INTEREST_YEARLY:
            points -= 10
    return months, max(0.0, points)


def _buffer(inputs: ScoreInputs) -> tuple[float, float]:
    outgoings = max(
        inputs.essentials + inputs.remittance_target,
        MIN_OUTGOINGS_SHARE * inputs.monthly_salary,
    )
    months = inputs.savings / outgoings
    return months, interpolate(BUFFER_MONTHS, months)


def _remittance(inputs: ScoreInputs) -> tuple[float, float]:
    share = inputs.remittance_target / inputs.monthly_salary
    points = interpolate(REMITTANCE_SHARE, share)
    if inputs.monthly_salary - inputs.essentials - inputs.remittance_target < 0:
        points = min(points, SHORTFALL_CAP_POINTS)
    return share, points


def _fee(inputs: ScoreInputs) -> tuple[float, float]:
    months = inputs.recruitment_fee / inputs.monthly_salary
    excess = max(0.0, months - inputs.fee_cap_months)
    return months, interpolate(FEE_EXCESS_MONTHS, excess)


def _banked(inputs: ScoreInputs) -> tuple[float, float]:
    value, points = BANKED[inputs.account]
    return value, float(points)


def score_inputs(inputs: ScoreInputs) -> CoachScore:
    """The score of one worker's answers.

    Each factor's points are rounded half up to a whole number, and that whole number is what is
    reported and weighted; `value` is the measured figure to two decimals.

    Raises:
        NotScorableError: The monthly pay is not above zero, so there is nothing to measure
            against.
    """
    if inputs.monthly_salary <= 0:
        raise NotScorableError("monthly_salary")
    measured = {
        "debt_to_income": _debt(inputs),
        "emergency_buffer": _buffer(inputs),
        "remittance_ratio": _remittance(inputs),
        "recruitment_fee_vs_cap": _fee(inputs),
        "banked_status": _banked(inputs),
    }
    whole = {name: half_up(points) for name, (_, points) in measured.items()}
    total = half_up(sum(WEIGHTS[name] * whole[name] for name in measured))
    return CoachScore(
        total=total,
        band=band_of(total, list(whole.values())),
        factors=[
            ScoreFactor(
                id=name,
                value=round(figure, 2),
                score=float(whole[name]),
                weight=WEIGHTS[name],
            )
            for name, (figure, _) in measured.items()
        ],
        rubric_version=RUBRIC_VERSION,
    )
