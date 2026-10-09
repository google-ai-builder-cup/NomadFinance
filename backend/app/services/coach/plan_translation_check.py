"""Checks that a translated plan changed nothing but words (NF-FC-014).

The model translates the narrative only (`PlanTranslation`); the figures of a plan are never sent.
Two guarantees are checked in code before a translation is saved:

* the narrative: the same entries in the same order, and in every text the same numbers and
  currency codes, character for character (no digits of another script, none added or dropped);
* the plan: with the narrative taken out, the translated plan equals the English one.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter

from app.schemas.coach_plan import CoachPlan
from app.schemas.coach_plan_text import NoteText, PlanTranslation, WeekText

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
CODE = re.compile(r"\b(?:SGD|KRW|MYR|JPY|HKD|AUD|PHP|INR|IDR|NPR|BDT)\b")
LINK = re.compile(r"https?:|www\.|\.com\b|@", re.IGNORECASE)
# A translation is rarely more than a few times longer; far more is a runaway answer.
MAX_GROWTH = 4
MAX_PROBLEMS = 12


def narrative_of(plan: CoachPlan) -> PlanTranslation:
    """The text of a plan, in the shape the translator takes."""
    return PlanTranslation(
        summary=plan.summary,
        weeks=[WeekText(week=w.week, title=w.title, actions=list(w.actions)) for w in plan.weeks],
        warnings=[NoteText(id=w.id, text=w.text) for w in plan.warnings],
        checklist=[NoteText(id=c.id, text=c.text) for c in plan.checklist],
        disclaimer=plan.disclaimer,
    )


def apply_narrative(plan: CoachPlan, text: PlanTranslation) -> CoachPlan:
    """The plan with its sentences replaced and everything else untouched."""
    warnings = [
        w.model_copy(update={"text": n.text})
        for w, n in zip(plan.warnings, text.warnings, strict=True)
    ]
    checklist = [
        c.model_copy(update={"text": n.text})
        for c, n in zip(plan.checklist, text.checklist, strict=True)
    ]
    weeks = [
        w.model_copy(update={"title": t.title, "actions": t.actions})
        for w, t in zip(plan.weeks, text.weeks, strict=True)
    ]
    return plan.model_copy(
        update={
            "summary": text.summary,
            "weeks": weeks,
            "warnings": warnings,
            "checklist": checklist,
            "disclaimer": text.disclaimer,
        }
    )


def _tokens(text: str) -> Counter[str]:
    return Counter(NUMBER.findall(text)) + Counter(CODE.findall(text))


def _text_problems(source: str, target: str, where: str) -> list[str]:
    problems: list[str] = []
    if not target.strip():
        return [f"{where}: empty"]
    if _tokens(source) != _tokens(target):
        wanted = sorted(_tokens(source).elements())
        problems.append(f"{where}: numbers and currency codes must be exactly {wanted}")
    if any(unicodedata.category(c) == "Nd" and c not in "0123456789" for c in target):
        problems.append(f"{where}: use the digits 0 to 9 only")
    if LINK.search(target) and not LINK.search(source):
        problems.append(f"{where}: no links or addresses")
    if len(target) > MAX_GROWTH * len(source) + 80:
        problems.append(f"{where}: far longer than the English")
    return problems


def check_translation(source: PlanTranslation, target: PlanTranslation) -> list[str]:
    """Everything wrong with a translation; empty when it can be saved."""
    problems = _text_problems(source.summary, target.summary, "summary")
    problems += _text_problems(source.disclaimer, target.disclaimer, "disclaimer")
    if [w.week for w in target.weeks] != [w.week for w in source.weeks]:
        problems.append("weeks: the same week numbers in the same order")
    else:
        for src_week, got_week in zip(source.weeks, target.weeks, strict=True):
            where = f"week {src_week.week}"
            problems += _text_problems(src_week.title, got_week.title, where)
            if len(got_week.actions) != len(src_week.actions):
                problems.append(f"{where}: {len(src_week.actions)} actions, as in the English")
                continue
            for english, translated in zip(src_week.actions, got_week.actions, strict=True):
                problems += _text_problems(english, translated, where)
    for name, src_notes, got_notes in (
        ("warnings", source.warnings, target.warnings),
        ("checklist", source.checklist, target.checklist),
    ):
        if [n.id for n in got_notes] != [n.id for n in src_notes]:
            problems.append(f"{name}: the same ids in the same order")
            continue
        for note, got in zip(src_notes, got_notes, strict=True):
            problems += _text_problems(note.text, got.text, f"{name} {note.id}")
    return problems[:MAX_PROBLEMS]


def figures_fingerprint(plan: CoachPlan) -> str:
    """The plan with every sentence taken out, as canonical JSON: all that must not change."""
    data = plan.model_dump(mode="json")
    data.pop("summary")
    data.pop("disclaimer")
    for week in data["weeks"]:
        week.pop("title")
        week.pop("actions")
    for note in data["warnings"] + data["checklist"]:
        note.pop("text")
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def same_figures(english: CoachPlan, translated: CoachPlan) -> bool:
    """Every figure, date, id, severity and week of the two plans is byte-identical."""
    return figures_fingerprint(english) == figures_fingerprint(translated)
