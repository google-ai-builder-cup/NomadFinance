"""Schema for the curated cost-of-living baselines (data/source/cost-baselines/{host}.json).

Check your files:  python -m src.validators.cost_baselines
One file per host country, named after it (SG.json). The Firestore loader reuses `load_baseline`,
so files that pass here load. The Coach builds a worker's 90-day budget from these figures, so
every figure must name the page it was read from: nothing is written from memory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.config import COST_BASELINES_DIR

# The six host countries and the currency each baseline is written in (docs/data-model).
HOST_CURRENCY = {"SG": "SGD", "KR": "KRW", "MY": "MYR", "JP": "JPY", "HK": "HKD", "AU": "AUD"}
# The plan's budget lines are built from these five ids, so a missing or extra one is refused.
CATEGORIES = ("accommodation", "food", "transport", "phone_data", "mandatory_deductions")
JOB_TYPES = (
    "domestic_worker",
    "manufacturing_worker",
    "care_worker",
    "plantation_worker",
    "construction_worker",
    "working_holiday",
    "other",
)

MAX_NOTES = 320

_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_HTTPS = re.compile(r"^https://\S+$")
_INITIALS = re.compile(r"^[A-Z]{2,3}$")


def _filled(value: str) -> str:
    if value.strip().upper().startswith("TODO"):
        raise ValueError("still a TODO placeholder")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(_Strict):
    url: str
    publisher: str = Field(min_length=3)
    retrieved_on: date

    @field_validator("url")
    @classmethod
    def _https(cls, url: str) -> str:
        if not _HTTPS.match(url):
            raise ValueError(f"source {url!r} must be an https:// address")
        return url

    @field_validator("retrieved_on")
    @classmethod
    def _not_future(cls, day: date) -> date:
        if day > date.today():
            raise ValueError("retrieved_on is in the future")
        return day


class Band(_Strict):
    low: float = Field(ge=0)
    typical: float = Field(ge=0)
    high: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Band:
        if not self.low <= self.typical <= self.high:
            raise ValueError("needs low <= typical <= high")
        return self


class Figure(Band):
    unit: Literal["month", "one_off", "pct_of_wage"]
    by_job_type: dict[str, Band] | None = None
    notes: str | None = Field(default=None, min_length=10, max_length=MAX_NOTES)
    source: Source
    # A range sometimes needs a second page (the low end from one, the high end from another).
    other_sources: list[Source] | None = Field(default=None, min_length=1)
    curator: str

    @field_validator("notes")
    @classmethod
    def _no_placeholder(cls, value: str | None) -> str | None:
        return value if value is None else _filled(value)

    @field_validator("curator")
    @classmethod
    def _initials(cls, value: str) -> str:
        if not _INITIALS.match(value):
            raise ValueError("curator must be the curator's initials, 2 or 3 capital letters")
        return value

    @field_validator("by_job_type")
    @classmethod
    def _job_types(cls, value: dict[str, Band] | None) -> dict[str, Band] | None:
        unknown = sorted(set(value or {}) - set(JOB_TYPES))
        if unknown:
            raise ValueError(f"unknown job type(s) {unknown}")
        return value

    @model_validator(mode="after")
    def _checks(self) -> Figure:
        if self.unit == "pct_of_wage" and self.high > 100:
            raise ValueError("a share of wage cannot be above 100")
        # A zero is a finding ("employer pays", "no such deduction"), so it must say why.
        if self.high == 0 and not self.notes:
            raise ValueError("a figure of 0 needs a note that says why")
        return self


class CostBaseline(_Strict):
    """One host country: the unit the loader writes and versions."""

    host_country: str
    currency: str
    categories: dict[str, Figure]
    setup_costs: dict[str, Figure] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_whole(self) -> CostBaseline:
        if self.host_country not in HOST_CURRENCY:
            raise ValueError(f"host_country {self.host_country!r} is not one of the six hosts")
        if self.currency != HOST_CURRENCY[self.host_country]:
            raise ValueError(
                f"{self.host_country} is written in {HOST_CURRENCY[self.host_country]}"
            )
        if set(self.categories) != set(CATEGORIES):
            raise ValueError(f"categories must be exactly {list(CATEGORIES)}")
        for cat_id, figure in self.categories.items():
            ok = ("month", "pct_of_wage") if cat_id == "mandatory_deductions" else ("month",)
            if figure.unit not in ok:
                raise ValueError(f"{cat_id}: unit must be one of {list(ok)}")
            if cat_id == "mandatory_deductions" and not figure.notes:
                raise ValueError("mandatory_deductions needs a note on what is withheld")
        for cost_id, figure in self.setup_costs.items():
            if not _ID.match(cost_id):
                raise ValueError(f"setup cost id {cost_id!r} must be lowercase snake_case")
            if figure.unit != "one_off":
                raise ValueError(f"{cost_id}: a setup cost has unit one_off")
        return self


def load_baseline(path: Path) -> CostBaseline:
    """Read and validate one file; its name must be the host country it holds."""
    parsed = CostBaseline.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    if path.stem != parsed.host_country:
        raise ValueError(
            f"{path.name} holds {parsed.host_country}: name the file {parsed.host_country}.json"
        )
    return parsed


def load_baselines(
    directory: Path = COST_BASELINES_DIR, only: list[str] | None = None
) -> dict[str, CostBaseline]:
    """Validate the files of `directory` (or only the listed hosts) and return them by host."""
    if not directory.is_dir():
        raise ValueError(f"{directory} is not a folder")
    paths = (
        [directory / f"{host}.json" for host in only] if only else sorted(directory.glob("*.json"))
    )
    if not paths:
        raise ValueError(f"no baseline files in {directory}")
    missing = [p.name for p in paths if not p.is_file()]
    if missing:
        raise ValueError(f"missing file(s) {missing} in {directory}")
    return {p.stem: load_baseline(p) for p in paths}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the curated cost-baseline files.")
    parser.add_argument("--input-dir", type=Path, default=COST_BASELINES_DIR)
    parser.add_argument("--only", nargs="+", metavar="HOST", help="check only these hosts")
    args = parser.parse_args(argv)
    try:
        baselines = load_baselines(args.input_dir, args.only)
    except ValidationError as exc:
        print(f"FAIL {exc.error_count()} problem(s)")
        for err in exc.errors()[:25]:
            print(f"     {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        return 1
    except (ValueError, OSError) as exc:
        print(f"FAIL {exc}")
        return 1
    for host, baseline in baselines.items():
        print(
            f"OK   {host} {baseline.currency}: {len(baseline.categories)} categories, "
            f"{len(baseline.setup_costs)} setup cost(s)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
