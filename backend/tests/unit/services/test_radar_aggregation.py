from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from google.api_core.exceptions import FailedPrecondition

from app.repositories.radar_repo import RadarRepository
from app.schemas.radar import RadarEntity, RadarReport, RadarValidation
from app.services.radar.aggregation import (
    MIN_INCIDENTS_FOR_HIGH_RISK,
    MIN_INCIDENTS_TO_FLAG,
    MIN_INCIDENTS_TO_RATE,
    update_entity_risk,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
EARLIER = NOW - timedelta(days=10)
LATER = NOW + timedelta(days=1)


def _report(**over: Any) -> RadarReport:
    values: dict[str, Any] = {
        "entity_type": "money_transfer_operator",
        "entity_name": "Example Remit",
        "entity_slug": "example-remit",
        "violation_type": "hidden_fees",
        "corridor_id": "SG-IN",
        "host_country": None,
        "description": "They showed one rate and charged another.",
        "language": "en",
        "cluster_id": "r1",
        "source": "user",
        "validation": RadarValidation(spam_score=0.0, category_confidence=0.9, model="m"),
        "created_at": NOW,
    }
    return RadarReport.model_validate(values | over)


def _entity(**over: Any) -> RadarEntity:
    values: dict[str, Any] = {
        "name": "Example Remit",
        "slug": "example-remit",
        "entity_type": "money_transfer_operator",
        "report_count": 1,
        "incident_count": 1,
        "first_reported_at": EARLIER,
        "last_reported_at": EARLIER,
        "risk_level": "low",
        "flagged": False,
        "updated_at": EARLIER,
    }
    return RadarEntity.model_validate(values | over)


class FakeRadar:
    def __init__(self, entity: RadarEntity | None = None, *, boom: bool = False) -> None:
        self.entity = entity.model_dump() if entity else None
        self.saved: RadarEntity | None = None
        self.boom = boom

    def get_entity(self, slug: str) -> dict[str, Any] | None:
        if self.boom:
            raise FailedPrecondition("down")
        return self.entity

    def set_entity(self, entity: RadarEntity) -> None:
        if self.boom:
            raise FailedPrecondition("down")
        self.saved = entity


async def test_the_first_report_creates_a_low_risk_unflagged_unrated_entity() -> None:
    radar = FakeRadar(entity=None)
    report = _report(cluster_id="r1")

    await update_entity_risk(report, "r1", cast(RadarRepository, radar), NOW)

    entity = radar.saved
    assert entity is not None
    assert (entity.report_count, entity.incident_count) == (1, 1)
    assert entity.risk_level == "low"
    assert entity.flagged is False
    assert entity.community_rating is None  # below MIN_INCIDENTS_TO_RATE
    assert entity.name == "Example Remit" and entity.entity_type == "money_transfer_operator"
    assert entity.corridors == ["SG-IN"]
    assert entity.violation_counts == {"hidden_fees": 1}
    assert entity.first_reported_at == NOW and entity.last_reported_at == NOW
    assert entity.updated_at == NOW


async def test_a_report_joining_an_existing_cluster_is_one_more_report_not_a_new_incident() -> None:
    radar = FakeRadar(entity=_entity(report_count=1, incident_count=1))
    report = _report(cluster_id="r_first")  # joined an earlier cluster, not its own

    await update_entity_risk(report, "r2", cast(RadarRepository, radar), NOW)

    entity = radar.saved
    assert entity is not None
    assert (entity.report_count, entity.incident_count) == (2, 1)


async def test_a_report_starting_its_own_cluster_is_a_new_incident() -> None:
    radar = FakeRadar(entity=_entity(report_count=1, incident_count=1))
    report = _report(cluster_id="r2")

    await update_entity_risk(report, "r2", cast(RadarRepository, radar), NOW)

    entity = radar.saved
    assert entity is not None
    assert (entity.report_count, entity.incident_count) == (2, 2)


@pytest.mark.parametrize(
    ("incident_count", "expected_risk", "expected_flagged", "expected_rating"),
    [
        (MIN_INCIDENTS_TO_RATE - 1, "low", False, None),
        (MIN_INCIDENTS_TO_FLAG, "medium", True, 4.0),
        (MIN_INCIDENTS_FOR_HIGH_RISK - 1, "medium", True, 3.0),
        (MIN_INCIDENTS_FOR_HIGH_RISK, "high", True, 2.5),
        (20, "high", True, 0.0),  # floored, never negative
    ],
)
async def test_risk_level_flagged_and_rating_follow_incident_count(
    incident_count: int, expected_risk: str, expected_flagged: bool, expected_rating: float | None
) -> None:
    # incident_count - 1 existing incidents, then one more report starts a new (final) one.
    radar = FakeRadar(
        entity=_entity(report_count=incident_count, incident_count=incident_count - 1)
    )
    report = _report(cluster_id="new")

    await update_entity_risk(report, "new", cast(RadarRepository, radar), NOW)

    entity = radar.saved
    assert entity is not None
    assert entity.incident_count == incident_count
    assert entity.risk_level == expected_risk
    assert entity.flagged is expected_flagged
    assert entity.community_rating == expected_rating


async def test_a_new_corridor_is_appended_without_duplicating_an_existing_one() -> None:
    radar = FakeRadar(entity=_entity(corridors=["SG-IN"]))
    report = _report(corridor_id="SG-IN")  # same corridor again

    await update_entity_risk(report, "r2", cast(RadarRepository, radar), NOW)
    assert radar.saved is not None and radar.saved.corridors == ["SG-IN"]

    radar2 = FakeRadar(entity=_entity(corridors=["SG-IN"]))
    await update_entity_risk(_report(corridor_id="SG-PH"), "r3", cast(RadarRepository, radar2), NOW)
    assert radar2.saved is not None and radar2.saved.corridors == ["SG-IN", "SG-PH"]


async def test_host_country_is_tracked_the_same_way_as_corridors() -> None:
    radar = FakeRadar(entity=_entity(host_countries=[]))
    report = _report(corridor_id=None, host_country="SG")

    await update_entity_risk(report, "r2", cast(RadarRepository, radar), NOW)

    assert radar.saved is not None and radar.saved.host_countries == ["SG"]


async def test_violation_counts_accumulate_per_type() -> None:
    radar = FakeRadar(entity=_entity(violation_counts={"hidden_fees": 2, "wage_theft": 1}))
    report = _report(violation_type="hidden_fees")

    await update_entity_risk(report, "r2", cast(RadarRepository, radar), NOW)

    assert radar.saved is not None
    assert radar.saved.violation_counts == {"hidden_fees": 3, "wage_theft": 1}


async def test_first_and_last_reported_at_track_the_full_span() -> None:
    radar = FakeRadar(entity=_entity(first_reported_at=NOW, last_reported_at=NOW))

    await update_entity_risk(_report(created_at=EARLIER), "r2", cast(RadarRepository, radar), NOW)
    assert radar.saved is not None
    assert radar.saved.first_reported_at == EARLIER and radar.saved.last_reported_at == NOW

    radar2 = FakeRadar(entity=_entity(first_reported_at=NOW, last_reported_at=NOW))
    await update_entity_risk(_report(created_at=LATER), "r3", cast(RadarRepository, radar2), NOW)
    assert radar2.saved is not None
    assert radar2.saved.first_reported_at == NOW and radar2.saved.last_reported_at == LATER


async def test_a_firestore_failure_is_swallowed_not_raised() -> None:
    radar = FakeRadar(boom=True)

    await update_entity_risk(_report(), "r1", cast(RadarRepository, radar), NOW)  # must not raise

    assert radar.saved is None
