"""Schema and checks for the known-scam pattern library (data/source/scam-patterns/*.jsonl).

Check your files:  python -m src.validators.scam_patterns

One file per scam type, one line per template. A template is a synthetic message in the shape a
scam really takes, with placeholders (`[AGENCY]`, `[AMOUNT]`, ...) where a real one has a name, a
sum or a contact point. The loader (src/loaders/scam_patterns.py) embeds each one and stores it in
`scam_patterns/`; the analyzer then finds the nearest ones to an incoming message (NF-SA-010).

The incoming message is redacted before it is embedded, so a template spells a contact point the
way the redactor does (`[PHONE]`, `[URL]`, ...) and a vector search compares like with like.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from src.config import SCAM_PATTERNS_DIR
from src.validators.scam_golden import synthetic_problems
from src.validators.scam_taxonomy import load_taxonomy

Language = Literal["en", "hi", "tl", "id", "ne", "bn"]
Corridor = Literal["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"]

LANGUAGES: tuple[str, ...] = ("en", "hi", "tl", "id", "ne", "bn")
CORRIDORS: tuple[str, ...] = ("SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH")

# Tracker NF-SA-006: at least 60 per scam type. Ten in every language keeps the six languages
# level, so a Nepali message is not matched on a thinner shelf than an English one.
MIN_PER_TYPE = 60
MIN_PER_LANGUAGE = 10
MIN_PER_CORRIDOR = 3
# Hindi is often typed in Latin letters; Nepali and Bengali too, less often (as in the golden sets).
MIN_LATIN = {"hi": 2, "ne": 1, "bn": 1}

PLACEHOLDERS = frozenset(
    {
        "PHONE", "EMAIL", "ID", "ACCOUNT", "URL",  # what the redactor writes
        "AGENCY", "COMPANY", "BANK", "NAME", "AMOUNT", "APP", "DATE",
    }
)  # fmt: skip
# The scope is six corridors and no others: a template that names a place outside it would
# teach the search a route the product does not cover.
OUT_OF_SCOPE = re.compile(
    r"\b(?:korea\w*|seoul|busan|uae|dubai|abu dhabi|sharjah|emirates|qatar|doha|saudi|riyadh"
    r"|kuwait|kr)\b|한국",
    re.IGNORECASE,
)

_ID = re.compile(r"^([a-z_]+)-(en|hi|tl|id|ne|bn)-(\d{3})$")
_INITIALS = re.compile(r"^[A-Z]{2,3}$")
_BRACKET = re.compile(r"\[([A-Za-z_]+)\]")
_TOKEN = re.compile(r"\w+", re.UNICODE)
_NATIVE = {"hi": (0x0900, 0x097F), "ne": (0x0900, 0x097F), "bn": (0x0980, 0x09FF)}
MAX_TEXT = 1200


@lru_cache(maxsize=1)
def _taxonomy_ids() -> tuple[frozenset[str], frozenset[str]]:
    taxonomy = load_taxonomy()
    return frozenset(taxonomy.types), frozenset(taxonomy.tactics)


def script_of(text: str, language: str) -> str:
    """`native` or `latin`: the letters a template is written in."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "latin"
    span = _NATIVE.get(language)
    native = 0 if span is None else sum(span[0] <= ord(ch) <= span[1] for ch in letters)
    if span is not None and native / len(letters) >= 0.3:
        return "native"
    return "latin"


class PatternRow(BaseModel):
    """One scam template."""

    model_config = ConfigDict(extra="forbid")

    id: str
    scam_type: str
    language: Language
    tactics: list[str] = Field(min_length=1, max_length=3)
    text: str = Field(min_length=40, max_length=MAX_TEXT)
    corridor_id: Corridor | None = None
    curator: str
    reviewed_by: str | None = None

    @field_validator("curator", "reviewed_by")
    @classmethod
    def _initials(cls, value: str | None) -> str | None:
        if value is not None and not _INITIALS.match(value):
            raise ValueError("initials must be 2 or 3 capital letters")
        return value

    @model_validator(mode="after")
    def _consistent(self) -> PatternRow:
        match = _ID.match(self.id)
        if match is None or (match.group(1), match.group(2)) != (self.scam_type, self.language):
            raise ValueError(f"id {self.id!r} must be {self.scam_type}-{self.language}-NNN")
        types, tactics = _taxonomy_ids()
        if self.scam_type not in types:
            raise ValueError(f"{self.scam_type!r} is not a taxonomy type")
        if len(set(self.tactics)) != len(self.tactics) or not set(self.tactics) <= tactics:
            raise ValueError(f"tactics {self.tactics} must be distinct taxonomy tactic ids")
        if "\n" in self.text or self.text != self.text.strip():
            raise ValueError("the text is one trimmed line")
        if self.text.upper().startswith("TODO"):
            raise ValueError("still a TODO placeholder")
        unknown = sorted(set(_BRACKET.findall(self.text)) - PLACEHOLDERS)
        if unknown:
            raise ValueError(f"unknown placeholder(s) {unknown}; allowed: {sorted(PLACEHOLDERS)}")
        problems = synthetic_problems(self.text)
        if problems:
            raise ValueError("; ".join(problems))
        if OUT_OF_SCOPE.search(self.text):
            raise ValueError("names a country or city outside the six corridors")
        has_native = any(
            0x0900 <= ord(ch) <= 0x09FF or 0x0980 <= ord(ch) <= 0x09FF for ch in self.text
        )
        if self.language in ("en", "tl", "id") and has_native:
            raise ValueError(f"{self.language} is written in Latin letters")
        if (
            self.language in _NATIVE
            and script_of(self.text, self.language) == "latin"
            and has_native
        ):
            raise ValueError("mixes native and Latin script: write it in one")
        if self.reviewed_by is not None and self.reviewed_by == self.curator:
            raise ValueError("the reviewer must be a different person from the curator")
        return self


def load_patterns(path: Path) -> tuple[list[PatternRow], list[str]]:
    """Read one JSONL file; return the rows that parse and one message per problem."""
    rows: list[PatternRow] = []
    problems: list[str] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(PatternRow.model_validate(json.loads(line)))
        except json.JSONDecodeError as exc:
            problems.append(f"{path.name} line {number}: not JSON ({exc.msg})")
        except ValidationError as exc:
            for err in exc.errors():
                where = ".".join(str(p) for p in err["loc"]) or "row"
                problems.append(f"{path.name} line {number}: {where}: {err['msg']}")
    return rows, problems


def load_all(directory: Path = SCAM_PATTERNS_DIR) -> tuple[list[PatternRow], list[str]]:
    """Every `<scam_type>.jsonl` in the folder, in type order."""
    rows: list[PatternRow] = []
    problems: list[str] = []
    paths = sorted(directory.glob("*.jsonl"))
    if not paths:
        return rows, [f"no *.jsonl file in {directory}"]
    for path in paths:
        file_rows, file_problems = load_patterns(path)
        problems.extend(file_problems)
        for row in file_rows:
            if row.scam_type != path.stem:
                problems.append(f"{path.name}: {row.id} belongs in {row.scam_type}.jsonl")
        rows.extend(file_rows)
    return rows, problems


def _words(text: str) -> frozenset[str]:
    return frozenset(_TOKEN.findall(text.lower()))


def check_library(rows: list[PatternRow]) -> list[str]:
    """Rules about the library as a whole: size, language and corridor coverage, repeats."""
    problems: list[str] = []
    types, _ = _taxonomy_ids()
    ids = [r.id for r in rows]
    if len(set(ids)) != len(ids):
        problems.append("ids are not unique")
    by_type: dict[str, list[PatternRow]] = defaultdict(list)
    for row in rows:
        by_type[row.scam_type].append(row)
    for type_id in sorted(types):
        group = by_type.get(type_id, [])
        if len(group) < MIN_PER_TYPE:
            problems.append(f"{type_id}: {len(group)} templates, needs {MIN_PER_TYPE}")
        per_language: Counter[str] = Counter(str(r.language) for r in group)
        per_corridor: Counter[str | None] = Counter(r.corridor_id for r in group)
        for language in LANGUAGES:
            if per_language[language] < MIN_PER_LANGUAGE:
                problems.append(
                    f"{type_id}: {per_language[language]} {language} templates, "
                    f"needs {MIN_PER_LANGUAGE}"
                )
            numbers = sorted(int(r.id[-3:]) for r in group if r.language == language)
            if numbers != list(range(1, len(numbers) + 1)):
                problems.append(f"{type_id}-{language}: ids must run 001 upwards with no gap")
            wanted = MIN_LATIN.get(language, 0)
            latin = sum(
                script_of(r.text, language) == "latin" for r in group if r.language == language
            )
            if language in MIN_LATIN and latin < wanted:
                problems.append(
                    f"{type_id}: {latin} {language} template(s) in Latin letters, needs {wanted}"
                )
            texts = [(r.id, _words(r.text)) for r in group if r.language == language]
            for i, (id_a, a) in enumerate(texts):
                for id_b, b in texts[i + 1 :]:
                    if a and b and len(a & b) / len(a | b) > 0.8:
                        problems.append(f"{id_a} and {id_b} are near-copies of one another")
        for corridor in CORRIDORS:
            if per_corridor[corridor] < MIN_PER_CORRIDOR:
                problems.append(
                    f"{type_id}: {per_corridor[corridor]} template(s) for {corridor}, "
                    f"needs {MIN_PER_CORRIDOR}"
                )
    seen: dict[str, str] = {}
    for row in rows:
        key = " ".join(row.text.lower().split())
        if key in seen:
            problems.append(f"{row.id} has the same text as {seen[key]}")
        seen[key] = row.id
    return problems


def pick_spot_check(rows: list[PatternRow], count: int = 10, seed: int = 1) -> list[PatternRow]:
    """A fixed sample for the second teammate: every type and every language, in turn.

    The same seed gives the same rows, so the reviewer and the curator talk about the same ones.
    """
    rng = random.Random(seed)
    pool = sorted(rows, key=lambda r: r.id)
    rng.shuffle(pool)
    types = sorted({r.scam_type for r in rows})
    chosen: list[PatternRow] = []
    for i in range(count):
        scam_type, language = types[i % len(types)], LANGUAGES[i % len(LANGUAGES)]
        options = [r for r in pool if r.scam_type == scam_type and r not in chosen]
        options.sort(key=lambda r: r.language != language)
        if options:
            chosen.append(options[0])
    return sorted(chosen, key=lambda r: r.id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the scam pattern library.")
    parser.add_argument("--directory", type=Path, default=SCAM_PATTERNS_DIR)
    parser.add_argument("--spot-check", type=int, metavar="N", help="list N rows to review")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--require-reviewed", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)
    # The spot-check prints Hindi, Nepali and Bengali; a Windows console or pipe is often cp1252.
    if reconfigure := getattr(sys.stdout, "reconfigure", None):
        reconfigure(encoding="utf-8")

    rows, problems = load_all(args.directory)
    if not problems:
        problems = check_library(rows)
    reviewed = sum(1 for r in rows if r.reviewed_by)
    if not problems and reviewed < args.require_reviewed:
        problems.append(f"{reviewed} row(s) reviewed, {args.require_reviewed} required")
    if problems:
        print(f"FAIL {len(problems)} problem(s)")
        for problem in problems[:40]:
            print(f"     {problem}")
        return 1
    per_type = Counter(r.scam_type for r in rows)
    per_language = Counter(r.language for r in rows)
    print(f"OK   {len(rows)} templates, {len(per_type)} types, {len(per_language)} languages")
    for type_id, count in sorted(per_type.items()):
        print(f"     {type_id}: {count}")
    print(f"     {reviewed} reviewed")
    if args.spot_check:
        for row in pick_spot_check(rows, args.spot_check, args.seed):
            print(f"  {row.id}  tactics={row.tactics}  corridor={row.corridor_id}")
            print(f"      {row.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
