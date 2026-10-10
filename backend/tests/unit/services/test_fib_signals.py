"""Coach and scam signals of the Financial Identity profile (NF-HR-001)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.scam_check_repo import ScamCheckRepository
from app.services.feature_flag_service import FeatureFlagService
from app.services.fib.signals import (
    NOT_SHARED,
    Sharing,
    SignalReader,
    coach_signal,
    recorded_savings_rate_pct,
    scam_signal,
    shared_now,
    sharing_of,
    signals_shown,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 15, 2, 0, tzinfo=UTC)


def _answered(day: int, remittance: str, savings: str, pay: str) -> dict[str, Any]:
    return {
        "due_on": "2026-09-01",
        "notified_at": NOW,
        "answered_at": datetime(2026, 10, day, 9, tzinfo=UTC),
        "answers": {"remittance": remittance, "savings": savings, "pay": pay},
    }


def _recorded_plan() -> dict[str, Any]:
    """The plan of docs/mocks/coach/plan-get-01-english.json, as a stored document holds it."""
    path = Path(__file__).resolve().parents[4] / "docs/mocks/coach/plan-get-01-english.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8"))["body"]["plan"])


def _plan(checkins: dict[str, Any] | None, **fields: Any) -> dict[str, Any]:
    document: dict[str, Any] = {"created_at": datetime(2026, 8, 1, tzinfo=UTC)}
    if checkins is not None:
        document["checkins"] = checkins
    return document | fields


class TestSharing:
    @pytest.mark.parametrize(
        ("user", "expected"),
        [
            ({}, NOT_SHARED),
            ({"signal_sharing": None}, NOT_SHARED),
            ({"signal_sharing": {}}, NOT_SHARED),
            ({"signal_sharing": {"coach": True}}, Sharing(True, False)),
            ({"signal_sharing": {"scam": True}}, Sharing(False, True)),
            ({"signal_sharing": {"coach": True, "scam": True}}, Sharing(True, True)),
            ({"signal_sharing": {"coach": False, "scam": False}}, NOT_SHARED),
            # Only a real `true` counts: a string or a number is not consent.
            ({"signal_sharing": {"coach": "true", "scam": 1}}, NOT_SHARED),
            ({"signal_sharing": "yes"}, NOT_SHARED),
        ],
    )
    def test_only_a_boolean_true_is_consent(self, user: dict[str, Any], expected: Sharing) -> None:
        assert sharing_of(user) == expected


class TestCoachSignal:
    def test_counts_the_answers_to_the_check_ins(self) -> None:
        document = _plan(
            {
                "d30": _answered(3, "on_track", "behind", "full_on_time"),
                "d60": _answered(9, "on_track", "on_track", "late_or_less"),
                "d90": {"due_on": "2026-11-30", "notified_at": NOW},
            }
        )

        signal = coach_signal("p1", document, None)

        assert signal == {
            "plan_id": "p1",
            "checkins_answered": 2,
            "remittance_on_track": 2,
            "savings_on_track": 1,
            "pay_on_time": 1,
            "last_checkin_at": datetime(2026, 10, 9, 9, tzinfo=UTC),
        }

    @pytest.mark.parametrize(
        "checkins",
        [
            None,
            {},
            {"d30": {"due_on": "2026-09-01", "notified_at": NOW}},
            {"d30": "not a map", "d60": 4},
            {"d30": {"answers": "oops", "answered_at": NOW}},
            {"d30": {"answers": {"remittance": "on_track"}}},
        ],
    )
    def test_is_none_until_one_check_in_is_answered(self, checkins: Any) -> None:
        assert coach_signal("p1", _plan(checkins), 10.0) is None

    def test_a_milestone_that_is_not_one_of_the_three_is_ignored(self) -> None:
        document = _plan({"d15": _answered(3, "on_track", "on_track", "full_on_time")})

        assert coach_signal("p1", document, None) is None

    def test_puts_the_planned_savings_rate_beside_the_recorded_one(self) -> None:
        # The recorded plan saves 400 AUD a month from 4,200 AUD: 9.5%.
        document = _plan(
            {"d30": _answered(3, "on_track", "on_track", "full_on_time")}, plan=_recorded_plan()
        )

        signal = coach_signal("p1", document, 7.2)

        assert signal is not None
        assert signal["savings_rate_target_pct"] == 9.5
        assert signal["savings_rate_recorded_pct"] == 7.2

    def test_leaves_the_comparison_out_when_the_plan_or_the_rate_is_missing(self) -> None:
        document = _plan({"d30": _answered(3, "on_track", "on_track", "full_on_time")})

        without_plan = coach_signal("p1", document, 7.2)
        without_rate = coach_signal("p1", document | {"plan": {"x": 1}}, None)

        assert without_plan is not None and "savings_rate_target_pct" not in without_plan
        assert without_rate is not None and "savings_rate_recorded_pct" not in without_rate

    def test_carries_no_text_a_worker_could_have_written(self) -> None:
        document = _plan({"d30": _answered(3, "on_track", "behind", "not_paid")})

        signal = coach_signal("p1", document, None)

        assert signal is not None
        assert all(not isinstance(v, str) or k == "plan_id" for k, v in signal.items())


class TestScamSignal:
    @staticmethod
    def _check(days_ago: float, is_scam: bool) -> tuple[str, dict[str, Any]]:
        return (
            f"c{days_ago}",
            {
                "last_checked_at": NOW - timedelta(days=days_ago),
                "verdict": {"is_scam": is_scam, "risk_level": "high", "scam_type": "x"},
            },
        )

    def test_counts_the_checks_of_the_window_and_the_flagged_ones(self) -> None:
        signal = scam_signal(
            [self._check(1, True), self._check(10, False), self._check(40, True)], NOW
        )

        assert signal == {
            "window_days": 90,
            "checks": 3,
            "scams_found": 2,
            "last_check_at": NOW - timedelta(days=1),
        }

    def test_leaves_out_a_check_older_than_90_days(self) -> None:
        signal = scam_signal([self._check(89.9, True), self._check(91, True)], NOW)

        assert signal is not None and signal["checks"] == 1

    @pytest.mark.parametrize("checks", [[], [("c", {})], [("c", {"last_checked_at": "x"})]])
    def test_is_none_without_a_usable_check(self, checks: list[tuple[str, dict[str, Any]]]) -> None:
        assert scam_signal(checks, NOW) is None

    def test_carries_neither_the_type_nor_the_text(self) -> None:
        signal = scam_signal([self._check(1, True)], NOW)

        assert signal is not None
        assert set(signal) == {"window_days", "checks", "scams_found", "last_check_at"}


class TestSavingsRate:
    def test_is_the_metrics_own_rate_as_a_percentage(self) -> None:
        metrics = {"savings_rate": {"score": 50, "detail": {"savings_rate": 0.1034}}}

        assert recorded_savings_rate_pct(metrics) == 10.3

    @pytest.mark.parametrize(
        "metrics",
        [
            {},
            {"savings_rate": {"score": None, "detail": {"reason": "no_savings_entries"}}},
            {"savings_rate": {"score": 0, "detail": {}}},
        ],
    )
    def test_is_none_when_the_metric_has_no_rate(self, metrics: dict[str, Any]) -> None:
        assert recorded_savings_rate_pct(metrics) is None


class TestWhatMayBeShownNow:
    @staticmethod
    def _profile() -> dict[str, Any]:
        return {
            "metrics": {},
            "coach_signal": {"checkins_answered": 1},
            "scam_signal": {"checks": 4},
            "narrative": {"language": "en", "text": "Report.", "activity_text": "Both."},
        }

    def test_keeps_what_is_still_shared(self) -> None:
        shown = shared_now(self._profile(), Sharing(True, True))

        assert shown == self._profile()

    def test_drops_the_signal_and_the_paragraph_when_one_is_turned_off(self) -> None:
        shown = shared_now(self._profile(), Sharing(coach=True, scam=False))

        assert "scam_signal" not in shown
        assert shown["coach_signal"] == {"checkins_answered": 1}
        assert shown["narrative"] == {"language": "en", "text": "Report."}

    def test_drops_everything_when_nothing_is_shared(self) -> None:
        shown = shared_now(self._profile(), NOT_SHARED)

        assert "coach_signal" not in shown and "scam_signal" not in shown
        assert shown["narrative"] == {"language": "en", "text": "Report."}
        assert shown["metrics"] == {}

    def test_does_not_change_the_stored_profile(self) -> None:
        profile = self._profile()

        shared_now(profile, NOT_SHARED)

        assert profile == self._profile()

    def test_a_profile_with_a_single_signal_keeps_its_paragraph_while_it_is_shared(self) -> None:
        profile = self._profile()
        del profile["scam_signal"]

        assert shared_now(profile, Sharing(True, False))["narrative"]["activity_text"] == "Both."
        assert "activity_text" not in shared_now(profile, NOT_SHARED)["narrative"]

    def test_names_the_signals_a_profile_carries(self) -> None:
        assert signals_shown(self._profile()) == ["coach", "scam"]
        assert signals_shown({"metrics": {}}) == []


class FakePlans:
    def __init__(self, newest: tuple[str, dict[str, Any]] | None, fail: bool = False) -> None:
        self._newest = newest
        self._fail = fail
        self.reads = 0

    def newest(self, uid: str) -> tuple[str, dict[str, Any]] | None:
        self.reads += 1
        if self._fail:
            raise ServiceUnavailable("down")
        return self._newest


class FakeChecks:
    def __init__(self, checks: list[tuple[str, dict[str, Any]]], fail: bool = False) -> None:
        self._checks = checks
        self._fail = fail
        self.asked: list[tuple[datetime, int]] = []

    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        self.asked.append((since, limit))
        if self._fail:
            raise ServiceUnavailable("down")
        return self._checks


class FakeFlags:
    def __init__(self, on: set[str]) -> None:
        self.on = on

    async def is_enabled(self, flag: str, uid: str) -> bool:
        return flag in self.on


def _reader(plans: FakePlans, checks: FakeChecks, flags: FakeFlags) -> SignalReader:
    return SignalReader(
        cast(CoachPlanRepository, plans),
        cast(ScamCheckRepository, checks),
        cast(FeatureFlagService, flags),
    )


_PLAN = ("p1", _plan({"d30": _answered(3, "on_track", "on_track", "full_on_time")}))
_CHECKS = [("c1", {"last_checked_at": NOW - timedelta(days=2), "verdict": {"is_scam": True}})]


class TestReader:
    async def test_reads_nothing_the_worker_has_not_opted_into(self) -> None:
        plans, checks = FakePlans(_PLAN), FakeChecks(_CHECKS)
        reader = _reader(plans, checks, FakeFlags({"coach", "scam"}))

        signals = await reader.read("u1", NOT_SHARED, {}, NOW)

        assert signals == {}
        assert plans.reads == 0 and checks.asked == []

    async def test_reads_only_the_signal_that_is_shared(self) -> None:
        plans, checks = FakePlans(_PLAN), FakeChecks(_CHECKS)
        reader = _reader(plans, checks, FakeFlags({"coach", "scam"}))

        signals = await reader.read("u1", Sharing(coach=False, scam=True), {}, NOW)

        assert set(signals) == {"scam_signal"}
        assert plans.reads == 0

    async def test_gives_both_when_both_are_shared_and_on(self) -> None:
        reader = _reader(FakePlans(_PLAN), FakeChecks(_CHECKS), FakeFlags({"coach", "scam"}))

        signals = await reader.read("u1", Sharing(True, True), {}, NOW)

        assert set(signals) == {"coach_signal", "scam_signal"}
        assert signals["scam_signal"]["scams_found"] == 1

    async def test_a_module_that_is_off_for_the_worker_is_inert(self) -> None:
        plans, checks = FakePlans(_PLAN), FakeChecks(_CHECKS)
        reader = _reader(plans, checks, FakeFlags(set()))

        signals = await reader.read("u1", Sharing(True, True), {}, NOW)

        assert signals == {}
        assert plans.reads == 0 and checks.asked == []

    async def test_asks_for_the_checks_of_the_window_with_a_cap(self) -> None:
        checks = FakeChecks(_CHECKS)
        reader = _reader(FakePlans(None), checks, FakeFlags({"scam"}))

        await reader.read("u1", Sharing(False, True), {}, NOW)

        assert checks.asked == [(NOW - timedelta(days=90), 1000)]

    async def test_a_failed_read_loses_that_signal_only(self) -> None:
        reader = _reader(
            FakePlans(_PLAN, fail=True), FakeChecks(_CHECKS), FakeFlags({"coach", "scam"})
        )

        signals = await reader.read("u1", Sharing(True, True), {}, NOW)

        assert set(signals) == {"scam_signal"}

    async def test_a_worker_with_no_plan_or_no_checks_has_no_signal(self) -> None:
        reader = _reader(FakePlans(None), FakeChecks([]), FakeFlags({"coach", "scam"}))

        assert await reader.read("u1", Sharing(True, True), {}, NOW) == {}
