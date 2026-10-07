"""Schema and checks for the Scam Analyzer's golden eval sets (evals/scam_golden_*.jsonl).

Check your file:      python -m src.validators.scam_golden
Pick rows to review:  python -m src.validators.scam_golden --spot-check 10
Before merging:       python -m src.validators.scam_golden --require-reviewed 10

One line per message, with the label a correct analyzer should give. The eval runner (NF-SA-014)
reads these files through `load_rows`, so a file that passes here runs. The rules of the labels
(what counts as high risk, when a message is benign) are in docs/evals/scam-golden-set.md.

The messages are invented. A real link or phone number in a test file would be a real person's
contact point or a live scam, so the checks below refuse one: links and addresses must be on a
reserved name (`.example`, `.invalid`, `.test`) and a long number must contain a run of zeros,
which no real number does.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.config import EVALS_DIR
from src.validators.scam_taxonomy import load_taxonomy

Language = Literal["en", "hi", "tl", "id", "ne", "bn"]
RiskLevel = Literal["low", "medium", "high"]

CORRIDORS = ("SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH")
RESERVED_TLDS = {"example", "invalid", "test", "localhost"}
MAX_TEXT = 4000  # the analyzer refuses longer messages (docs/api/v2-scam.md)
MAX_RATIONALE = 160

# Size and mix of one set (tracker NF-SA-003: 40 messages, about 28 scams and 12 benign).
ROWS_PER_SET = 40
SCAMS_PER_SET = range(26, 31)
ROWS_PER_LANGUAGE = range(18, 23)

_ID = re.compile(r"^gold-(en|hi|tl|id|ne|bn)-(\d{3})$")
_INITIALS = re.compile(r"^[A-Z]{2,3}$")
_FILE = re.compile(r"^scam_golden_([a-z]{2})_([a-z]{2})\.jsonl$")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)*)")
_BARE_DOMAIN = re.compile(
    r"\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|info|biz|io|co|in|sg|ph|id|my|au|jp|hk|kr|me|ly|gl"
    r"|xyz|top|app|gov|edu)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"\+?\d[\d \-().]{6,}\d")
_TRAILING = ".,;:!?)\"'।"


@lru_cache(maxsize=1)
def _taxonomy_ids() -> tuple[frozenset[str], frozenset[str]]:
    taxonomy = load_taxonomy()
    return frozenset(taxonomy.types), frozenset(taxonomy.tactics)


def _ascii_digits(text: str) -> str:
    """Devanagari, Bengali and other native digits as 0-9, so a number is checked the same."""
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)


def _reserved(host: str) -> bool:
    return host.rsplit(".", 1)[-1].lower() in RESERVED_TLDS


def synthetic_problems(text: str) -> list[str]:
    """What in `text` could be a real link, address or number."""
    problems: list[str] = []
    for match in _URL.findall(text):
        host = urlparse(match.rstrip(_TRAILING) if "//" in match else f"//{match}").hostname or ""
        if not _reserved(host):
            problems.append(f"link {match!r} is not on a reserved name (.example, .invalid, .test)")
    for domain in _EMAIL.findall(text):
        if not _reserved(domain):
            problems.append(f"address at {domain!r} is not on a reserved name")
    without_links = _EMAIL.sub(" ", _URL.sub(" ", text))
    for match in _BARE_DOMAIN.findall(without_links):
        problems.append(f"{match!r} looks like a real domain; write it as a .example link")
    for match in _NUMBER.findall(_ascii_digits(text)):
        digits = re.sub(r"\D", "", match)
        if len(digits) >= 8 and "000000" not in digits:
            problems.append(f"number {match.strip()!r} could be real: use zeros, like 0000 0031")
    return problems


class GoldenRow(BaseModel):
    """One labelled message."""

    model_config = ConfigDict(extra="forbid")

    id: str
    language: Language
    script: Literal["native", "latin"] = Field(
        description="Hindi is often typed in Latin letters (Hinglish); the label says which."
    )
    text: str = Field(
        min_length=10, max_length=MAX_TEXT, description="As pasted, before redaction."
    )
    is_scam: bool
    scam_type: str | None
    tactics: list[str] = Field(max_length=3)
    risk_level: RiskLevel
    rationale: str = Field(min_length=20, max_length=MAX_RATIONALE)
    resembles: str | None = Field(description="For a benign message: the scam type it imitates.")
    corridor_id: Literal["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"] | None = None
    channel: Literal["sms", "whatsapp", "email", "social"]
    provenance: Literal["synthetic", "anonymised"]
    curator: str
    reviewed_by: str | None = None

    @field_validator("curator", "reviewed_by")
    @classmethod
    def _initials(cls, value: str | None) -> str | None:
        if value is not None and not _INITIALS.match(value):
            raise ValueError("initials must be 2 or 3 capital letters")
        return value

    @field_validator("text", "rationale")
    @classmethod
    def _filled(cls, value: str) -> str:
        if value.strip().upper().startswith("TODO"):
            raise ValueError("still a TODO placeholder")
        return value

    @field_validator("rationale")
    @classmethod
    def _one_line(cls, value: str) -> str:
        if "\n" in value:
            raise ValueError("the rationale is one line")
        return value

    @model_validator(mode="after")
    def _the_label_is_consistent(self) -> GoldenRow:
        match = _ID.match(self.id)
        if match is None or match.group(1) != self.language:
            raise ValueError(f"id {self.id!r} must be gold-{self.language}-NNN")
        if self.language == "en" and self.script != "latin":
            raise ValueError("English is written in Latin letters")
        if self.provenance == "synthetic":
            problems = synthetic_problems(self.text)
            if problems:
                raise ValueError("; ".join(problems))
        types, tactics = _taxonomy_ids()
        unknown = [t for t in self.tactics if t not in tactics]
        if unknown or len(set(self.tactics)) != len(self.tactics):
            raise ValueError(f"tactics {self.tactics} must be distinct taxonomy tactic ids")
        if self.is_scam:
            if self.scam_type not in types:
                raise ValueError(f"a scam needs a taxonomy type, got {self.scam_type!r}")
            if not self.tactics:
                raise ValueError("a scam names at least one tactic")
            if self.resembles is not None:
                raise ValueError("`resembles` is for benign messages")
        else:
            if self.scam_type is not None or self.tactics or self.risk_level != "low":
                raise ValueError("a benign message has no type or tactics and low risk")
            if self.resembles not in types:
                raise ValueError("a benign look-alike names the scam type it resembles")
        if self.reviewed_by is not None and self.reviewed_by == self.curator:
            raise ValueError("the reviewer must be a different person from the curator")
        return self


def load_rows(path: Path) -> tuple[list[GoldenRow], list[str]]:
    """Read a JSONL file; return the rows that parse and one message per problem."""
    rows: list[GoldenRow] = []
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(GoldenRow.model_validate(json.loads(line)))
        except json.JSONDecodeError as exc:
            problems.append(f"line {number}: not JSON ({exc.msg})")
        except ValidationError as exc:
            for err in exc.errors():
                where = ".".join(str(p) for p in err["loc"]) or "row"
                problems.append(f"line {number}: {where}: {err['msg']}")
    return rows, problems


def check_set(rows: list[GoldenRow], path: Path) -> list[str]:
    """Rules about the file as a whole: size, mix and coverage."""
    problems: list[str] = []
    named = _FILE.match(path.name)
    expected = set(named.groups()) if named else None
    if expected is None:
        problems.append(f"{path.name}: name it scam_golden_<lang>_<lang>.jsonl")
    if len(rows) != ROWS_PER_SET:
        problems.append(f"{len(rows)} rows, expected {ROWS_PER_SET}")
    if expected is not None and {r.language for r in rows} != expected:
        problems.append(
            f"languages are {sorted({r.language for r in rows})}, file name says {sorted(expected)}"
        )
    for language, count in Counter(r.language for r in rows).items():
        if count not in ROWS_PER_LANGUAGE:
            problems.append(f"{language}: {count} rows, expected 18 to 22")
    ids = [r.id for r in rows]
    if len(set(ids)) != len(ids):
        problems.append("ids are not unique")
    for language in {r.language for r in rows}:
        numbers = sorted(int(r.id[-3:]) for r in rows if r.language == language)
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(f"{language}: ids must run gold-{language}-001 upwards with no gap")
    texts = [" ".join(r.text.lower().split()) for r in rows]
    if len(set(texts)) != len(texts):
        problems.append("two rows have the same text")
    scams = [r for r in rows if r.is_scam]
    if len(scams) not in SCAMS_PER_SET:
        problems.append(f"{len(scams)} scams, expected 26 to 30 (and the rest benign)")
    types, tactics = _taxonomy_ids()
    seen_types = Counter(r.scam_type for r in scams)
    for type_id in sorted(types):
        if seen_types[type_id] < 2:
            problems.append(f"scam type {type_id} has {seen_types[type_id]} scam row(s), needs 2")
    unused = sorted(tactics - {t for r in scams for t in r.tactics})
    if unused:
        problems.append(f"no scam row uses tactic(s) {unused}")
    if {r.risk_level for r in scams} != {"low", "medium", "high"}:
        problems.append("the scam rows must include low, medium and high risk")
    if len({r.resembles for r in rows if not r.is_scam}) < 5:
        problems.append("the benign rows should resemble at least 5 different scam types")
    return problems


def pick_spot_check(rows: list[GoldenRow], count: int = 10, seed: int = 1) -> list[GoldenRow]:
    """A fixed sample for the second teammate: some benign, both languages, many scam types.

    The same seed gives the same rows, so the reviewer and the curator talk about the same ones.
    """
    rng = random.Random(seed)
    pool = sorted(rows, key=lambda r: r.id)
    rng.shuffle(pool)
    chosen: list[GoldenRow] = []
    types_seen: set[str | None] = set()
    languages: Counter[str] = Counter()
    benign_wanted = max(1, round(count * 0.3))
    for row in pool:
        if len(chosen) == benign_wanted:
            break
        if not row.is_scam and languages[row.language] <= len(chosen) // 2:
            chosen.append(row)
            languages[row.language] += 1
    for row in pool:
        if len(chosen) == count:
            break
        if row.is_scam and row.scam_type not in types_seen and row not in chosen:
            if languages[row.language] <= count // 2:
                chosen.append(row)
                types_seen.add(row.scam_type)
                languages[row.language] += 1
    for row in pool:
        if len(chosen) == count:
            break
        if row not in chosen:
            chosen.append(row)
    return sorted(chosen, key=lambda r: r.id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the scam golden eval sets.")
    parser.add_argument("paths", nargs="*", type=Path, help="default: every file in evals/")
    parser.add_argument("--spot-check", type=int, metavar="N", help="list N rows to review")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--require-reviewed", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)
    paths = args.paths or sorted(EVALS_DIR.glob("scam_golden_*.jsonl"))
    if not paths:
        print("FAIL no scam_golden_*.jsonl file found")
        return 1

    failed = False
    for path in paths:
        rows, problems = load_rows(path)
        if not problems:
            problems = check_set(rows, path)
        reviewed = sum(1 for r in rows if r.reviewed_by)
        if reviewed < args.require_reviewed:
            problems.append(f"{reviewed} row(s) reviewed, {args.require_reviewed} required")
        if problems:
            failed = True
            print(f"FAIL {path.name}: {len(problems)} problem(s)")
            for problem in problems[:30]:
                print(f"     {problem}")
            continue
        scams = sum(r.is_scam for r in rows)
        print(
            f"OK   {path.name}: {len(rows)} rows, {scams} scam, {len(rows) - scams} benign, "
            f"{reviewed} reviewed"
        )
        if args.spot_check:
            for row in pick_spot_check(rows, args.spot_check, args.seed):
                label = row.scam_type or f"benign (resembles {row.resembles})"
                print(f"  {row.id}  {label}  tactics={row.tactics}  risk={row.risk_level}")
                print(f"      {row.text}")
                print(f"      why: {row.rationale}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
