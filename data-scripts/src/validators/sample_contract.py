"""Schema for the demo sample contracts (data/seed/contracts/manifest.json, NF-P3-020).

Check the files:  python -m src.validators.sample_contract
The uploader reuses Manifest, so a set that passes here uploads. The value lists mirror
backend/app/schemas/contract.py and backend/app/schemas/contract_compare.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import RADAR_SEED_FILE, SEED_CONTRACTS_DIR
from src.validators.labor_law import COUNTRIES
from src.validators.radar_seed import load as load_radar_seed

JobType = Literal[
    "domestic_worker",
    "manufacturing_worker",
    "care_worker",
    "plantation_worker",
    "construction_worker",
    "working_holiday",
    "other",
]
Category = Literal[
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
    "other",
]
Risk = Literal["caution", "danger"]
Overall = Literal["fair", "mixed", "risky"]
Language = Literal["en", "hi", "tl", "id", "ne", "bn"]

MAX_PDF_BYTES = 1_000_000  # a demo laptop uploads these live; keep them small
_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class PlantedIssue(BaseModel):
    """One problem the contract text was written to contain."""

    model_config = ConfigDict(extra="forbid")

    clause: str = Field(pattern=r"^\d+$")
    category: Category
    risk: Risk


class SampleContract(BaseModel):
    """One contract's entry in the manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z]{2}_[a-z_]+$")
    file: str = Field(pattern=r"^[a-z_]+\.pdf$")
    country: str
    job_type: JobType
    worker_language: Language
    worker: str = Field(min_length=3)
    employer: str = Field(min_length=3)
    agency: str | None
    radar_entity_slug: str | None
    overall: Overall
    demo_note: str = Field(min_length=10)
    planted_issues: list[PlantedIssue] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> SampleContract:
        if self.country not in COUNTRIES:
            raise ValueError(f"country {self.country!r} is not one of {COUNTRIES}")
        if self.file != f"{self.id}.pdf" or not self.id.startswith(self.country.lower() + "_"):
            raise ValueError(f"{self.id}: id must be <country>_<name> and the file <id>.pdf")
        if self.radar_entity_slug and not _SLUG.match(self.radar_entity_slug):
            raise ValueError(f"{self.id}: radar_entity_slug is not a lowercase hyphen slug")
        dangers = sum(1 for i in self.planted_issues if i.risk == "danger")
        # The three labels are only useful for rehearsal if they mean different things.
        expected = {"fair": dangers == 0, "mixed": 1 <= dangers <= 2, "risky": dangers >= 3}
        if not expected[self.overall]:
            raise ValueError(f"{self.id}: {dangers} danger issue(s) do not fit {self.overall!r}")
        return self


class Manifest(BaseModel):
    """The whole file: one contract per host country."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(alias="_comment", default="")
    contracts: list[SampleContract]

    @model_validator(mode="after")
    def _check(self) -> Manifest:
        countries = [c.country for c in self.contracts]
        if sorted(countries) != sorted(COUNTRIES):
            raise ValueError(f"need exactly one contract per host country {COUNTRIES}")
        if len({c.id for c in self.contracts}) != len(self.contracts):
            raise ValueError("duplicate contract ids")
        if not {"fair", "mixed", "risky"} <= {c.overall for c in self.contracts}:
            raise ValueError("the set needs at least one fair, one mixed and one risky contract")
        return self


def load(directory: Path = SEED_CONTRACTS_DIR) -> Manifest:
    """Read the manifest and check every file it names; raises ValidationError or ValueError."""
    manifest = Manifest.model_validate(
        json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    )
    radar_slugs = {r.entity_slug for r in load_radar_seed(RADAR_SEED_FILE).reports}
    for contract in manifest.contracts:
        pdf = directory / contract.file
        if not pdf.is_file():
            raise ValueError(f"{contract.id}: {contract.file} is missing")
        data = pdf.read_bytes()
        if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-32:]:
            raise ValueError(f"{contract.file} is not a complete PDF")
        if len(data) > MAX_PDF_BYTES:
            raise ValueError(f"{contract.file} is {len(data)} bytes; the limit is {MAX_PDF_BYTES}")
        text = (directory / "source" / f"{contract.id}.txt").read_text(encoding="utf-8")
        for issue in contract.planted_issues:
            if not re.search(rf"^{issue.clause}\. ", text, re.MULTILINE):
                raise ValueError(f"{contract.id}: clause {issue.clause} is not in the text")
        if contract.radar_entity_slug and contract.radar_entity_slug not in radar_slugs:
            raise ValueError(
                f"{contract.id}: {contract.radar_entity_slug} is not in the radar seed"
            )
    listed = {c.file for c in manifest.contracts}
    extra = {p.name for p in directory.glob("*.pdf")} - listed
    if extra:
        raise ValueError(f"PDF(s) not in the manifest: {sorted(extra)}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the demo sample contracts.")
    parser.add_argument("--input-dir", type=Path, default=SEED_CONTRACTS_DIR)
    args = parser.parse_args(argv)
    try:
        manifest = load(args.input_dir)
    except ValidationError as exc:
        for err in exc.errors():
            print(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}", file=sys.stderr)
        return 1
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for c in manifest.contracts:
        print(f"{c.country}  {c.overall:<5}  {c.file}  ({len(c.planted_issues)} planted issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
