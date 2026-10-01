"""Financial Identity metrics (NF-P3-013): the four scores of `financial_profile/current`.

Pure functions over already-loaded entries, so every formula is testable without Firestore or
Gemini. Each metric is `{"score": 0..100 or None, "detail": {...}}`; a metric with no data has
`score: None` and a `reason`, never 0, so a missing log does not read as bad behaviour.

The formulas and constants below are this project's own choice (the design doc names the four
metrics but not how to compute them); none is calibrated against real lending outcomes.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from statistics import fmean, pstdev
from typing import Any, NamedTuple

MetricResult = dict[str, Any]
# Amount and currency in, amount in the reporting currency out; None when there is no rate.
Convert = Callable[[float, str], float | None]

# Current month plus the 11 before it.
WINDOW_MONTHS = 12
# Saving this share of income scores 100. A round number to make the score readable, not a
# standard from any lender.
SAVINGS_TARGET_RATE = 0.20


class Entry(NamedTuple):
    day: date
    data: dict[str, Any]


def window_start(today: date) -> date:
    index = today.year * 12 + today.month - 1 - (WINDOW_MONTHS - 1)
    return date(index // 12, index % 12 + 1, 1)


def entries_in_window(raw: list[tuple[str, dict[str, Any]]], today: date) -> list[Entry]:
    """Entries dated inside the window and not in the future; an unreadable date is dropped."""
    start = window_start(today)
    entries = []
    for _, data in raw:
        try:
            day = date.fromisoformat(str(data.get("entry_date")))
        except ValueError:
            continue
        if start <= day <= today:
            entries.append(Entry(day, data))
    return entries


def _month(day: date) -> int:
    return day.year * 12 + day.month - 1


def _months_in_period(first: date, today: date, active: set[int]) -> int:
    """Months from the metric's first entry to today. The running month is not counted
    against the worker until it has an entry: the 5th of the month is too early to say that
    no salary arrived."""
    total = _month(today) - _month(first) + 1
    if total > 1 and _month(today) not in active:
        total -= 1
    return total


def _no_data(reason: str) -> MetricResult:
    return {"score": None, "detail": {"reason": reason}}


def _converted(entries: list[Entry], convert: Convert) -> tuple[list[tuple[Entry, float]], int]:
    """Each entry with its amount in the reporting currency, and how many had no rate."""
    kept: list[tuple[Entry, float]] = []
    for entry in entries:
        amount = convert(float(entry.data["amount"]), str(entry.data.get("currency")))
        if amount is not None:
            kept.append((entry, amount))
    return kept, len(entries) - len(kept)


def income_stability(income: list[Entry], convert: Convert, today: date) -> MetricResult:
    """Months with income over months in the period, less how much monthly income varies."""
    if not income:
        return _no_data("no_income_entries")
    converted, excluded = _converted(income, convert)
    if not converted:
        return _no_data("no_income_in_a_convertible_currency")
    monthly: dict[int, float] = defaultdict(float)
    for entry, amount in converted:
        monthly[_month(entry.day)] += amount
    months = _months_in_period(min(e.day for e, _ in converted), today, set(monthly))
    coverage = min(len(monthly) / months, 1.0)
    values = list(monthly.values())
    variation = pstdev(values) / fmean(values) if len(values) > 1 else 0.0
    return {
        "score": round(100 * coverage * (1 - min(variation, 1.0))),
        "detail": {
            "months_with_income": len(monthly),
            "months_in_period": months,
            "mean_monthly_income": round(fmean(values), 2),
            "monthly_variation": round(variation, 3),
            "excluded_entries": excluded,
        },
    }


def savings_rate(income: list[Entry], savings: list[Entry], convert: Convert) -> MetricResult:
    """Net savings (deposits less withdrawals) as a share of income, against the target."""
    income_converted, income_excluded = _converted(income, convert)
    income_total = sum(amount for _, amount in income_converted)
    if income_total <= 0:
        return _no_data("no_income_in_a_convertible_currency")
    if not savings:
        return _no_data("no_savings_entries")
    savings_converted, savings_excluded = _converted(savings, convert)
    if not savings_converted:
        return _no_data("no_savings_in_a_convertible_currency")
    net = sum(
        amount if entry.data.get("direction") == "deposit" else -amount
        for entry, amount in savings_converted
    )
    rate = net / income_total
    share = max(0.0, min(rate / SAVINGS_TARGET_RATE, 1.0))
    return {
        "score": round(100 * share),
        "detail": {
            "income_total": round(income_total, 2),
            "net_savings": round(net, 2),
            "savings_rate": round(rate, 3),
            "target_rate": SAVINGS_TARGET_RATE,
            "excluded_entries": income_excluded + savings_excluded,
        },
    }


def remittance_consistency(transfers: list[Entry], convert: Convert, today: date) -> MetricResult:
    """Months with at least one transfer home over months since the first one."""
    if not transfers:
        return _no_data("no_transfers")
    active = {_month(t.day) for t in transfers}
    months = _months_in_period(min(t.day for t in transfers), today, active)
    received = [
        convert(float(t.data["receive_amount"]), str(t.data.get("receive_currency")))
        for t in transfers
    ]
    costs = [float(t.data["cost_pct"]) for t in transfers if t.data.get("cost_pct") is not None]
    return {
        "score": round(100 * min(len(active) / months, 1.0)),
        "detail": {
            "months_with_transfer": len(active),
            "months_in_period": months,
            "transfer_count": len(transfers),
            "total_received": round(sum(r for r in received if r is not None), 2),
            "average_cost_pct": round(fmean(costs), 2) if costs else None,
            "excluded_entries": sum(1 for r in received if r is None),
        },
    }


def bill_payment_reliability(bills: list[Entry]) -> MetricResult:
    """Paid bills over all logged bills."""
    if not bills:
        return _no_data("no_bills")
    paid = sum(1 for b in bills if b.data.get("paid") is True)
    return {
        "score": round(100 * paid / len(bills)),
        "detail": {
            "bills_total": len(bills),
            "bills_paid": paid,
            "bills_unpaid": len(bills) - paid,
        },
    }


def overall_score(metrics: dict[str, MetricResult]) -> int | None:
    """Plain average of the metrics that have a score; None when none has."""
    scores = [m["score"] for m in metrics.values() if m["score"] is not None]
    return round(fmean(scores)) if scores else None


def compute_metrics(
    income: list[Entry],
    transfers: list[Entry],
    bills: list[Entry],
    savings: list[Entry],
    convert: Convert,
    today: date,
) -> dict[str, MetricResult]:
    return {
        "income_stability": income_stability(income, convert, today),
        "savings_rate": savings_rate(income, savings, convert),
        "remittance_consistency": remittance_consistency(transfers, convert, today),
        "bill_payment_reliability": bill_payment_reliability(bills),
    }
