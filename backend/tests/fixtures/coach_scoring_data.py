"""The stored data the score reads, taken from the curated source files (NF-FC-011).

The same JSON the loaders write to Firestore (`data-scripts/data/source/`), so a test uses the real
cost baselines and the real labor-law rules, in the shape the repositories return them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[3] / "data-scripts" / "data" / "source"
HOSTS = ("SG", "KR", "MY", "JP", "HK", "AU")


def baseline(host: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (SOURCE / "cost-baselines" / f"{host}.json").read_text(encoding="utf-8")
    )
    return data


def law_rules(host: str) -> dict[str, dict[str, Any]]:
    """`labor_laws/{host}/rules` as `LaborLawRepository.get_rules` returns it."""
    data = json.loads((SOURCE / "labor-laws" / f"{host}.json").read_text(encoding="utf-8"))
    rules: dict[str, dict[str, Any]] = data["rules"]
    return rules


class FakeBaselines:
    def __init__(self, missing: tuple[str, ...] = ()) -> None:
        self.missing = missing

    def get_baseline(self, host: str) -> dict[str, Any] | None:
        return None if host in self.missing else baseline(host)


class FakeLaws:
    def __init__(self, without_fee_rule: tuple[str, ...] = ()) -> None:
        self.without = without_fee_rule

    def get_version(self, country: str) -> int | None:
        return 1

    def get_rules(self, country: str, version: int | None = None) -> dict[str, dict[str, Any]]:
        rules = law_rules(country)
        if country in self.without:
            rules = {k: v for k, v in rules.items() if k != "recruitment_fees"}
        return rules


class FakeRates:
    def __init__(self, rates: dict[str, float]) -> None:
        self.rates = rates

    def get_rate(self, pair_id: str) -> dict[str, Any] | None:
        return {"rate": self.rates[pair_id]} if pair_id in self.rates else None
