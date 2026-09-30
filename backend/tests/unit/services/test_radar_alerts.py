from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest
from google.api_core.exceptions import FailedPrecondition

from app.integrations.gemini import GeminiClient
from app.repositories.radar_repo import RadarRepository
from app.repositories.user_repo import UserRepository
from app.schemas.radar import RadarReport, RadarValidation
from app.schemas.radar_alert import RadarAlert, RadarAlertHeader
from app.services.radar.alerts import (
    MIN_REPORTS_TO_ALERT,
    WINDOW_DAYS,
    Surge,
    _detect_surges,
    _severity,
    run_aggregation,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
IN_WINDOW = NOW - timedelta(days=2)
IN_BASELINE = NOW - timedelta(days=10)


def _report(**over: Any) -> RadarReport:
    values: dict[str, Any] = {
        "entity_type": "money_transfer_operator",
        "entity_name": "Example Remit",
        "entity_slug": "example-remit",
        "violation_type": "hidden_fees",
        "corridor_id": "SG-IN",
        "description": "x",
        "language": "en",
        "cluster_id": "r1",
        "source": "user",
        "validation": RadarValidation(spam_score=0.0, category_confidence=0.9, model="m"),
        "created_at": IN_WINDOW,
    }
    return RadarReport.model_validate(values | over)


# --- _detect_surges (pure) -------------------------------------------------------------


def test_a_new_entity_with_enough_reports_and_no_baseline_is_a_surge() -> None:
    window = [_report(), _report()]

    surges = _detect_surges(window, [])

    assert surges == [Surge("example-remit", "Example Remit", "hidden_fees", 2, 0)]


def test_below_the_minimum_report_count_is_not_a_surge() -> None:
    assert _detect_surges([_report()], []) == []


def test_at_or_below_baseline_is_not_a_surge() -> None:
    window = [_report(), _report()]
    baseline = [_report(), _report()]  # steady state, not a surge

    assert _detect_surges(window, baseline) == []


def test_above_baseline_and_the_minimum_is_a_surge() -> None:
    window = [_report(), _report(), _report()]
    baseline = [_report()]

    surges = _detect_surges(window, baseline)

    assert surges == [Surge("example-remit", "Example Remit", "hidden_fees", 3, 1)]


def test_the_most_reported_violation_type_in_the_window_is_used() -> None:
    window = [
        _report(violation_type="hidden_fees"),
        _report(violation_type="hidden_fees"),
        _report(violation_type="wage_theft"),
    ]

    surges = _detect_surges(window, [])

    assert surges[0].violation_type == "hidden_fees"


def test_different_entities_are_scored_independently() -> None:
    window = [
        _report(entity_slug="a", entity_name="A"),
        _report(entity_slug="a", entity_name="A"),
        _report(entity_slug="b", entity_name="B"),
    ]

    surges = _detect_surges(window, [])

    assert {s.entity_slug for s in surges} == {"a"}  # "b" has only 1 report


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "info"), (MIN_REPORTS_TO_ALERT, "info"), (3, "warning"), (4, "warning"), (5, "critical")],
)
def test_severity_bands(count: int, expected: str) -> None:
    assert _severity(count) == expected


# --- run_aggregation (orchestration) ----------------------------------------------------


class FakeRadar:
    def __init__(self, reports: list[RadarReport] | None = None) -> None:
        self.reports = reports or []
        self.active_alerts: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self.headers: dict[str, RadarAlertHeader] = {}
        self.created_alerts: list[tuple[str, str, RadarAlert]] = []
        self.notified: list[tuple[str, str, datetime]] = []
        self._next_id = 0
        self.boom_corridors: set[str] = set()

    def reports_since(self, corridor_id: str, since: datetime) -> list[dict[str, Any]]:
        if corridor_id in self.boom_corridors:
            raise FailedPrecondition("no matching index")
        return [
            r.model_dump()
            for r in self.reports
            if r.corridor_id == corridor_id and r.created_at >= since
        ]

    def get_active_alert(self, corridor_id: str, entity_slug: str) -> dict[str, Any] | None:
        for _id, alert in self.active_alerts.get(corridor_id, []):
            if alert["entity_slug"] == entity_slug:
                return alert
        return None

    def new_alert_id(self, corridor_id: str) -> str:
        self._next_id += 1
        return f"a{self._next_id}"

    def create_alert(self, corridor_id: str, alert_id: str, alert: RadarAlert) -> None:
        self.created_alerts.append((corridor_id, alert_id, alert))
        self.active_alerts.setdefault(corridor_id, []).append((alert_id, alert.model_dump()))

    def list_active_alerts(self, corridor_id: str) -> list[tuple[str, dict[str, Any]]]:
        return list(self.active_alerts.get(corridor_id, []))

    def expire_alert(self, corridor_id: str, alert_id: str) -> None:
        self.active_alerts[corridor_id] = [
            (aid, a) for aid, a in self.active_alerts.get(corridor_id, []) if aid != alert_id
        ]

    def set_alert_header(self, header: RadarAlertHeader) -> None:
        self.headers[header.corridor_id] = header

    def set_alert_notified(self, corridor_id: str, alert_id: str, notified_at: datetime) -> None:
        self.notified.append((corridor_id, alert_id, notified_at))


class FakeUsers:
    def by_host_and_home(self, host_country: str, home_country: str) -> list[tuple[str, Any]]:
        return []

    def subscribed_to_corridor(self, corridor_id: str) -> list[tuple[str, Any]]:
        return []


class FakeGemini:
    async def generate_structured(self, **kwargs: Any) -> Any:
        raise AssertionError("no subscribers were set up; Gemini must not be called")


async def test_a_surge_creates_one_alert_and_updates_the_header() -> None:
    radar = FakeRadar([_report(), _report()])

    result = await run_aggregation(
        cast(RadarRepository, radar),
        cast(UserRepository, FakeUsers()),
        cast(GeminiClient, FakeGemini()),
        NOW,
    )

    assert result.alerts_created == 1
    assert result.alerts_expired == 0
    corridor_id, alert_id, alert = radar.created_alerts[0]
    assert (corridor_id, alert.entity_slug, alert.status) == ("SG-IN", "example-remit", "active")
    assert radar.headers["SG-IN"].active_count == 1


async def test_an_existing_active_alert_is_not_duplicated() -> None:
    radar = FakeRadar([_report(), _report()])
    radar.active_alerts["SG-IN"] = [
        (
            "existing",
            RadarAlert(
                corridor_id="SG-IN",
                entity_slug="example-remit",
                entity_name="Example Remit",
                violation_type="hidden_fees",
                window_days=WINDOW_DAYS,
                report_count=2,
                baseline_count=0,
                severity="info",
                status="active",
                created_at=NOW - timedelta(days=1),
                expires_at=NOW + timedelta(days=6),
            ).model_dump(),
        )
    ]

    result = await run_aggregation(
        cast(RadarRepository, radar),
        cast(UserRepository, FakeUsers()),
        cast(GeminiClient, FakeGemini()),
        NOW,
    )

    assert result.alerts_created == 0
    assert radar.created_alerts == []


async def test_an_alert_past_its_expiry_is_marked_expired() -> None:
    radar = FakeRadar([])
    radar.active_alerts["SG-IN"] = [
        (
            "old",
            RadarAlert(
                corridor_id="SG-IN",
                entity_slug="example-remit",
                entity_name="Example Remit",
                violation_type="hidden_fees",
                window_days=WINDOW_DAYS,
                report_count=2,
                baseline_count=0,
                severity="info",
                status="active",
                created_at=NOW - timedelta(days=10),
                expires_at=NOW - timedelta(days=1),  # already past
            ).model_dump(),
        )
    ]

    result = await run_aggregation(
        cast(RadarRepository, radar),
        cast(UserRepository, FakeUsers()),
        cast(GeminiClient, FakeGemini()),
        NOW,
    )

    assert result.alerts_expired == 1
    assert radar.active_alerts["SG-IN"] == []  # removed from the active list
    assert radar.headers["SG-IN"].active_count == 0


async def test_one_corridors_index_failure_does_not_stop_the_others() -> None:
    radar = FakeRadar([_report(corridor_id="AU-IN"), _report(corridor_id="AU-IN")])
    radar.boom_corridors = {"SG-IN"}

    result = await run_aggregation(
        cast(RadarRepository, radar),
        cast(UserRepository, FakeUsers()),
        cast(GeminiClient, FakeGemini()),
        NOW,
    )

    assert result.corridors_scanned == 6
    assert result.alerts_created == 1  # AU-IN's surge still went through
