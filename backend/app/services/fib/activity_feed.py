"""The worker's unified activity feed (NF-HR-001): money log, Coach and Scam Analyzer in one list.

The feed is the worker's own view of their own activity, so it is not behind the report's
opt-in (`signal_sharing` is about what goes into a report others read). The Coach and scam events
need their module on for the worker, like every cross-feature row. A read that fails drops its
events and nothing else.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.fib_repo import EntryKind, FibRepository
from app.repositories.scam_check_repo import ScamCheckRepository
from app.schemas.fib_activity import (
    ActivityFeedResponse,
    ActivityItem,
    BillItem,
    CoachCheckinItem,
    CoachPlanItem,
    IncomeItem,
    SavingsItem,
    ScamCheckItem,
    TransferItem,
)
from app.services.feature_flag_service import FeatureFlagService
from app.services.fib.signals import MILESTONES, SCAM_READ_LIMIT

logger = logging.getLogger(__name__)

PLAN_READ_LIMIT = 20


def _day(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _entry_items(
    kind: EntryKind, entries: list[tuple[str, dict[str, Any]]], since: date
) -> list[Any]:
    items: list[Any] = []
    for entry_id, data in entries:
        on = _day(data.get("entry_date"))
        if on is None or on < since:
            continue
        try:
            if kind == "income":
                items.append(
                    IncomeItem(
                        id=entry_id,
                        on=on,
                        amount=data["amount"],
                        currency=data["currency"],
                        category=data.get("category"),
                        verified=data.get("verified") is True,
                    )
                )
            elif kind == "transfers":
                items.append(
                    TransferItem(
                        id=entry_id,
                        on=on,
                        amount=data["send_amount"],
                        currency=data["send_currency"],
                        corridor_id=data.get("corridor_id"),
                    )
                )
            elif kind == "bills":
                items.append(
                    BillItem(
                        id=entry_id,
                        on=on,
                        amount=data["amount"],
                        currency=data["currency"],
                        category=data.get("category"),
                        paid=data.get("paid") is True,
                    )
                )
            else:
                items.append(
                    SavingsItem(
                        id=entry_id,
                        on=on,
                        amount=data["amount"],
                        currency=data["currency"],
                        direction=data["direction"],
                    )
                )
        except (KeyError, ValueError, TypeError):
            # One entry that does not match its shape is left out, not the whole feed.
            logger.warning("fib_activity_entry_skipped kind=%s", kind)
    return items


def _coach_items(plans: list[tuple[str, dict[str, Any]]], since: date) -> list[Any]:
    items: list[Any] = []
    for plan_id, data in plans:
        made = _day(data.get("created_at"))
        if made is not None and made >= since:
            items.append(
                CoachPlanItem(
                    id=plan_id,
                    on=made,
                    corridor_id=data.get("corridor_id"),
                    departure_date=_day(data.get("departure_date")),
                )
            )
        checkins = data.get("checkins")
        if not isinstance(checkins, dict):
            continue
        for milestone in MILESTONES:
            entry = checkins.get(milestone)
            if not isinstance(entry, dict):
                continue
            answered = _day(entry.get("answered_at"))
            answers = entry.get("answers")
            if answered is None or answered < since or not isinstance(answers, dict):
                continue
            try:
                items.append(
                    CoachCheckinItem(
                        id=plan_id,
                        on=answered,
                        milestone=milestone,
                        remittance=answers["remittance"],
                        savings=answers["savings"],
                        pay=answers["pay"],
                    )
                )
            except (KeyError, ValueError):
                logger.warning("fib_activity_checkin_skipped")
    return items


def _scam_items(checks: list[tuple[str, dict[str, Any]]], since: date) -> list[Any]:
    items: list[Any] = []
    for check_id, data in checks:
        on = _day(data.get("last_checked_at"))
        verdict = data.get("verdict")
        if on is None or on < since or not isinstance(verdict, dict):
            continue
        try:
            items.append(
                ScamCheckItem(
                    id=check_id,
                    on=on,
                    is_scam=verdict.get("is_scam") is True,
                    risk_level=verdict.get("risk_level"),
                    scam_type=verdict.get("scam_type"),
                )
            )
        except ValueError:
            logger.warning("fib_activity_scam_check_skipped")
    return items


async def build_feed(
    uid: str,
    *,
    days: int,
    limit: int,
    now: datetime,
    fib: FibRepository,
    plans: CoachPlanRepository,
    scam_checks: ScamCheckRepository,
    flags: FeatureFlagService,
) -> ActivityFeedResponse:
    """Everything the worker did in the last `days` days, newest first, at most `limit` items."""
    since = (now - timedelta(days=days)).date()
    found: list[Any] = []
    kinds: tuple[EntryKind, ...] = ("income", "transfers", "bills", "savings")
    for kind in kinds:
        entries = await run_in_threadpool(fib.list_entries, uid, kind)
        found += _entry_items(kind, entries, since)

    if await flags.is_enabled("coach", uid):
        try:
            recent = await run_in_threadpool(plans.activity, uid, PLAN_READ_LIMIT)
            found += _coach_items(recent, since)
        except GoogleAPICallError:
            logger.warning("fib_activity_coach_read_failed", exc_info=True)
    if await flags.is_enabled("scam", uid):
        try:
            checks = await run_in_threadpool(
                scam_checks.activity_since,
                uid,
                datetime.combine(since, datetime.min.time(), tzinfo=now.tzinfo),
                SCAM_READ_LIMIT,
            )
            found += _scam_items(checks, since)
        except GoogleAPICallError:
            logger.warning("fib_activity_scam_read_failed", exc_info=True)

    found.sort(key=lambda item: (item.on, item.kind, item.id), reverse=True)
    items: list[ActivityItem] = found[:limit]
    return ActivityFeedResponse(items=items, days=days, truncated=len(found) > limit)
