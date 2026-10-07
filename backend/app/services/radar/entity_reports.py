"""Exploitation Radar: an entity's report list (NF-P3-008's profile page).

`radar_reports` has no client access (`firestore.rules`) — the entity's own aggregated
profile (`radar_entities/{slug}`) is read directly by the frontend (it's client-readable
and holds no personal data), but its individual reports are served through here, which
strips `reporter_hash` and the classification internals.
"""

from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from app.repositories.radar_repo import RadarRepository
from app.schemas.radar import RadarReport
from app.schemas.radar_report import RadarReportSummary


async def list_entity_reports(slug: str, radar: RadarRepository) -> list[RadarReportSummary]:
    """Every report about one entity, newest first. Empty for an unknown slug, same as an
    entity with no reports — the two are indistinguishable from `radar_reports` alone."""
    raw = await run_in_threadpool(radar.list_by_entity, slug)
    summaries = []
    for report_id, data in raw:
        report = RadarReport.model_validate(data)
        summaries.append(
            RadarReportSummary(
                report_id=report_id,
                violation_type=report.violation_type,
                description=report.description,
                summary=report.summary,
                language=report.language,
                corridor_id=report.corridor_id,
                host_country=report.host_country,
                source=report.source,
                scam=report.scam,
                created_at=report.created_at,
            )
        )
    return summaries
