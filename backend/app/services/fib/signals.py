"""Coach and scam-check signals for the Financial Identity profile (NF-HR-001).

`users/{uid}.signal_sharing` is the worker's opt-in, off when absent. At the weekly recompute
each shared signal becomes a block of numbers and dates on `financial_profile/current`
(`coach_signal`, `scam_signal`); a block the worker has not opted into is never written, and one
written earlier is gone because the recompute replaces the document. Nothing here carries what a
worker typed or a message said: only counts, fixed answer choices and dates.

Each signal also needs its module on for the worker (the `coach` and `scam` flags), so with a
flag off the signal is inert, as the design requires of every cross-feature row.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.scam_check_repo import ScamCheckRepository
from app.schemas.coach_plan import CoachPlan
from app.services.coach.plan_goals import goals_for
from app.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)

SCAM_WINDOW_DAYS = 90
# A worker cannot check more than 20 messages an hour (NF-SA-012), so this is far above any real
# 90 days; it only keeps one run's reads bounded.
SCAM_READ_LIMIT = 1000
MILESTONES = ("d30", "d60", "d90")

Signals = dict[str, dict[str, Any]]


class Sharing(NamedTuple):
    coach: bool
    scam: bool


NOT_SHARED = Sharing(coach=False, scam=False)


def sharing_of(user: dict[str, Any]) -> Sharing:
    """The worker's choice. Anything but a boolean `true` is "not shared"."""
    choice = user.get("signal_sharing")
    if not isinstance(choice, dict):
        return NOT_SHARED
    return Sharing(choice.get("coach") is True, choice.get("scam") is True)


def coach_signal(
    plan_id: str,
    plan_document: dict[str, Any],
    savings_rate_recorded_pct: float | None,
) -> dict[str, Any] | None:
    """What the worker's check-in answers say, or None before they answered any.

    `answers` hold fixed choices (`on_track`, `behind`, `not_yet`; `full_on_time`, ...), so this
    counts choices. The plan's savings-rate target is set beside the rate recorded over the
    profile's period, both as numbers, with no verdict between them.
    """
    checkins = plan_document.get("checkins")
    if not isinstance(checkins, dict):
        return None
    answered = [
        entry
        for milestone in MILESTONES
        if isinstance(entry := checkins.get(milestone), dict)
        and isinstance(entry.get("answers"), dict)
        and entry.get("answered_at") is not None
    ]
    if not answered:
        return None

    def count(key: str, value: str) -> int:
        return sum(1 for entry in answered if entry["answers"].get(key) == value)

    signal: dict[str, Any] = {
        "plan_id": plan_id,
        "checkins_answered": len(answered),
        "remittance_on_track": count("remittance", "on_track"),
        "savings_on_track": count("savings", "on_track"),
        "pay_on_time": count("pay", "full_on_time"),
        "last_checkin_at": max(entry["answered_at"] for entry in answered),
    }
    target = _savings_target_pct(plan_id, plan_document)
    if target is not None and savings_rate_recorded_pct is not None:
        signal["savings_rate_target_pct"] = target
        signal["savings_rate_recorded_pct"] = savings_rate_recorded_pct
    return signal


def _savings_target_pct(plan_id: str, plan_document: dict[str, Any]) -> float | None:
    try:
        plan = CoachPlan.model_validate(plan_document["plan"])
        created = plan_document["created_at"]
        target = goals_for(plan_id, plan, created)["savings_rate_target_pct"]
    except (KeyError, ValueError, TypeError):
        return None
    return float(target)


def scam_signal(checks: list[tuple[str, dict[str, Any]]], now: datetime) -> dict[str, Any] | None:
    """Counts of the messages checked in the window and how many were flagged, or None."""
    since = now - timedelta(days=SCAM_WINDOW_DAYS)
    seen = [
        data
        for _, data in checks
        if isinstance(data.get("last_checked_at"), datetime) and data["last_checked_at"] >= since
    ]
    if not seen:
        return None
    return {
        "window_days": SCAM_WINDOW_DAYS,
        "checks": len(seen),
        "scams_found": sum(1 for d in seen if (d.get("verdict") or {}).get("is_scam") is True),
        "last_check_at": max(d["last_checked_at"] for d in seen),
    }


def recorded_savings_rate_pct(metrics: dict[str, Any]) -> float | None:
    """The savings metric's own rate (net savings over income), as a percentage, when it has one."""
    metric = metrics.get("savings_rate") or {}
    rate = (metric.get("detail") or {}).get("savings_rate")
    if metric.get("score") is None or not isinstance(rate, int | float):
        return None
    return round(float(rate) * 100, 1)


def shared_now(profile: dict[str, Any], sharing: Sharing) -> dict[str, Any]:
    """The profile as it may be shown now: signals the worker still shares, and nothing else.

    The stored profile is rewritten only by the weekly recompute, so a worker who turns sharing
    off is protected here, in every export, from the moment they do. The activity paragraph
    names both signals, so it goes as soon as either is no longer shared.
    """
    kept = {
        key: value
        for key, value in profile.items()
        if key not in ("coach_signal", "scam_signal")
        or (key == "coach_signal" and sharing.coach)
        or (key == "scam_signal" and sharing.scam)
    }
    complete = all(key in kept for key in ("coach_signal", "scam_signal") if key in profile)
    narrative = kept.get("narrative")
    if isinstance(narrative, dict) and "activity_text" in narrative and not complete:
        kept["narrative"] = {k: v for k, v in narrative.items() if k != "activity_text"}
    return kept


def signals_shown(profile: dict[str, Any]) -> list[str]:
    """Which signals a profile carries, as `coach` and `scam`: recorded on an export so that a
    PDF made while sharing was on is not handed out again after it is turned off."""
    return [
        name for name, key in (("coach", "coach_signal"), ("scam", "scam_signal")) if key in profile
    ]


class SignalReader:
    """Reads what the worker has shared. One instance serves a whole recompute run."""

    def __init__(
        self,
        plans: CoachPlanRepository,
        scam_checks: ScamCheckRepository,
        flags: FeatureFlagService,
    ) -> None:
        self._plans = plans
        self._scam_checks = scam_checks
        self._flags = flags

    async def read(
        self, uid: str, sharing: Sharing, metrics: dict[str, Any], now: datetime
    ) -> Signals:
        """The signals to write: only those shared, with their module on, and with data.

        A read that fails costs the profile that signal and nothing else.
        """
        signals: Signals = {}
        if sharing.coach and await self._flags.is_enabled("coach", uid):
            try:
                newest = await run_in_threadpool(self._plans.newest, uid)
            except GoogleAPICallError:
                logger.warning("fib_coach_signal_read_failed", exc_info=True)
                newest = None
            if newest is not None:
                block = coach_signal(newest[0], newest[1], recorded_savings_rate_pct(metrics))
                if block is not None:
                    signals["coach_signal"] = block
        if sharing.scam and await self._flags.is_enabled("scam", uid):
            try:
                checks = await run_in_threadpool(
                    self._scam_checks.activity_since,
                    uid,
                    now - timedelta(days=SCAM_WINDOW_DAYS),
                    SCAM_READ_LIMIT,
                )
            except GoogleAPICallError:
                logger.warning("fib_scam_signal_read_failed", exc_info=True)
                checks = []
            block = scam_signal(checks, now)
            if block is not None:
                signals["scam_signal"] = block
        return signals
