from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.radar import RadarViolationType

RadarAlertSeverity = Literal["info", "warning", "critical"]
RadarAlertStatus = Literal["active", "expired"]


class RadarAlert(BaseModel):
    """`radar_alerts/{corridor}/current/{alertId}` (docs/data-model/collections/radar.md).
    Backend-only; no client ever writes this."""

    type: Literal["report_surge"] = "report_surge"
    corridor_id: str
    entity_slug: str
    entity_name: str
    violation_type: RadarViolationType
    window_days: int
    report_count: int
    baseline_count: int
    severity: RadarAlertSeverity
    status: RadarAlertStatus
    created_at: datetime
    expires_at: datetime
    notified_at: datetime | None = None
    schema_version: int = 1


class RadarAlertHeader(BaseModel):
    """`radar_alerts/{corridor}` (radar.md): what a corridor list reads for a badge count
    without loading every alert."""

    corridor_id: str
    active_count: int = Field(ge=0)
    updated_at: datetime


class AlertNotificationText(BaseModel):
    """Gemini's answer for one alert in one language (`radar/alert_notification.v1`)."""

    title: str
    body: str


class AggregateRadarResponse(BaseModel):
    """Result of `POST /api/v1/internal/aggregate-radar` (NF-P3-004)."""

    corridors_scanned: int
    alerts_created: int
    alerts_expired: int
    notifications_sent: int
    completed_at: datetime
