"""Exploitation Radar alert cron (NF-P3-004): the AGG subgraph of the pipeline
(docs/mermaid/exploitation-radar-pipeline.mmd) — detect surges, write and expire alerts.

Runs every 6 hours (infra/cloud-scheduler/radar-aggregation.yaml). Reads raw `radar_reports`
directly rather than NF-P3-003's `radar_entities`: entity aggregation keeps running totals,
never a time-windowed count, and a surge is inherently about a recent window versus its own
baseline. Who gets told about a freshly created alert, and in what words, is `notify.py`.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import get_args

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.integrations.gemini import GeminiClient
from app.repositories.radar_repo import RadarRepository
from app.repositories.user_repo import UserRepository
from app.schemas.radar import RadarReport, RadarViolationType
from app.schemas.radar_alert import (
    AggregateRadarResponse,
    RadarAlert,
    RadarAlertHeader,
    RadarAlertSeverity,
)
from app.schemas.remittance_compare import CorridorId
from app.services.radar.notify import notify_new_alert

logger = logging.getLogger(__name__)

# Both already appear as the illustrative values in radar_alerts' own doc example
# (radar.md), so they're treated as intentional, not arbitrary.
WINDOW_DAYS = 7
BASELINE_DAYS = WINDOW_DAYS

# A surge needs at least this many reports in the window, and more than its own baseline:
# one report is an account, not yet a pattern (same reasoning as NF-P3-003's flagging floor).
MIN_REPORTS_TO_ALERT = 2
WARNING_AT = 3
CRITICAL_AT = 5


@dataclass(frozen=True)
class Surge:
    entity_slug: str
    entity_name: str
    violation_type: RadarViolationType
    report_count: int
    baseline_count: int


def _severity(report_count: int) -> RadarAlertSeverity:
    if report_count >= CRITICAL_AT:
        return "critical"
    if report_count >= WARNING_AT:
        return "warning"
    return "info"


def _detect_surges(
    window_reports: list[RadarReport], baseline_reports: list[RadarReport]
) -> list[Surge]:
    """Pure: which entities in the window qualify for a new alert. Easy to unit test."""
    baseline_counts = Counter(r.entity_slug for r in baseline_reports)
    window_counts = Counter(r.entity_slug for r in window_reports)
    latest_name: dict[str, str] = {}
    violations: dict[str, Counter[RadarViolationType]] = {}
    for report in window_reports:
        latest_name[report.entity_slug] = report.entity_name
        violations.setdefault(report.entity_slug, Counter())[report.violation_type] += 1

    surges = []
    for slug, count in window_counts.items():
        baseline = baseline_counts.get(slug, 0)
        if count >= MIN_REPORTS_TO_ALERT and count > baseline:
            violation_type = violations[slug].most_common(1)[0][0]
            surges.append(Surge(slug, latest_name[slug], violation_type, count, baseline))
    return surges


async def _process_corridor(
    corridor_id: str, radar: RadarRepository, now: datetime
) -> tuple[list[tuple[str, RadarAlert]], int]:
    """Detect surges and expire stale alerts on one corridor.

    Returns:
        Newly created (alert_id, RadarAlert) pairs, and how many alerts were expired.
    """
    window_start = now - timedelta(days=WINDOW_DAYS)
    baseline_start = now - timedelta(days=WINDOW_DAYS + BASELINE_DAYS)

    raw_reports = await run_in_threadpool(radar.reports_since, corridor_id, baseline_start)
    reports = [RadarReport.model_validate(raw) for raw in raw_reports]
    window_reports = [r for r in reports if r.created_at >= window_start]
    baseline_reports = [r for r in reports if r.created_at < window_start]

    created: list[tuple[str, RadarAlert]] = []
    for surge in _detect_surges(window_reports, baseline_reports):
        existing = await run_in_threadpool(radar.get_active_alert, corridor_id, surge.entity_slug)
        if existing is not None:
            continue  # already alerted; don't recreate one every 6 hours for the same surge
        alert_id = radar.new_alert_id(corridor_id)
        alert = RadarAlert(
            corridor_id=corridor_id,
            entity_slug=surge.entity_slug,
            entity_name=surge.entity_name,
            violation_type=surge.violation_type,
            window_days=WINDOW_DAYS,
            report_count=surge.report_count,
            baseline_count=surge.baseline_count,
            severity=_severity(surge.report_count),
            status="active",
            created_at=now,
            expires_at=now + timedelta(days=WINDOW_DAYS),
        )
        await run_in_threadpool(radar.create_alert, corridor_id, alert_id, alert)
        created.append((alert_id, alert))

    expired_count = 0
    for alert_id, raw in await run_in_threadpool(radar.list_active_alerts, corridor_id):
        if raw["expires_at"] <= now:
            await run_in_threadpool(radar.expire_alert, corridor_id, alert_id)
            expired_count += 1

    if created or expired_count:
        still_active = await run_in_threadpool(radar.list_active_alerts, corridor_id)
        header = RadarAlertHeader(
            corridor_id=corridor_id, active_count=len(still_active), updated_at=now
        )
        await run_in_threadpool(radar.set_alert_header, header)

    return created, expired_count


async def run_aggregation(
    radar: RadarRepository, users: UserRepository, gemini: GeminiClient, now: datetime
) -> AggregateRadarResponse:
    """Scan every corridor, write/expire alerts, and notify subscribed workers of new ones."""
    corridors = get_args(CorridorId)
    alerts_created = 0
    alerts_expired = 0
    notifications_sent = 0

    for corridor_id in corridors:
        try:
            created, expired = await _process_corridor(corridor_id, radar, now)
        except GoogleAPICallError:
            # A missing composite index (FailedPrecondition) or a Firestore blip on one
            # corridor must not stop the other five; the traceback keeps it visible in logs.
            logger.exception("radar_surge_detection_failed corridor=%s", corridor_id)
            continue
        alerts_expired += expired
        alerts_created += len(created)
        for alert_id, alert in created:
            notifications_sent += await notify_new_alert(alert_id, alert, radar, users, gemini, now)

    logger.info(
        "radar_aggregation corridors=%d created=%d expired=%d notified=%d",
        len(corridors),
        alerts_created,
        alerts_expired,
        notifications_sent,
    )
    return AggregateRadarResponse(
        corridors_scanned=len(corridors),
        alerts_created=alerts_created,
        alerts_expired=alerts_expired,
        notifications_sent=notifications_sent,
        completed_at=now,
    )
