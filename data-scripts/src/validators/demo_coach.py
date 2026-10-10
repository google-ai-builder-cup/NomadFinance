"""Schema for the demo workers' Coach seed (data/seed/coach/*.json, NF-HR-003).

Check the files:  python -m src.validators.demo_coach
Each file holds a stored session, a stored plan and the plan's translation exactly as the backend
wrote them (it is built by `backend/tests/fixtures/demo_seed.py`, and a backend test fails when a
file drifts from the real models). This module only checks what the loader relies on, so a bad
edit stops at the checker and not halfway through a load. The days a file carries are relative:
`departure_in_days` (negative: already left) and `plan_created_days_ago`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import SEED_COACH_DIR

SLOT_NAMES = (
    "destination_country",
    "job_type",
    "departure_date",
    "monthly_salary",
    "dependents",
    "remittance_target",
    "recruitment_fee_paid",
    "debt_outstanding",
    "debt_interest",
    "savings",
    "bank_or_wallet",
)
DEPARTURE = "@departure"
MILESTONE_DAYS = {"d30": 30, "d60": 60, "d90": 90}
PLAN_WEEKS = 13
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_CODE = re.compile(r"\b[A-Z]{3}\b")


class CheckinSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answered_days_after_due: int = Field(ge=0, le=30)
    answers: dict[Literal["remittance", "savings", "pay"], str]


class SignalSharing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coach: bool
    scam: bool


def tokens(text: str) -> list[str]:
    """The numbers and currency codes of a sentence, which a translation must keep exactly."""
    return sorted(_NUMBER.findall(text) + _CODE.findall(text))


def sentences(plan: dict[str, Any]) -> list[str]:
    """Every sentence of a plan's narrative, in a fixed order."""
    out = [plan["summary"], plan["disclaimer"]]
    for week in plan["weeks"]:
        out += [week["title"], *week["actions"]]
    out += [note["text"] for note in plan["warnings"]]
    out += [item["text"] for item in plan["checklist"]]
    return out


class CoachSeed(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    comment: str = Field(alias="_comment", default="")
    uid: str = Field(pattern=r"^[A-Za-z0-9_-]{3,128}$")
    language: Literal["hi", "tl", "id", "ne", "bn"]
    session_id: str = Field(pattern=r"^demo_s_[0-9]{2}$")
    departure_in_days: int = Field(ge=-365, le=365)
    plan_created_days_ago: int = Field(ge=1, le=365)
    checkins: dict[Literal["d30", "d60", "d90"], CheckinSeed]
    signal_sharing: SignalSharing
    session: dict[str, Any]
    plan: dict[str, Any]
    translations: dict[str, dict[str, Any]]

    @model_validator(mode="after")
    def _consistent(self) -> CoachSeed:
        slots = self.plan.get("slots", {})
        if set(slots) - set(SLOT_NAMES):
            raise ValueError(f"unknown slots: {sorted(set(slots) - set(SLOT_NAMES))}")
        if slots.get("departure_date") != DEPARTURE:
            raise ValueError(f"plan.slots.departure_date must be {DEPARTURE!r}")
        if self.plan.get("departure_date") != DEPARTURE:
            raise ValueError(f"plan.departure_date must be {DEPARTURE!r}")
        record = self.session.get("slots", {}).get("departure_date", {})
        if record.get("value") != DEPARTURE:
            raise ValueError(f"session.slots.departure_date.value must be {DEPARTURE!r}")
        if self.session.get("status") != "completed" or self.session.get("stage") != "plan":
            raise ValueError("the session must be completed, at the plan stage")
        if not all(r.get("confirmed") is True for r in self.session["slots"].values()):
            raise ValueError("every answer of the session must be confirmed")
        plan = self.plan.get("plan", {})
        if [w["week"] for w in plan.get("weeks", [])] != list(range(1, PLAN_WEEKS + 1)):
            raise ValueError("the plan must have weeks 1 to 13, in order")
        if set(self.translations) != {self.language}:
            raise ValueError(f"translations must hold exactly {self.language!r}")
        translated = self.translations[self.language].get("plan", {})
        if [tokens(a) for a in sentences(plan)] != [tokens(b) for b in sentences(translated)]:
            raise ValueError("the translation changes a number or a currency code")
        # The plan was made before the worker left (or on the day), and every answered
        # check-in was answered by today.
        if -self.plan_created_days_ago > self.departure_in_days:
            raise ValueError("the plan is dated after the departure")
        for milestone, answered in self.checkins.items():
            due = self.departure_in_days + MILESTONE_DAYS[milestone]
            if due + answered.answered_days_after_due > 0:
                raise ValueError(f"{milestone} is answered in the future")
        return self


def is_blank(path: Path) -> bool:
    return not path.read_text(encoding="utf-8").strip()


def load(path: Path) -> CoachSeed:
    """Read and validate one file.

    Raises:
        ValueError: The file is not valid JSON, or breaks the schema's own checks.
        pydantic.ValidationError: The content breaks the schema.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    return CoachSeed.model_validate(raw)


def seed_files(directory: Path = SEED_COACH_DIR) -> list[Path]:
    return sorted(directory.glob("*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the demo Coach seed files.")
    parser.add_argument("--input-dir", type=Path, default=SEED_COACH_DIR)
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
            print(
                f"{path.name}: OK ({seed.uid}, {seed.language}, score "
                f"{seed.plan['score']['total']}, {len(seed.checkins)} check-in(s))"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
