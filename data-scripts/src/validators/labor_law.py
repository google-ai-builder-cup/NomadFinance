"""Schema for the curated labor-law files (data/source/labor-laws/<CC>.json) and a checker.

Check your file:      python -m src.validators.labor_law
Start a new country:  python -m src.validators.labor_law --template JP --output <path>/JP.json
The Firestore loader (NF-P1-018) reuses LaborLawFile, so a file that passes here loads.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.config import LABOR_LAWS_DIR

COUNTRIES = ("SG", "KR", "MY", "JP", "HK", "AU")

# Same values as users.job_type in docs/data-model/collections/users.md.
JOB_TYPES = (
    "domestic_worker",
    "manufacturing_worker",
    "care_worker",
    "plantation_worker",
    "construction_worker",
    "working_holiday",
    "other",
)

# Document ids under labor_laws/{country}/rules; keep in step with the table in
# docs/data-model/collections/labor_laws.md (a test compares the two).
CATEGORY_IDS = (
    "minimum_wage",
    "working_hours",
    "overtime_pay",
    "rest_days_and_holidays",
    "annual_leave",
    "sick_leave",
    "salary_payment",
    "salary_deductions",
    "termination_notice",
    "early_termination",
    "recruitment_fees",
    "passport_retention",
    "accommodation",
    "insurance_and_injury",
    "social_security",
)

Coverage = Literal["regulated", "partly_regulated", "not_regulated", "unclear"]
Confidence = Literal["high", "medium", "low"]
Period = Literal["hour", "day", "week", "month", "year", "once"]


def _filled(value: str) -> str:
    # The template is full of TODO markers; a file that still has one is not finished.
    if value.strip().upper().startswith("TODO"):
        raise ValueError("still a TODO placeholder")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Limit(_Strict):
    """A number a contract clause can be compared with."""

    value: float
    unit: str = Field(min_length=1)
    period: Period | None = None
    note: str | None = None


class Reference(_Strict):
    """Where a rule comes from. Official texts only; add the NATLEX record when you have it."""

    law: str = Field(min_length=3)
    section: str = Field(min_length=1)
    url: str = Field(pattern=r"^https?://\S+$")
    year: int | None = Field(default=None, ge=1800, le=2100)
    in_force_since: date | None = None
    natlex_isn: str | None = None

    _law_filled = field_validator("law", "section")(_filled)


class IlostatCheck(_Strict):
    indicator: str = Field(min_length=1)
    value: float
    checked_on: date


class Variant(_Strict):
    """The rule for one group of workers. A job-type variant overrides the `all` variant."""

    applies_to: list[str] = Field(min_length=1)
    requirements: list[str] = Field(min_length=1)
    limits: dict[str, Limit] = Field(default_factory=dict)
    penalty: str | None = None
    enforced_by: str | None = None

    @field_validator("applies_to")
    @classmethod
    def _check_groups(cls, groups: list[str]) -> list[str]:
        unknown = [g for g in groups if g != "all" and g not in JOB_TYPES]
        if unknown:
            raise ValueError(f"unknown worker group {unknown}; use 'all' or one of {JOB_TYPES}")
        if len(set(groups)) != len(groups):
            raise ValueError("duplicate worker group")
        if "all" in groups and len(groups) > 1:
            raise ValueError("'all' cannot be combined with job types; use a separate variant")
        return groups

    @field_validator("requirements")
    @classmethod
    def _check_requirements(cls, items: list[str]) -> list[str]:
        for item in items:
            _filled(item)
            if len(item.strip()) < 15:
                raise ValueError(f"requirement too short to be useful: {item!r}")
        return items


class Rule(_Strict):
    coverage: Coverage
    title: str = Field(min_length=3)
    summary: str = Field(min_length=20, max_length=800)
    variants: list[Variant] = Field(min_length=1)
    references: list[Reference] = Field(min_length=1)
    ilostat_check: IlostatCheck | None = None
    confidence: Confidence
    notes: str | None = None
    last_verified_on: date

    _title_filled = field_validator("title", "summary")(_filled)

    @model_validator(mode="after")
    def _check_rule(self) -> Rule:
        seen: list[str] = []
        for variant in self.variants:
            seen.extend(variant.applies_to)
        duplicates = sorted(g for g, n in Counter(seen).items() if n > 1)
        if duplicates:
            raise ValueError(f"worker group in more than one variant: {duplicates}")
        if self.coverage == "unclear" and self.confidence != "low":
            raise ValueError("coverage 'unclear' needs confidence 'low'")
        return self


class LaborLawFile(_Strict):
    country: Literal["SG", "KR", "MY", "JP", "HK", "AU"]
    name: str = Field(min_length=2)
    curated_by: list[str] = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    last_verified_on: date
    notes: str | None = None
    rules: dict[str, Rule]

    @model_validator(mode="after")
    def _check_categories(self) -> LaborLawFile:
        missing = [c for c in CATEGORY_IDS if c not in self.rules]
        extra = sorted(set(self.rules) - set(CATEGORY_IDS))
        if missing or extra:
            raise ValueError(f"need exactly the 15 categories; missing {missing}, extra {extra}")
        return self


def load(path: Path) -> LaborLawFile:
    """Read and validate one country file; the file name must match its country code."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    parsed = LaborLawFile.model_validate(data)
    if path.stem != parsed.country:
        raise ValueError(f"{path.name} contains country {parsed.country}")
    return parsed


def template(country: str) -> dict[str, object]:
    """A skeleton with every category present and every value a TODO marker."""
    rule: dict[str, object] = {
        "coverage": "TODO regulated | partly_regulated | not_regulated | unclear",
        "title": "TODO short title",
        "summary": "TODO the rule in plain English for a worker, 1 to 3 sentences",
        "variants": [
            {
                "applies_to": ["all"],
                "requirements": ["TODO one obligation per item, with the article number"],
                "limits": {},
                "penalty": None,
                "enforced_by": None,
            }
        ],
        "references": [
            {"law": "TODO name of the law", "section": "TODO articles", "url": "https://TODO"}
        ],
        "ilostat_check": None,
        "confidence": "TODO high | medium | low",
        "notes": None,
        "last_verified_on": "TODO YYYY-MM-DD",
    }
    return {
        "country": country,
        "name": "TODO country name",
        "curated_by": ["TODO your name"],
        "reviewed_by": [],
        "last_verified_on": "TODO YYYY-MM-DD",
        "notes": None,
        "rules": {category: json.loads(json.dumps(rule)) for category in CATEGORY_IDS},
    }


def _describe(parsed: LaborLawFile) -> str:
    coverage = Counter(r.coverage for r in parsed.rules.values())
    confidence = Counter(r.confidence for r in parsed.rules.values())
    variants = sum(len(r.variants) for r in parsed.rules.values())
    refs = sum(len(r.references) for r in parsed.rules.values())
    return (
        f"{len(parsed.rules)} rules, {variants} variants, {refs} references | "
        f"coverage {dict(coverage)} | confidence {dict(confidence)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check curated labor-law files.")
    parser.add_argument("paths", nargs="*", type=Path, help="files to check (default: all six)")
    parser.add_argument("--template", metavar="CC", choices=COUNTRIES, help="print a skeleton file")
    parser.add_argument("--output", type=Path, help="write the template here instead of printing")
    parser.add_argument("--force", action="store_true", help="overwrite an already curated file")
    parser.add_argument("--require-all", action="store_true", help="fail on files not curated yet")
    args = parser.parse_args(argv)

    if args.template:
        text = json.dumps(template(args.template), indent=2, ensure_ascii=False) + "\n"
        if args.output is None:
            print(text, end="")
            return 0
        if args.output.exists() and not args.force:
            if json.loads(args.output.read_text(encoding="utf-8-sig")) != {}:
                print(f"REFUSED {args.output}: already has content; use --force to replace it")
                return 1
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote template to {args.output}")
        return 0

    status = 0
    for path in args.paths or sorted(LABOR_LAWS_DIR.glob("*.json")):
        try:
            if json.loads(path.read_text(encoding="utf-8-sig")) == {}:
                print(f"SKIP {path.name}: not curated yet")
                status |= 1 if args.require_all else 0
                continue
            print(f"OK   {path.name}: {_describe(load(path))}")
        except ValidationError as exc:
            status = 1
            print(f"FAIL {path.name}: {exc.error_count()} problem(s)")
            for err in exc.errors()[:25]:
                print(f"     {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        except (ValueError, OSError) as exc:
            status = 1
            print(f"FAIL {path.name}: {exc}")
    return status


if __name__ == "__main__":
    sys.exit(main())
