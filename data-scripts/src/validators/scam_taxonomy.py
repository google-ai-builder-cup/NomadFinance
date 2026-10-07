"""Schema for the curated scam taxonomy (data/source/scam-taxonomy/types.json and tactics.json).

Check your files:  python -m src.validators.scam_taxonomy
The Firestore loader (NF-SA-001) reuses `load_taxonomy`, so files that pass here load. The text
is read by migrant workers and fed to the classifier as grounding, so it is held to plain
English (short sentences, no placeholders) and every entry must name a source: no claim is
written from memory.
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

from src.config import SCAM_TAXONOMY_DIR

# The starting ids from docs/data-model/collections/scam.md, plus `other_scam` so a real scam
# outside the list is not forced into a wrong type. Other tasks refer to these ids by name
# (patterns, golden sets, i18n keys), so a missing one must fail here, not later.
REQUIRED_TYPES = (
    "fake_job_offer",
    "illegal_recruitment_fee",
    "remittance_otp_phishing",
    "loan_app_trap",
    "authority_impersonation",
    "investment_romance",
    "lottery",
    "other_scam",
)
REQUIRED_TACTICS = ("urgency", "authority", "scarcity", "fear", "reciprocity", "social_proof")

_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_HTTPS = re.compile(r"^https://\S+$")
_INITIALS = re.compile(r"^[A-Z]{2,3}$")

# Plain-English limits: a long sentence or paragraph is not read on a phone by a tired worker.
MAX_DEFINITION = 260
MAX_SIGN = 130
MAX_RESPONSE = 400


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


class Entry(_Strict):
    """One scam type or one tactic. Fields of the other kind are rejected, not ignored."""

    label: str = Field(min_length=3, max_length=60)
    definition: str = Field(min_length=20, max_length=MAX_DEFINITION)
    signs: list[str] = Field(min_length=3, max_length=6)
    safe_response: str = Field(min_length=20, max_length=MAX_RESPONSE)
    how_it_works: str | None = Field(default=None, min_length=20, max_length=MAX_RESPONSE)
    related_tactics: list[str] | None = None
    default_risk: Literal["low", "medium", "high"] | None = None
    order: int = Field(ge=1)
    sources: list[Source] = Field(min_length=1)
    curator: str

    @field_validator("label", "definition", "safe_response", "how_it_works")
    @classmethod
    def _no_placeholder(cls, value: str | None) -> str | None:
        return value if value is None else _filled(value)

    @field_validator("signs")
    @classmethod
    def _signs(cls, signs: list[str]) -> list[str]:
        for sign in signs:
            _filled(sign)
            if not 5 <= len(sign) <= MAX_SIGN:
                raise ValueError(f"sign {sign!r} must be 5 to {MAX_SIGN} characters")
        if len({s.lower() for s in signs}) != len(signs):
            raise ValueError("signs must not repeat")
        return signs

    @field_validator("curator")
    @classmethod
    def _initials(cls, value: str) -> str:
        if not _INITIALS.match(value):
            raise ValueError("curator must be the curator's initials, 2 or 3 capital letters")
        return value


class TaxonomyFile(_Strict):
    kind: Literal["type", "tactic"]
    entries: dict[str, Entry] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_entries(self) -> TaxonomyFile:
        for entry_id, entry in self.entries.items():
            if not _ID.match(entry_id):
                raise ValueError(f"id {entry_id!r} must be lowercase snake_case")
            if self.kind == "type":
                if entry.default_risk is None:
                    raise ValueError(f"{entry_id}: a type needs default_risk")
                if entry.how_it_works is not None:
                    raise ValueError(f"{entry_id}: how_it_works belongs to tactics only")
            else:
                if entry.how_it_works is None:
                    raise ValueError(f"{entry_id}: a tactic needs how_it_works")
                if entry.default_risk is not None or entry.related_tactics is not None:
                    raise ValueError(f"{entry_id}: default_risk and related_tactics are for types")
        orders = [e.order for e in self.entries.values()]
        if len(set(orders)) != len(orders):
            raise ValueError("order must be different for every entry")
        return self


class Taxonomy(_Strict):
    """Both files together; the unit the loader writes and versions."""

    types: dict[str, Entry]
    tactics: dict[str, Entry]

    @model_validator(mode="after")
    def _check_whole(self) -> Taxonomy:
        clash = sorted(set(self.types) & set(self.tactics))
        if clash:
            raise ValueError(f"ids must be unique across types and tactics, repeated: {clash}")
        missing_types = [t for t in REQUIRED_TYPES if t not in self.types]
        if missing_types:
            raise ValueError(f"missing required type(s) {missing_types}")
        missing_tactics = [t for t in REQUIRED_TACTICS if t not in self.tactics]
        if missing_tactics:
            raise ValueError(f"missing required tactic(s) {missing_tactics}")
        for type_id, entry in self.types.items():
            unknown = [t for t in entry.related_tactics or [] if t not in self.tactics]
            if unknown:
                raise ValueError(f"{type_id}: related_tactics {unknown} are not tactics")
        return self


def load_file(path: Path, kind: Literal["type", "tactic"]) -> TaxonomyFile:
    """Read and validate one file; the file must hold the kind its name says."""
    parsed = TaxonomyFile.model_validate(json.loads(path.read_text(encoding="utf-8-sig")))
    if parsed.kind != kind:
        raise ValueError(f"{path.name} holds kind {parsed.kind!r}, expected {kind!r}")
    return parsed


def load_taxonomy(directory: Path = SCAM_TAXONOMY_DIR) -> Taxonomy:
    """Validate types.json and tactics.json together and return the whole taxonomy."""
    types = load_file(directory / "types.json", "type")
    tactics = load_file(directory / "tactics.json", "tactic")
    return Taxonomy(types=types.entries, tactics=tactics.entries)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the curated scam taxonomy files.")
    parser.add_argument("--input-dir", type=Path, default=SCAM_TAXONOMY_DIR)
    args = parser.parse_args(argv)
    try:
        taxonomy = load_taxonomy(args.input_dir)
    except ValidationError as exc:
        print(f"FAIL {exc.error_count()} problem(s)")
        for err in exc.errors()[:25]:
            print(f"     {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        return 1
    except (ValueError, OSError) as exc:
        print(f"FAIL {exc}")
        return 1
    print(f"OK   {len(taxonomy.types)} type(s), {len(taxonomy.tactics)} tactic(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
