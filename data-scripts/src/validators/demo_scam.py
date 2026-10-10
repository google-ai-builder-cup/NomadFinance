"""Schema for the demo workers' stored scam checks (data/seed/scam-checks/*.json, NF-HR-003).

Check the files:  python -m src.validators.demo_scam
Built by `backend/tests/fixtures/demo_seed.py` through the backend's own analyzer; a backend test
fails when a file drifts from it. This checks what the loader relies on: five checks, distinct
messages, a verdict and an explainer, and no time field and no cache key (the loader gives those).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import SEED_SCAM_DIR

CHECKS_PER_WORKER = 5
TIME_FIELDS = ("created_at", "last_checked_at", "expires_at", "reported_at")
# Worked out by the loader from the masked text and the language, never kept in a file.
DERIVED_FIELDS = ("cache_key",)
# Present on a stored check; the loader needs them or the history cannot show it.
REQUIRED = (
    "input_type",
    "language",
    "redacted_text",
    "verdict",
    "indicators",
    "explainer",
    "taxonomy_version",
    "prompt_versions",
)


def cache_key(redacted_text: str, language: str) -> str:
    """The backend's key (`check_store.cache_key`): the masked text normalised, a newline, the
    output language. A repeat of the message in that language is then answered from the check."""
    normalised = " ".join(unicodedata.normalize("NFKC", redacted_text).casefold().split())
    return hashlib.sha256(f"{normalised}\n{language}".encode()).hexdigest()


def message_key(document: dict[str, Any]) -> str:
    """The key of a check's masked text in its output language."""
    return cache_key(document["redacted_text"], document["language"])


class CheckSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^demo_k_[0-9]{2}$")
    golden_id: str = Field(pattern=r"^gold-[a-z]{2}-[0-9]{3}$")
    message: str = Field(min_length=1, max_length=4000)
    days_ago: int = Field(ge=0, le=80)
    hour_utc: int = Field(ge=0, le=23)
    document: dict[str, Any]

    @model_validator(mode="after")
    def _document(self) -> CheckSeed:
        missing = [name for name in REQUIRED if name not in self.document]
        if missing:
            raise ValueError(f"{self.id}: missing {missing}")
        present = [name for name in TIME_FIELDS if name in self.document]
        if present:
            raise ValueError(f"{self.id}: {present} are set by the loader, not the file")
        derived = [name for name in DERIVED_FIELDS if name in self.document]
        if derived:
            raise ValueError(f"{self.id}: {derived} are worked out by the loader, not the file")
        if not self.document["explainer"]:
            raise ValueError(f"{self.id}: a stored check without an explainer is not served")
        if self.message == self.document["redacted_text"] and "[" in self.message:
            raise ValueError(f"{self.id}: the message is already masked")
        return self


class ScamSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    comment: str = Field(alias="_comment", default="")
    uid: str = Field(pattern=r"^[A-Za-z0-9_-]{3,128}$")
    checks: list[CheckSeed]

    @model_validator(mode="after")
    def _five(self) -> ScamSeed:
        if len(self.checks) != CHECKS_PER_WORKER:
            raise ValueError(f"a worker has {CHECKS_PER_WORKER} checks, not {len(self.checks)}")
        ids = [c.id for c in self.checks]
        keys = [message_key(c.document) for c in self.checks]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
            raise ValueError("duplicate check ids or messages")
        scams = sum(1 for c in self.checks if c.document["verdict"]["is_scam"])
        if scams in (0, CHECKS_PER_WORKER):
            raise ValueError("the checks must mix scams and benign messages")
        return self


def is_blank(path: Path) -> bool:
    return not path.read_text(encoding="utf-8").strip()


def load(path: Path) -> ScamSeed:
    """Read and validate one file.

    Raises:
        ValueError: The file is not valid JSON, or breaks the schema's own checks.
        pydantic.ValidationError: The content breaks the schema.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    return ScamSeed.model_validate(raw)


def seed_files(directory: Path = SEED_SCAM_DIR) -> list[Path]:
    return sorted(directory.glob("*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the demo scam-check seed files.")
    parser.add_argument("--input-dir", type=Path, default=SEED_SCAM_DIR)
    args = parser.parse_args(argv)
    failed = False
    for path in seed_files(args.input_dir):
        try:
            seed = load(path)
        except ValidationError as exc:
            failed = True
            print(f"{path.name}: {exc.error_count()} problem(s)")
            for err in exc.errors()[:10]:
                print(f"    {'.'.join(str(p) for p in err['loc'])}: {err['msg']}")
        except (ValueError, OSError) as exc:
            failed = True
            print(f"{path.name}: {exc}")
        else:
            scams = sum(1 for c in seed.checks if c.document["verdict"]["is_scam"])
            print(f"{path.name}: OK ({seed.uid}: {scams} scam, {5 - scams} benign)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
