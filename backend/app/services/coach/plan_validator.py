"""Checks that a plan holds no figure that cannot be worked out from the inputs (NF-FC-012).

Two checks, neither using a model:

* the sentences: every number the model wrote must be a number it was given (`build_facts`), to
  the precision it wrote it, and every amount must be one of the money facts. A made-up fee, a
  helpline number or a sum of two facts is rejected;
* the figures: the plan's budget, goals, remittance, debt and emergency fund must equal what
  `compute_figures` gives, so a plan edited after it was made (or a bug) is caught.
"""

from __future__ import annotations

import math
import re
from typing import Any

from app.schemas.coach_plan import CoachPlan
from app.schemas.coach_plan_text import NoteText, PlanText
from app.services.coach.plan_figures import PlanFigures

PLAN_WEEKS = 13
MAX_SUMMARY_CHARS = 700
MAX_TITLE_CHARS = 80
MAX_TEXT_CHARS = 260
# Numbers any sentence may use about the plan's own shape: the weeks, and the 30/60/90-day marks.
STRUCTURE = frozenset({*range(0, PLAN_WEEKS + 1), 30, 60, 90})
# Facts that are counts or times, not money. Everything else numeric in the facts is an amount.
COUNT_KEYS = frozenset(
    {
        "dependents",
        "months_to_clear",
        "months_of_costs",
        "weeks_to_target",
        "send_in_weeks",
        "total",
        "arrival_week",
        "first_pay_week",
    }
)
CURRENCY = (
    r"(?:SGD|KRW|MYR|JPY|HKD|AUD|PHP|INR|IDR|NPR|BDT|"
    r"dollars?|pesos?|rupees?|rupiah|ringgit|yen|won)"
)
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:,\d+)*(?:\.\d+)?)")
_AFTER_CURRENCY = re.compile(rf"\s?{CURRENCY}\b", re.IGNORECASE)
_BEFORE_CURRENCY = re.compile(rf"(?:{CURRENCY}\s?|[$€£₹₱¥]\s?)$", re.IGNORECASE)
_SCALE = re.compile(r"\b(?:thousand|million|billion|lakh|crore)s?\b", re.IGNORECASE)
_LINK = re.compile(r"https?:|www\.|\.com\b|@", re.IGNORECASE)
_PERCENT_WORD = re.compile(r"\s?(?:%|percent\b|per cent\b)", re.IGNORECASE)
# A plan never recommends borrowing, a lender, an investment or a product (the prompt says so;
# this catches the common ways a model still does). NF-FC-013 holds the wider guardrails.
_ADVICE = re.compile(
    r"\b(?:borrow\w*|invest\w*|insurance|(?:new|another|safer|cheaper|better|different|"
    r"get\s+a|take\s+(?:out\s+)?a|apply\s+for\s+a)\s+(?:\w+\s+)?(?:loan|lender|credit))\b",
    re.IGNORECASE,
)


class Numbers:
    """The numbers a plan's sentences may use, sorted by what they are."""

    def __init__(self, facts: dict[str, Any]) -> None:
        self.money: list[float] = []
        self.counts: set[float] = set()
        self.percents: list[float] = []
        self._walk(facts, "")

    def _walk(self, node: Any, key: str) -> None:
        if isinstance(node, dict):
            for name, value in node.items():
                self._walk(value, str(name))
        elif isinstance(node, list):
            for value in node:
                self._walk(value, key)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            if "percent" in key:
                self.percents.append(float(node))
            elif key in COUNT_KEYS:
                self.counts.add(float(node))
            else:
                self.money.append(float(node))
        elif isinstance(node, str):
            self.counts.update(float(n) for n in re.findall(r"\d+", node))


def _agrees(figure: float, written: float, decimals: int) -> bool:
    """`written` is `figure` rounded (or cut) to the `decimals` it was written with."""
    scale = 10**decimals
    rounded = math.floor(abs(figure) * scale + 0.5 + 1e-9) / scale
    cut = math.floor(abs(figure) * scale + 1e-9) / scale
    return bool(abs(written - rounded) < 1e-9 or abs(written - cut) < 1e-9)


def _any_agrees(figures: list[float], written: float, decimals: int) -> bool:
    return any(_agrees(figure, written, decimals) for figure in figures)


def number_problems(text: str, numbers: Numbers, where: str) -> list[str]:
    """Why `text` holds a number that was not given, if it does."""
    problems: list[str] = []
    for match in _NUMBER.finditer(text):
        raw = match.group(1)
        written = float(raw.replace(",", ""))
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        after = text[match.end() : match.end() + 12]
        before = text[max(0, match.start() - 6) : match.start()]
        if _PERCENT_WORD.match(after):
            ok = _any_agrees(numbers.percents, written, decimals)
        elif _AFTER_CURRENCY.match(after) or _BEFORE_CURRENCY.search(before):
            ok = _any_agrees(numbers.money, written, decimals)
        else:
            ok = (
                written in numbers.counts
                or (decimals == 0 and int(written) in STRUCTURE)
                or _any_agrees(numbers.money, written, decimals)
            )
        if not ok:
            problems.append(f"{where}: the number {raw} is not one of the given facts")
    if _SCALE.search(text):
        problems.append(f"{where}: write numbers in digits, never with thousand or million")
    if _LINK.search(text):
        problems.append(f"{where}: no links or addresses")
    if _ADVICE.search(text):
        problems.append(
            f"{where}: never suggest borrowing, a loan, a lender, insurance or investing"
        )
    return problems


def _notes(notes: list[NoteText], wanted: list[str], what: str) -> list[str]:
    found = [note.id for note in notes]
    problems = []
    if sorted(found) != sorted(wanted):
        problems.append(f"{what}: ids must be exactly {wanted}, got {found}")
    problems += [f"{what} {n.id}: empty or too long" for n in notes if not 0 < len(n.text) <= 260]
    return problems


def check_text(
    text: PlanText, facts: dict[str, Any], warning_ids: list[str], checklist_ids: list[str]
) -> list[str]:
    """Everything wrong with the model's sentences; empty when they can be used."""
    numbers = Numbers(facts)
    problems: list[str] = []
    if not 0 < len(text.summary) <= MAX_SUMMARY_CHARS:
        problems.append("summary: empty or too long")
    problems += number_problems(text.summary, numbers, "summary")
    if [week.week for week in text.weeks] != list(range(1, PLAN_WEEKS + 1)):
        problems.append("weeks: exactly weeks 1 to 13, in order")
    for week in text.weeks:
        where = f"week {week.week}"
        if not 0 < len(week.title) <= MAX_TITLE_CHARS:
            problems.append(f"{where}: title empty or too long")
        if not 1 <= len(week.actions) <= 4:
            problems.append(f"{where}: one to four actions")
        problems += number_problems(week.title, numbers, where)
        for action in week.actions:
            if not 0 < len(action) <= MAX_TEXT_CHARS:
                problems.append(f"{where}: an action is empty or too long")
            problems += number_problems(action, numbers, where)
    problems += _notes(text.warnings, warning_ids, "warnings")
    problems += _notes(text.checklist, checklist_ids, "checklist")
    for note in [*text.warnings, *text.checklist]:
        problems += number_problems(note.text, numbers, f"note {note.id}")
    return problems[:12]


def check_figures(plan: CoachPlan, expected: PlanFigures) -> list[str]:
    """Whether the plan's figures are the ones worked out from the inputs."""
    pairs = [
        ("monthly_budget", plan.monthly_budget, expected.budget),
        ("remittance", plan.remittance, expected.remittance),
        ("debt", plan.debt, expected.debt),
        ("emergency_fund", plan.emergency_fund, expected.emergency_fund),
    ]
    differs = [name for name, got, want in pairs if got != want]
    return [f"{name} differs from the worked-out figures" for name in differs]
