"""Schema for the curated complaint-template files (data/source/complaint-templates/<CC>.json).

Check your files:  python -m src.validators.complaint_template
The Firestore loader (NF-P2-006) reuses ComplaintTemplateFile, so a file that passes here loads.
A template is the fixed frame of a complaint letter plus who to send it to, so a wrong phone
number or address here sends a worker to the wrong place: authority details must be read from
the authority's own website and the pages listed in `sources`.
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

from src.config import COMPLAINT_TEMPLATES_DIR
from src.validators.labor_law import CATEGORY_IDS, COUNTRIES

# Languages the letters are written in: the language each authority works in. Keep in step with
# LetterLanguage in backend/app/schemas/contract_complaint.py (a backend test compares them).
LETTER_LANGUAGES = ("en", "ko", "ms", "ja")

# Template ids: one per labor-law category, plus `general` for any violation without its own.
TYPE_IDS = ("general", *CATEGORY_IDS)

# The values the letter step can fill in (contract/complaint.v2). A marker outside this list
# would reach the worker unfilled. Keep in step with the backend test that checks the files.
PLACEHOLDERS = (
    "authority_name",
    "worker_name",
    "worker_contact",
    "employer_name",
    "contract_details",
    "violation_summary",
)
REQUIRED_PLACEHOLDERS = ("authority_name", "violation_summary")

_MARKER = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[0-9][0-9 ()\-]{2,24}$")
_HTTPS = re.compile(r"^https://\S+$")


def _filled(value: str) -> str:
    if value.strip().upper().startswith("TODO"):
        raise ValueError("still a TODO placeholder")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Channel(_Strict):
    """One way to reach the authority."""

    kind: Literal["web", "email", "phone", "post"]
    value: str = Field(min_length=3)
    note: str | None = None

    @model_validator(mode="after")
    def _check_value(self) -> Channel:
        _filled(self.value)
        rules = {"web": _HTTPS, "email": _EMAIL, "phone": _PHONE}
        pattern = rules.get(self.kind)
        if pattern is not None and not pattern.match(self.value):
            raise ValueError(f"{self.value!r} is not a valid {self.kind} value")
        return self


class TemplateType(_Strict):
    authority_name: str = Field(min_length=3)
    authority_url: str | None = None
    channels: list[Channel] = Field(min_length=1)
    letter_language: Literal["en", "ko", "ms", "ja"]
    template_text: str = Field(min_length=100)
    placeholders: list[str] = Field(min_length=1)
    reviewed_on: date

    _filled_text = field_validator("authority_name", "template_text")(_filled)

    @field_validator("authority_url")
    @classmethod
    def _https_url(cls, url: str | None) -> str | None:
        if url is not None and not _HTTPS.match(url):
            raise ValueError("authority_url must be an https:// address")
        return url

    @field_validator("reviewed_on")
    @classmethod
    def _not_future(cls, day: date) -> date:
        if day > date.today():
            raise ValueError("reviewed_on is in the future")
        return day

    @model_validator(mode="after")
    def _check_placeholders(self) -> TemplateType:
        # {{name}} exactly: no spaces, so the letter step and this check see the same markers.
        found = [m.strip() for m in _MARKER.findall(self.template_text)]
        raw = _MARKER.findall(self.template_text)
        if raw != found:
            raise ValueError("write markers as {{name}}, with no spaces inside the braces")
        unknown = sorted(set(found) - set(PLACEHOLDERS))
        if unknown:
            raise ValueError(f"unknown placeholder(s) {unknown}; use only {list(PLACEHOLDERS)}")
        missing = [name for name in REQUIRED_PLACEHOLDERS if name not in found]
        if missing:
            raise ValueError(f"template_text must contain {missing}")
        if sorted(set(found)) != sorted(self.placeholders) or len(set(self.placeholders)) != len(
            self.placeholders
        ):
            raise ValueError(
                f"placeholders {sorted(self.placeholders)} must list each marker used in "
                f"template_text exactly once: {sorted(set(found))}"
            )
        return self


class ComplaintTemplateFile(_Strict):
    country: Literal["SG", "KR", "MY", "JP", "HK", "AU"]
    curated_by: list[str] = Field(min_length=1)
    reviewed_by: list[str] = Field(default_factory=list)
    last_verified_on: date
    notes: str | None = None
    sources: list[str] = Field(min_length=1)
    types: dict[str, TemplateType]

    @field_validator("sources")
    @classmethod
    def _official_pages(cls, urls: list[str]) -> list[str]:
        for url in urls:
            if not _HTTPS.match(url):
                raise ValueError(f"source {url!r} must be an https:// address")
        return urls

    @model_validator(mode="after")
    def _check_types(self) -> ComplaintTemplateFile:
        extra = sorted(set(self.types) - set(TYPE_IDS))
        if extra:
            raise ValueError(f"unknown template type(s) {extra}; use 'general' or a category id")
        if "general" not in self.types:
            raise ValueError("a 'general' template is required: it covers every violation type")
        return self


def load(path: Path) -> ComplaintTemplateFile:
    """Read and validate one country file; the file name must match its country code."""
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    parsed = ComplaintTemplateFile.model_validate(data)
    if path.stem != parsed.country:
        raise ValueError(f"{path.name} contains country {parsed.country}")
    return parsed


def _describe(parsed: ComplaintTemplateFile) -> str:
    general = parsed.types["general"]
    kinds = ", ".join(sorted({c.kind for c in general.channels}))
    return (
        f"{len(parsed.types)} template(s), letters in {general.letter_language}, "
        f"{len(general.channels)} channels ({kinds}), {len(parsed.sources)} sources"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check curated complaint-template files.")
    parser.add_argument("paths", nargs="*", type=Path, help="files to check (default: all six)")
    parser.add_argument("--require-all", action="store_true", help="fail if a country is missing")
    args = parser.parse_args(argv)

    status = 0
    paths = args.paths or sorted(COMPLAINT_TEMPLATES_DIR.glob("*.json"))
    if args.require_all and not args.paths:
        missing = [c for c in COUNTRIES if not (COMPLAINT_TEMPLATES_DIR / f"{c}.json").exists()]
        if missing:
            print(f"FAIL missing country file(s): {', '.join(missing)}")
            status = 1
    for path in paths:
        try:
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
