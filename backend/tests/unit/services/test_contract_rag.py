from __future__ import annotations

from typing import Any, cast

import pytest

from app.repositories.labor_law_repo import LaborLawRepository
from app.services.contract.rag import LaborLawNotFoundError, get_labor_law_context

pytestmark = pytest.mark.anyio


def _rule(**changes: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "coverage": "regulated",
        "title": "Working hours and breaks",
        "summary": "No more than 8 hours a day or 40 hours a week.",
        "variants": [
            {
                "applies_to": ["all"],
                "requirements": ["No more than 40 hours per week (Art. 32)."],
                "limits": {"weekly_hours_limit": {"value": 40, "unit": "hours", "period": "week"}},
                "penalty": None,
                "enforced_by": "Labour inspectorate",
            }
        ],
        "references": [{"law": "Labor Standards Act", "section": "Art. 32", "url": "https://x"}],
        "confidence": "high",
        "notes": None,
    }
    return payload | changes


class FakeRepo:
    def __init__(self, version: int | None, rules: dict[str, dict[str, Any]]) -> None:
        self.version = version
        self.rules = rules
        self.countries_asked: list[str] = []

    def get_version(self, country: str) -> int | None:
        self.countries_asked.append(country)
        return self.version

    def get_rules(self, country: str, version: int | None = None) -> dict[str, dict[str, Any]]:
        return self.rules


async def test_returns_every_curated_category_with_law_version() -> None:
    repo = FakeRepo(3, {"working_hours": _rule(), "minimum_wage": _rule(title="Minimum wage")})

    result = await get_labor_law_context("JP", "domestic_worker", cast(LaborLawRepository, repo))

    assert result.country == "JP"
    assert result.job_type == "domestic_worker"
    assert result.law_version == 3
    assert [r.category for r in result.rules] == ["minimum_wage", "working_hours"]
    assert repo.countries_asked == ["JP"]


async def test_a_job_type_variant_overrides_the_all_variant() -> None:
    rule = _rule(
        variants=[
            {
                "applies_to": ["all"],
                "requirements": ["The general rule applies (Art. 32)."],
                "limits": {},
                "penalty": None,
                "enforced_by": None,
            },
            {
                "applies_to": ["domestic_worker"],
                "requirements": ["Domestic workers are excluded (Art. 116(2))."],
                "limits": {},
                "penalty": None,
                "enforced_by": None,
            },
        ]
    )
    repo = FakeRepo(1, {"working_hours": rule})

    for_domestic = await get_labor_law_context(
        "JP", "domestic_worker", cast(LaborLawRepository, repo)
    )
    for_care = await get_labor_law_context("JP", "care_worker", cast(LaborLawRepository, repo))

    assert for_domestic.rules[0].applicable_variant.applies_to == ["domestic_worker"]
    assert for_domestic.rules[0].applicable_variant.requirements == [
        "Domestic workers are excluded (Art. 116(2))."
    ]
    assert for_care.rules[0].applicable_variant.applies_to == ["all"]
    # The full variant list is kept even when one is picked out as applicable.
    assert len(for_care.rules[0].variants) == 2


async def test_missing_version_raises_not_found() -> None:
    repo = FakeRepo(None, {"working_hours": _rule()})

    with pytest.raises(LaborLawNotFoundError):
        await get_labor_law_context("HK", "care_worker", cast(LaborLawRepository, repo))


async def test_empty_rules_raises_not_found_even_with_a_version() -> None:
    repo = FakeRepo(1, {})

    with pytest.raises(LaborLawNotFoundError):
        await get_labor_law_context("HK", "care_worker", cast(LaborLawRepository, repo))
