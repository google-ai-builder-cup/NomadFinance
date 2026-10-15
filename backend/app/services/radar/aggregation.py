"""Exploitation Radar steps 8 and 9 (NF-P3-003): recompute an entity's risk profile after a
new report is stored.

Called for every report, whatever its source (NF-P3-001 user reports, NF-P2-021 contract
signals): a contract-flagged employer only ever becomes `flagged` if this runs on that path
too (cross-pillar flow #4, NF-P3-023). Best effort, the same treatment `intake.py` gives the
embedding write: a Firestore failure here costs this entity's own updated badge/rating, never
the report that was just stored.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.repositories.radar_repo import RadarRepository
from app.schemas.radar import RadarEntity, RadarReport, RadarRiskLevel

logger = logging.getLogger(__name__)

# incident_count below this: not enough signal for a rating or a public flag. A single
# report, however serious, is one account, not yet a confirmed pattern (this pillar is
# "pattern detection", not first-complaint-wins).
MIN_INCIDENTS_TO_RATE = 2
MIN_INCIDENTS_TO_FLAG = 2
MIN_INCIDENTS_FOR_HIGH_RISK = 5

# Perfect score at 0 incidents, floored at 0 by 10. Linear and easy to retune once real
# demo data (NF-P3-005) gives something to calibrate against; see the runbook for why this
# stays this simple for now.
RATING_START = 5.0
RATING_STEP_PER_INCIDENT = 0.5


def _risk_level(incident_count: int) -> RadarRiskLevel:
    if incident_count >= MIN_INCIDENTS_FOR_HIGH_RISK:
        return "high"
    if incident_count >= MIN_INCIDENTS_TO_FLAG:
        return "medium"
    return "low"


def _community_rating(incident_count: int) -> float | None:
    if incident_count < MIN_INCIDENTS_TO_RATE:
        return None
    return round(max(0.0, RATING_START - RATING_STEP_PER_INCIDENT * incident_count), 1)


def _new_entity(report: RadarReport, now: datetime) -> RadarEntity:
    return RadarEntity(
        name=report.entity_name,
        slug=report.entity_slug,
        entity_type=report.entity_type,
        report_count=0,
        incident_count=0,
        first_reported_at=report.created_at,
        last_reported_at=report.created_at,
        risk_level="low",
        flagged=False,
        updated_at=now,
    )


def _apply_report(entity: RadarEntity, report: RadarReport, is_new_incident: bool) -> RadarEntity:
    """The entity's profile with one more report folded in. Pure; easy to unit test."""
    corridors = entity.corridors
    if report.corridor_id is not None and report.corridor_id not in corridors:
        corridors = [*corridors, report.corridor_id]
    host_countries = entity.host_countries
    if report.host_country is not None and report.host_country not in host_countries:
        host_countries = [*host_countries, report.host_country]
    violation_counts = dict(entity.violation_counts)
    violation_counts[report.violation_type] = violation_counts.get(report.violation_type, 0) + 1
    incident_count = entity.incident_count + (1 if is_new_incident else 0)

    return entity.model_copy(
        update={
            "corridors": corridors,
            "host_countries": host_countries,
            "report_count": entity.report_count + 1,
            "incident_count": incident_count,
            "violation_counts": violation_counts,
            "first_reported_at": min(entity.first_reported_at, report.created_at),
            "last_reported_at": max(entity.last_reported_at, report.created_at),
            "community_rating": _community_rating(incident_count),
            "risk_level": _risk_level(incident_count),
            "flagged": incident_count >= MIN_INCIDENTS_TO_FLAG,
        }
    )


async def update_entity_risk(
    report: RadarReport, report_id: str, radar: RadarRepository, now: datetime
) -> None:
    """Steps 8 and 9: fold one freshly stored report into its entity's profile.

    Args:
        report: The report that was just written (its own `cluster_id` says whether it
            started a new incident or joined one).
        report_id: The report's own id; `report.cluster_id == report_id` means it started a
            new cluster (a new incident), same test `clustering.find_cluster` result implies.
        radar: Repository for `radar_entities/{slug}`.
        now: Current time for `updated_at`; report timestamps use `report.created_at`.

    Not transactional: two reports about the same entity landing at the same instant could
    race and one update could be lost. Acceptable for this prototype's expected concurrency;
    not something this task fixes.
    """
    is_new_incident = report.cluster_id == report_id
    try:
        existing = await run_in_threadpool(radar.get_entity, report.entity_slug)
        entity = RadarEntity.model_validate(existing) if existing else _new_entity(report, now)
        updated = _apply_report(entity, report, is_new_incident).model_copy(
            update={"updated_at": now}
        )
        await run_in_threadpool(radar.set_entity, updated)
    except GoogleAPICallError:
        logger.exception("radar_entity_update_failed slug=%s", report.entity_slug)
