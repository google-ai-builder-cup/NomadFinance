from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.repositories.radar_repo import RadarRepository
from app.schemas.radar import RadarValidation
from app.services.radar.entity_reports import list_entity_reports

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _report(**over: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "entity_type": "money_transfer_operator",
        "entity_name": "Example Remit",
        "entity_slug": "example-remit",
        "violation_type": "hidden_fees",
        "corridor_id": "SG-IN",
        "description": "They showed one rate and charged another.",
        "language": "en",
        "cluster_id": "r1",
        "source": "user",
        "reporter_hash": "abc123",
        "validation": RadarValidation(spam_score=0.0, category_confidence=0.9, model="m"),
        "summary": "Operator charged a worse rate than shown.",
        "created_at": NOW,
    }
    return values | over


class FakeRadar:
    def __init__(self, reports: list[tuple[str, dict[str, Any]]]) -> None:
        self.reports = reports

    def list_by_entity(self, slug: str) -> list[tuple[str, dict[str, Any]]]:
        return self.reports


async def test_returns_a_summary_per_report() -> None:
    radar = FakeRadar([("r1", _report())])

    summaries = await list_entity_reports("example-remit", cast(RadarRepository, radar))

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.report_id == "r1"
    assert summary.violation_type == "hidden_fees"
    assert summary.summary == "Operator charged a worse rate than shown."
    assert summary.created_at == NOW


async def test_never_includes_reporter_hash_or_validation_internals() -> None:
    radar = FakeRadar([("r1", _report())])

    summaries = await list_entity_reports("example-remit", cast(RadarRepository, radar))

    dumped = summaries[0].model_dump()
    assert "reporter_hash" not in dumped
    assert "validation" not in dumped
    assert "spam_score" not in str(dumped)


async def test_an_unknown_slug_or_a_reportless_entity_is_an_empty_list() -> None:
    radar = FakeRadar([])

    summaries = await list_entity_reports("no-such-entity", cast(RadarRepository, radar))

    assert summaries == []


async def test_a_contract_signal_report_with_no_summary_is_kept_with_summary_none() -> None:
    radar = FakeRadar([("r1", _report(source="contract_signal", reporter_hash=None, summary=None))])

    summaries = await list_entity_reports("example-remit", cast(RadarRepository, radar))

    assert summaries[0].summary is None
    assert summaries[0].source == "contract_signal"
