"""A slow, plain copy of the scoring rubric (`docs/features/coach-scoring.md`, version 1).

It exists to check the persona fixtures (NF-FC-007): the expected scores stored there are
re-worked here from the answers, and this file is itself checked against the three worked
examples printed in the rubric page. It is not the scoring engine (NF-FC-011); the engine must
match the fixtures, and this file is only a second way of reaching the same numbers.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.schemas.coach_profile import CoachProfile, Money

BASELINES = (
    Path(__file__).resolve().parents[3] / "data-scripts" / "data" / "source" / "cost-baselines"
)

WEIGHTS = {
    "debt_to_income": 0.30,
    "emergency_buffer": 0.25,
    "remittance_ratio": 0.15,
    "recruitment_fee_vs_cap": 0.20,
    "banked_status": 0.10,
}
# The most the host's law lets an agent charge, in months of pay (rubric page, "by host").
CAP_MONTHS = {"SG": 2.0, "MY": 1.0, "HK": 0.10, "KR": 0.0, "JP": 0.0, "AU": 0.0}
HOST_CURRENCY = {"SG": "SGD", "KR": "KRW", "MY": "MYR", "JP": "JPY", "HK": "HKD", "AU": "AUD"}
DEBT = [(0, 100), (1, 85), (3, 60), (6, 30), (12, 0)]
BUFFER = [(0, 0), (1, 35), (3, 75), (6, 100)]
REMITTANCE = [(0, 100), (0.3, 100), (0.5, 70), (0.7, 30), (0.9, 0)]
FEE_EXCESS = [(0, 100), (0.25, 75), (0.5, 55), (1, 30), (2, 0)]
BANKED = {
    "both": (1.0, 100),
    "bank_account": (1.0, 90),
    "mobile_wallet": (0.5, 55),
    "none": (0.0, 0),
}
ESSENTIAL_LINES = ("accommodation", "food", "transport", "phone_data")


def half_up(number: float) -> int:
    """90.5 is 91 (the built-in `round` would give 90). The tiny add keeps 59.25 stable."""
    return math.floor(number + 0.5 + 1e-9)


def interpolate(anchors: Sequence[tuple[float, float]], x: float) -> float:
    if x <= anchors[0][0]:
        return float(anchors[0][1])
    for (x0, p0), (x1, p1) in zip(anchors, anchors[1:], strict=False):
        if x <= x1:
            return p0 + (p1 - p0) * (x - x0) / (x1 - x0)
    return float(anchors[-1][1])


def essentials(host: str, job_type: str) -> float:
    """Typical accommodation + food + transport + phone for the host, with the job's override."""
    data = json.loads((BASELINES / f"{host}.json").read_text(encoding="utf-8"))
    total = 0.0
    for line in ESSENTIAL_LINES:
        figure = data["categories"][line]
        band = (figure.get("by_job_type") or {}).get(job_type, figure)
        total += band["typical"]
    return total


def to_host(money: Money, host: str, rates: dict[str, float], per_month: bool) -> float:
    """The amount in the host currency. `rates` maps a currency to units bought by one host unit."""
    amount = money.per_month() if per_month else money.amount
    if money.currency == HOST_CURRENCY[host]:
        return amount
    return amount / rates[money.currency]


def band_for(total: int, points: list[int]) -> str:
    band = "needs_work" if total < 40 else "getting_ready" if total < 70 else "well_prepared"
    if band == "well_prepared" and min(points) < 20:
        return "getting_ready"
    return band


def score(profile: CoachProfile, rates: dict[str, float]) -> dict[str, Any]:
    """The rubric applied to a complete profile. Returns the arithmetic as well as the score."""
    assert profile.destination_country and profile.job_type
    assert profile.monthly_salary and profile.remittance_target and profile.savings
    assert profile.recruitment_fee_paid and profile.debt_outstanding and profile.bank_or_wallet
    host = profile.destination_country
    salary = to_host(profile.monthly_salary, host, rates, per_month=True)
    remittance = to_host(profile.remittance_target, host, rates, per_month=True)
    fee = to_host(profile.recruitment_fee_paid, host, rates, per_month=False)
    debt = to_host(profile.debt_outstanding, host, rates, per_month=False)
    savings = to_host(profile.savings, host, rates, per_month=False)
    costs = essentials(host, profile.job_type)

    debt_months = debt / salary
    debt_points = interpolate(DEBT, debt_months)
    if debt > 0 and profile.debt_interest is not None:
        yearly = profile.debt_interest.rate_percent * (
            12 if profile.debt_interest.period == "month" else 1
        )
        debt_points -= 20 if yearly >= 48 else 10 if yearly >= 24 else 0
    debt_points = max(0.0, debt_points)

    outgoings = max(costs + remittance, 0.25 * salary)
    buffer_months = savings / outgoings

    share = remittance / salary
    share_points = interpolate(REMITTANCE, share)
    if salary - costs - remittance < 0:
        share_points = min(share_points, 25.0)

    fee_months = fee / salary
    fee_points = interpolate(FEE_EXCESS, max(0.0, fee_months - CAP_MONTHS[host]))

    banked_value, banked_points = BANKED[profile.bank_or_wallet]
    factors = {
        "debt_to_income": (debt_months, debt_points),
        "emergency_buffer": (buffer_months, interpolate(BUFFER, buffer_months)),
        "remittance_ratio": (share, share_points),
        "recruitment_fee_vs_cap": (fee_months, fee_points),
        "banked_status": (banked_value, float(banked_points)),
    }
    whole = {name: half_up(points) for name, (_, points) in factors.items()}
    total = half_up(sum(WEIGHTS[name] * whole[name] for name in factors))
    return {
        "amounts": {
            "salary": salary,
            "remittance": remittance,
            "fee": fee,
            "debt": debt,
            "savings": savings,
            "essentials": costs,
            "outgoings": outgoings,
        },
        "factors": {name: (value, whole[name]) for name, (value, _) in factors.items()},
        "total": total,
        "band": band_for(total, list(whole.values())),
    }
