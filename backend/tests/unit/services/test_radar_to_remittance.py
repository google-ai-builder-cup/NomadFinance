from __future__ import annotations

from typing import Any, cast

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.repositories.radar_repo import RadarRepository
from app.services.cross_pillar.radar_to_remittance import (
    flag_providers,
    flagged_slugs,
    mark_flagged,
)
from tests.unit.services.test_remittance_recommender import _comparison, _provider

pytestmark = pytest.mark.anyio


def _comparison_of(*firms: str) -> Any:
    return _comparison(*(_provider(i + 1, firm, i + 1) for i, firm in enumerate(firms)))


def test_slugs_include_the_aliases_of_each_flagged_operator() -> None:
    entities = [
        {"slug": "quickcash-remit", "aliases": ["Quick Cash Remit"], "report_count": 4},
        {"slug": "other", "report_count": 2},
    ]

    assert flagged_slugs(entities) == {"quickcash-remit": 4, "quick-cash-remit": 4, "other": 2}


def test_mark_flagged_matches_by_slug_and_keeps_the_ranking() -> None:
    comparison = _comparison_of("InstaReM", "Quick Cash Remit", "Wise")

    marked = mark_flagged(comparison, {"quick-cash-remit": 4})

    assert [(p.firm, p.rank, p.flagged, p.flag_report_count) for p in marked.providers] == [
        ("InstaReM", 1, False, None),
        ("Quick Cash Remit", 2, True, 4),
        ("Wise", 3, False, None),
    ]


class FakeRadar:
    def __init__(self, entities: list[dict[str, Any]] | Exception) -> None:
        self.entities = entities
        self.asked: list[str] = []

    def flagged_entities(self, entity_type: str) -> list[dict[str, Any]]:
        self.asked.append(entity_type)
        if isinstance(self.entities, Exception):
            raise self.entities
        return self.entities


async def test_flag_providers_reads_only_flagged_operators() -> None:
    radar = FakeRadar([{"slug": "wise", "report_count": 3}])

    marked = await flag_providers(_comparison_of("InstaReM", "Wise"), cast(RadarRepository, radar))

    assert radar.asked == ["money_transfer_operator"]
    assert [p.flagged for p in marked.providers] == [False, True]


async def test_a_radar_read_failure_leaves_the_comparison_unflagged() -> None:
    radar = FakeRadar(ServiceUnavailable("firestore blip"))  # type: ignore[no-untyped-call]
    comparison = _comparison_of("InstaReM", "Wise")

    assert await flag_providers(comparison, cast(RadarRepository, radar)) == comparison
