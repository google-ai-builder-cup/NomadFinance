"""Schema for the demo radar reports (data/seed/radar-reports/seed_reports.json, NF-P3-005).

Check the file:  python -m src.validators.radar_seed
The loader reuses SeedFile, so a file that passes here loads. The value lists mirror
backend/app/schemas/radar.py and the corridor list mirrors src/config.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import CORRIDORS, RADAR_SEED_FILE
from src.validators.labor_law import COUNTRIES

EntityType = Literal["money_transfer_operator", "recruitment_agency", "employer"]
ViolationType = Literal[
    "hidden_fees",
    "exchange_rate_markup",
    "illegal_recruitment_fee",
    "wage_theft",
    "illegal_deduction",
    "contract_substitution",
    "passport_retention",
    "unlicensed_operator",
    "other",
]
Language = Literal["en", "hi", "tl", "id", "ne", "bn"]

CORRIDOR_IDS = tuple(c.corridor_id for c in CORRIDORS)
_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MIN_REPORTS, MAX_REPORTS = 15, 20  # the tracker asks for 15-20


class SeedReport(BaseModel):
    """One demo report as written in the file (no timestamps: the loader adds them)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^seed_[a-z0-9_]+$")
    cluster_id: str
    entity_name: str = Field(min_length=2)
    entity_slug: str
    entity_type: EntityType
    corridor_id: str | None = None
    host_country: str
    violation_type: ViolationType
    language: Language
    hours_ago: int = Field(ge=1)
    description: str = Field(min_length=10)

    @model_validator(mode="after")
    def _check(self) -> SeedReport:
        if not _SLUG.match(self.entity_slug):
            raise ValueError(f"entity_slug {self.entity_slug!r} is not a lowercase hyphen slug")
        if self.corridor_id is not None and self.corridor_id not in CORRIDOR_IDS:
            raise ValueError(f"corridor_id {self.corridor_id!r} is not one of {CORRIDOR_IDS}")
        if self.host_country not in COUNTRIES:
            raise ValueError(f"host_country {self.host_country!r} is not one of {COUNTRIES}")
        if self.corridor_id and self.corridor_id.split("-")[0] != self.host_country:
            raise ValueError("host_country must be the corridor's sending country")
        return self


class SeedFile(BaseModel):
    """The whole file: cross-report rules live here."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(alias="_comment", default="")
    reports: list[SeedReport]

    @model_validator(mode="after")
    def _check(self) -> SeedFile:
        ids = [r.id for r in self.reports]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate report ids")
        if not MIN_REPORTS <= len(ids) <= MAX_REPORTS:
            raise ValueError(f"expected {MIN_REPORTS}-{MAX_REPORTS} reports, found {len(ids)}")
        by_id = {r.id: r for r in self.reports}
        for report in self.reports:
            head = by_id.get(report.cluster_id)
            if head is None:
                raise ValueError(f"{report.id}: cluster_id {report.cluster_id} is not a report id")
            if head.cluster_id != head.id or head.entity_slug != report.entity_slug:
                raise ValueError(f"{report.id}: cluster must start at a report of the same entity")
        names: dict[str, tuple[str, str]] = {}
        for report in self.reports:
            if names.setdefault(report.entity_slug, (report.entity_name, report.entity_type)) != (
                report.entity_name,
                report.entity_type,
            ):
                raise ValueError(f"{report.entity_slug}: name or type differs between reports")
        missing = set(CORRIDOR_IDS) - {r.corridor_id for r in self.reports}
        if missing:
            raise ValueError(f"no report on corridor(s) {sorted(missing)}: the heatmap has a gap")
        return self


def load(path: Path = RADAR_SEED_FILE) -> SeedFile:
    """Read and validate the seed file; raises ValidationError, ValueError or OSError."""
    return SeedFile.model_validate(json.loads(path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the demo radar reports file.")
    parser.add_argument("--input", type=Path, default=RADAR_SEED_FILE)
    args = parser.parse_args(argv)
    try:
        parsed = load(args.input)
    except ValidationError as exc:
        for err in exc.errors():
            print(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(f"{args.input.name}: {exc}", file=sys.stderr)
        return 1
    print(f"OK: {len(parsed.reports)} reports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
