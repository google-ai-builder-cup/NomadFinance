from __future__ import annotations

import math
import random
from datetime import date

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config import CORRIDORS


class Quote(BaseModel):
    """Price of sending a fixed USD-equivalent amount, in the sender's local currency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    send_amount_lcu: float = Field(gt=0)
    fee_lcu: float = Field(ge=0)
    # Units of payout currency per 1 unit of sending currency, as applied by the provider.
    fx_rate: float = Field(gt=0)
    # Negative when the provider beats the interbank rate; that is real, not an error.
    fx_margin_pct: float = Field(ge=-20, le=100)
    total_cost_pct: float = Field(ge=-20, le=100)


class ProviderRecord(BaseModel):
    """One surveyed service: a firm plus how the sender pays and how the receiver collects."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rpw_id: int
    firm: str = Field(min_length=1)
    firm_type: str = Field(min_length=1)
    payment_instrument: str = Field(min_length=1)
    access_point: str = Field(min_length=1)
    pickup_method: str = Field(min_length=1)
    speed: str = Field(min_length=1)
    network_coverage: str | None = None
    note: str | None = None
    # Not always the destination currency: some services pay out in USD, and then fx_rate is
    # not comparable with the local-currency providers. total_cost_pct stays comparable.
    payout_currency: str = Field(pattern=r"^[A-Z]{3}$")
    interbank_rate: float = Field(gt=0)
    surveyed_on: date
    quote_200: Quote
    quote_500: Quote


class CorridorDoc(BaseModel):
    """One document for the Firestore `corridors/{corridor_id}` collection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    corridor_id: str = Field(pattern=r"^[A-Z]{2}-[A-Z]{2}$")
    source_country: str
    destination_country: str
    source_currency: str = Field(pattern=r"^[A-Z]{3}$")
    destination_currency: str = Field(pattern=r"^[A-Z]{3}$")
    period: str = Field(pattern=r"^\d{4}_[1-4]Q$")
    provider_count: int = Field(ge=1)
    providers: list[ProviderRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_consistency(self) -> CorridorDoc:
        if self.provider_count != len(self.providers):
            raise ValueError(f"{self.corridor_id}: provider_count does not match providers")
        ids = [p.rpw_id for p in self.providers]
        if len(ids) != len(set(ids)):
            raise ValueError(f"{self.corridor_id}: duplicate rpw_id")
        return self


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str
    attribution: str
    file_name: str
    sheet: str


class RpwCorridorFile(BaseModel):
    """Whole output file: attribution, survey period and the six corridor documents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: SourceInfo
    period: str = Field(pattern=r"^\d{4}_[1-4]Q$")
    corridors: list[CorridorDoc]

    @model_validator(mode="after")
    def _check_corridor_set(self) -> RpwCorridorFile:
        expected = [c.corridor_id for c in CORRIDORS]
        actual = [c.corridor_id for c in self.corridors]
        if actual != expected:
            raise ValueError(f"corridors must be {expected} in order, got {actual}")
        return self


def _same(a: float, b: object) -> bool:
    return isinstance(b, int | float) and math.isclose(a, float(b), rel_tol=1e-9, abs_tol=1e-9)


def verify_against_source(
    raw: pd.DataFrame, output: RpwCorridorFile, sample_size: int = 15, seed: int = 42
) -> list[str]:
    """Cross-check parsed records against the untouched workbook rows.

    Compares every corridor's record count with the raw row count, then spot-checks a
    reproducible random sample field by field. Returns one line per sampled record so the
    caller can print it, and raises ValueError listing every mismatch found.
    """
    by_id = raw.set_index("id")
    codes = {c.corridor_id: c.rpw_code for c in CORRIDORS}
    problems: list[str] = []
    pairs: list[tuple[str, ProviderRecord]] = []

    for doc in output.corridors:
        rows = raw[(raw["corridor"] == codes[doc.corridor_id]) & (raw["period"] == output.period)]
        if len(rows) != doc.provider_count:
            problems.append(f"{doc.corridor_id}: {doc.provider_count} parsed vs {len(rows)} raw")
        pairs.extend((doc.corridor_id, p) for p in doc.providers)

    lines: list[str] = []
    for corridor_id, p in random.Random(seed).sample(pairs, min(sample_size, len(pairs))):
        if p.rpw_id not in by_id.index:
            problems.append(f"{corridor_id} id {p.rpw_id}: not found in source")
            continue
        r = by_id.loc[p.rpw_id]
        checks = {
            "corridor": r["corridor"] == codes[corridor_id],
            "period": r["period"] == output.period,
            "firm": str(r["firm"]).strip() == p.firm,
            "speed": str(r["speed actual"]).strip() == p.speed,
            "fee_200": _same(p.quote_200.fee_lcu, r["cc1 lcu fee"]),
            "fee_500": _same(p.quote_500.fee_lcu, r["cc2 lcu fee"]),
            "fx_200": _same(p.quote_200.fx_rate, r["cc1 lcu fx rate"]),
            "cost_200": _same(p.quote_200.total_cost_pct, r["cc1 total cost %"]),
            "cost_500": _same(p.quote_500.total_cost_pct, r["cc2 total cost %"]),
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            problems.append(f"{corridor_id} id {p.rpw_id}: mismatch in {', '.join(failed)}")
        lines.append(
            f"{corridor_id} id {p.rpw_id} {p.firm}: cost@200={p.quote_200.total_cost_pct}% "
            f"cost@500={p.quote_500.total_cost_pct}% -> {'OK' if not failed else 'MISMATCH'}"
        )

    if problems:
        raise ValueError("source verification failed:\n" + "\n".join(problems))
    return lines
