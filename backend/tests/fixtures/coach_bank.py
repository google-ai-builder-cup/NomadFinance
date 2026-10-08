"""Shared by the Coach question bank tests (NF-FC-001): the file, and ways to edit a copy of it."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import app.services.coach.question_bank as question_bank
from app.schemas.coach_profile import parse_slot_value
from app.schemas.coach_questions import QuestionBank

DATA_FILE = Path(question_bank.__file__).with_name("question_bank.json")
# A fixed day, so a range test never depends on the clock.
TODAY = date(2026, 10, 8)


def raw() -> dict[str, Any]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def build(change: Callable[[dict[str, Any]], object]) -> QuestionBank:
    """The bank as it would be if `change` were made to a copy of the file."""
    data = copy.deepcopy(raw())
    change(data)
    return QuestionBank.model_validate(data)


def question(data: dict[str, Any], slot: str) -> dict[str, Any]:
    return next(item for item in data["questions"] if item["slot"] == slot)


def money(amount: float, currency: str = "SGD", period: str = "month") -> Any:
    return parse_slot_value(
        "monthly_salary" if period != "once" else "savings",
        {"amount": amount, "currency": currency, "period": period},
    )
