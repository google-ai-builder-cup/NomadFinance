"""Gathering what the preparedness score reads (NF-FC-011): one currency, the costs, the fee cap.

Pure helpers over documents already read from Firestore; `coach_scorer.py` does the reading.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.schemas.coach_profile import CoachProfile, Money
from app.services.coach.scoring import ScoreInputs

HOST_CURRENCY: dict[str, str] = {
    "SG": "SGD",
    "KR": "KRW",
    "MY": "MYR",
    "JP": "JPY",
    "HK": "HKD",
    "AU": "AUD",
}
ESSENTIAL_LINES = ("accommodation", "food", "transport", "phone_data")
# The keys of `labor_laws/{host}/rules/recruitment_fees` (`variants[].limits`) that are the most an
# agent may charge a worker, in months of pay or a percent of the first month's wages. Other
# limits of the same rule (a refund share, a registration fee in money) are not caps.
FEE_CAP_KEYS = ("maximum_agency_fee", "placement_fee_non_citizen", "maximum_commission")


class ScoreUnavailableError(RuntimeError):
    """The score cannot be worked out now: data is missing. The session shows "try again"."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def essential_lines(baseline: Mapping[str, Any], job_type: str) -> dict[str, float]:
    """Typical monthly cost of each essential line, with the job's override.

    Raises:
        ScoreUnavailableError: A line is missing from the stored baseline.
    """
    lines: dict[str, float] = {}
    for line in ESSENTIAL_LINES:
        figure = baseline.get("categories", {}).get(line)
        if not isinstance(figure, Mapping):
            raise ScoreUnavailableError(f"baseline_line:{line}")
        band = (figure.get("by_job_type") or {}).get(job_type, figure)
        lines[line] = float(band["typical"])
    return lines


def essentials_from(baseline: Mapping[str, Any], job_type: str) -> float:
    """Typical accommodation + food + transport + phone for a month, with the job's override.

    Raises:
        ScoreUnavailableError: A line is missing from the stored baseline.
    """
    return sum(essential_lines(baseline, job_type).values())


def fee_cap_months(rules: Mapping[str, Mapping[str, Any]]) -> float:
    """The most an agent may charge, in months of pay; 0 when the law gives no number.

    A limit in months is used as it is and a percent is divided by 100. KR, JP and AU have no
    number (taking money from a worker is not allowed or not capped), so their cap is 0.
    """
    for variant in rules.get("recruitment_fees", {}).get("variants", []):
        if "all" not in variant.get("applies_to", []):
            continue
        limits = variant.get("limits") or {}
        for key in FEE_CAP_KEYS:
            limit = limits.get(key)
            if not isinstance(limit, Mapping):
                continue
            if limit.get("unit") == "months":
                return float(limit["value"])
            if limit.get("unit") == "percent":
                return float(limit["value"]) / 100
    return 0.0


def currencies_to_convert(profile: CoachProfile, host: str) -> set[str]:
    """The currencies of the profile's amounts that are not the host's, so need a rate."""
    amounts = (
        profile.monthly_salary,
        profile.remittance_target,
        profile.recruitment_fee_paid,
        profile.debt_outstanding,
        profile.savings,
    )
    return {m.currency for m in amounts if m is not None and m.currency != HOST_CURRENCY[host]}


def to_host(money: Money, host: str, rates: Mapping[str, float], *, per_month: bool) -> float:
    """The amount in the host currency, from `rates` (pair id such as `SGD_INR`: units bought by
    one host unit).

    Raises:
        ScoreUnavailableError: There is no rate from the host currency to the amount's.
    """
    amount = money.per_month() if per_month else money.amount
    if money.currency == HOST_CURRENCY[host]:
        return amount
    pair = f"{HOST_CURRENCY[host]}_{money.currency}"
    rate = rates.get(pair)
    if rate is None or rate <= 0:
        raise ScoreUnavailableError(f"no_rate:{pair}")
    return amount / rate


def build_inputs(
    profile: CoachProfile,
    *,
    essentials: float,
    cap_months: float,
    rates: Mapping[str, float],
) -> ScoreInputs:
    """The rubric's inputs from a complete profile, in the host currency.

    Raises:
        ScoreUnavailableError: An answer is missing, or an amount has no rate.
    """
    host = profile.destination_country
    salary, target = profile.monthly_salary, profile.remittance_target
    fee, debt, savings = (
        profile.recruitment_fee_paid,
        profile.debt_outstanding,
        profile.savings,
    )
    if host is None or salary is None or target is None or fee is None or debt is None:
        raise ScoreUnavailableError("incomplete")
    if savings is None or profile.bank_or_wallet is None:
        raise ScoreUnavailableError("incomplete")
    interest = profile.debt_interest
    yearly = None
    if interest is not None:
        yearly = interest.rate_percent * (12 if interest.period == "month" else 1)
    return ScoreInputs(
        monthly_salary=to_host(salary, host, rates, per_month=True),
        remittance_target=to_host(target, host, rates, per_month=True),
        recruitment_fee=to_host(fee, host, rates, per_month=False),
        debt=to_host(debt, host, rates, per_month=False),
        savings=to_host(savings, host, rates, per_month=False),
        debt_rate_yearly_percent=yearly,
        account=profile.bank_or_wallet,
        essentials=essentials,
        fee_cap_months=cap_months,
    )
