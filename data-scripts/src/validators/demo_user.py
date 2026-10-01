"""Schema for the demo users (data/seed/users/*.json, NF-P3-015).

Check the files:  python -m src.validators.demo_user
The loader reuses UserSeed, so a file that passes here loads. The value lists mirror
backend/app/schemas/fib.py (categories, directions, account types) and
docs/data-model/collections/users.md (profile values); the corridor list is src/config.py's.
Entries carry no dates, only `months_ago` and `day`: the loader turns them into real dates
relative to the day it runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from src.config import CORRIDORS, SEED_USERS_DIR
from src.validators.labor_law import COUNTRIES

IncomeCategory = Literal["salary", "overtime", "bonus", "other_income"]
BillCategory = Literal[
    "rent", "utilities", "phone_internet", "transport", "food", "medical", "other_expense"
]
Language = Literal["en", "hi", "tl", "id", "ne", "bn"]
JobType = Literal[
    "domestic_worker",
    "manufacturing_worker",
    "care_worker",
    "plantation_worker",
    "construction_worker",
    "working_holiday",
    "other",
]
HOME_COUNTRIES = ("PH", "IN", "ID", "NP", "BD")

# The profile looks back 12 calendar months (backend/app/services/fib/profile_metrics.py), so
# older history would be ignored by the recompute.
MAX_MONTHS_AGO = 11
CURRENCY = r"^[A-Z]{3}$"
_CORRIDORS = {c.corridor_id: c for c in CORRIDORS}


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    months_ago: int = Field(ge=0, le=MAX_MONTHS_AGO)
    # 28 at most: every month has that day, so no entry lands on a date that does not exist.
    day: int = Field(ge=1, le=28)
    notes: str | None = Field(default=None, max_length=500)


class Income(_Entry):
    id: str = Field(pattern=r"^demo_i_[0-9]{2}$")
    amount: float = Field(gt=0)
    currency: str = Field(pattern=CURRENCY)
    category: IncomeCategory
    employer_name: str | None = Field(default=None, max_length=200)


class Transfer(_Entry):
    id: str = Field(pattern=r"^demo_t_[0-9]{2}$")
    corridor_id: str
    provider_name: str = Field(min_length=2)
    provider_rpw_id: int | None = None
    send_amount: float = Field(gt=0)
    send_currency: str = Field(pattern=CURRENCY)
    receive_amount: float = Field(gt=0)
    receive_currency: str = Field(pattern=CURRENCY)
    fee: float | None = Field(default=None, ge=0)
    mid_market_rate: float | None = Field(default=None, gt=0)
    cost_pct: float | None = None

    @model_validator(mode="after")
    def _matches_corridor(self) -> Transfer:
        corridor = _CORRIDORS.get(self.corridor_id)
        if corridor is None:
            raise ValueError(f"corridor_id {self.corridor_id!r} is not one of {list(_CORRIDORS)}")
        if (self.send_currency, self.receive_currency) != (
            corridor.source_currency,
            corridor.destination_currency,
        ):
            raise ValueError(
                f"{self.id}: {self.corridor_id} sends {corridor.source_currency} and "
                f"pays out {corridor.destination_currency}"
            )
        return self


class BillExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0, le=1)
    model: str
    prompt_version: int = Field(ge=1)


class Bill(_Entry):
    id: str = Field(pattern=r"^demo_b_[0-9]{2}$")
    amount: float = Field(gt=0)
    currency: str = Field(pattern=CURRENCY)
    vendor: str | None = Field(default=None, max_length=200)
    paid: bool
    category: BillCategory
    category_source: Literal["user", "model"]
    category_confidence: float | None = Field(default=None, ge=0, le=1)
    source: Literal["manual", "bill_ocr"]
    # Day of the same month printed on the bill, for a photographed bill.
    bill_day: int | None = Field(default=None, ge=1, le=28)
    extraction: BillExtraction | None = None

    @model_validator(mode="after")
    def _check(self) -> Bill:
        # fib.md: a confidence belongs to a model category only.
        if (self.category_source == "model") != (self.category_confidence is not None):
            raise ValueError(f"{self.id}: category_confidence goes with category_source 'model'")
        if (self.source == "bill_ocr") != (self.extraction is not None):
            raise ValueError(f"{self.id}: an `extraction` map goes with source 'bill_ocr'")
        if self.bill_day is not None and self.bill_day > self.day:
            raise ValueError(f"{self.id}: the bill is dated after the day it was logged")
        return self


class Saving(_Entry):
    id: str = Field(pattern=r"^demo_s_[0-9]{2}$")
    amount: float = Field(gt=0)
    currency: str = Field(pattern=CURRENCY)
    direction: Literal["deposit", "withdrawal"]
    account_type: Literal["cash", "bank", "mobile_wallet", "other"] | None = None


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_country: Literal["PH", "IN", "ID", "NP", "BD"]
    host_country: str
    job_type: JobType
    preferred_language: Language

    @model_validator(mode="after")
    def _host(self) -> Profile:
        if self.host_country not in COUNTRIES:
            raise ValueError(f"host_country {self.host_country!r} is not one of {COUNTRIES}")
        return self


class UserSeed(BaseModel):
    """One demo user's file."""

    model_config = ConfigDict(extra="forbid")

    comment: str = Field(alias="_comment", default="")
    uid: str = Field(pattern=r"^[A-Za-z0-9_-]{3,128}$")
    user: Profile
    income: list[Income] = []
    transfers: list[Transfer] = []
    bills: list[Bill] = []
    savings: list[Saving] = []

    @model_validator(mode="after")
    def _unique_ids(self) -> UserSeed:
        ids = [
            e.id for group in (self.income, self.transfers, self.bills, self.savings) for e in group
        ]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate entry ids")
        if not ids:
            raise ValueError("a demo user needs at least one entry")
        return self


def is_blank(path: Path) -> bool:
    """True for a stub that has not been filled in yet (empty or whitespace only)."""
    return not path.read_text(encoding="utf-8").strip()


def load(path: Path) -> UserSeed:
    """Read and validate one file.

    Raises:
        ValueError: The file is not valid JSON.
        pydantic.ValidationError: The content breaks the schema.
        OSError: The file cannot be read.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    return UserSeed.model_validate(raw)


def seed_files(directory: Path = SEED_USERS_DIR) -> list[Path]:
    return sorted(directory.glob("*.json"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the demo user seed files.")
    parser.add_argument("--input-dir", type=Path, default=SEED_USERS_DIR)
    args = parser.parse_args(argv)

    failed = False
    for path in seed_files(args.input_dir):
        if is_blank(path):
            print(f"{path.name}: empty, skipped")
            continue
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
                f"{path.name}: OK ({seed.uid}: {len(seed.income)} income, "
                f"{len(seed.transfers)} transfers, {len(seed.bills)} bills, "
                f"{len(seed.savings)} savings)"
            )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
