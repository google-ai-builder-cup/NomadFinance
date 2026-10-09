"""Day 30, 60 and 90 check-in reminders (NF-FC-016): the daily job of
docs/mermaid/financial-coach-pipeline.mmd.

Runs once a day (infra/cloud-scheduler/coach-checkins.yaml). A plan is due when its departure
date plus 30, 60 or 90 days is today, or was in the last CATCH_UP_DAYS days, so one skipped run
delays a reminder instead of losing it. Each reminder is a `coach_checkin` notification and a
push, written once per plan and milestone however often the job runs (see `_remind`).
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from firebase_admin.exceptions import FirebaseError  # type: ignore[import-untyped]
from google.api_core.exceptions import GoogleAPICallError

from app.integrations.firebase_messaging import send_push, usable_tokens
from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.user_repo import UserRepository
from app.schemas.coach_checkin import SendCheckinsResponse
from app.services.coach.checkin_texts import checkin_text, reminder_language
from app.services.feature_flag_service import FeatureFlagService
from app.utils.hashing import hash_user_id

logger = logging.getLogger(__name__)

# Keys of `coach_plans.checkins` (coach.md), and how many days after departure each is due.
MILESTONES: dict[str, int] = {"d30": 30, "d60": 60, "d90": 90}
# Windows of 4 departure days never overlap between milestones (30 days apart), so a plan is
# found for one milestone at a time.
CATCH_UP_DAYS = 3

Outcome = Literal["notified", "already_sent", "flag_off", "reminders_off", "superseded", "bad_date"]
_SKIPPED: tuple[Outcome, ...] = ("flag_off", "reminders_off", "superseded", "bad_date")


def window_for(today: date, days: int) -> tuple[str, str]:
    """The departure dates (first, last) whose day `days` is today or in the catch-up window."""
    last = today - timedelta(days=days)
    return (last - timedelta(days=CATCH_UP_DAYS)).isoformat(), last.isoformat()


def _already_sent(plan: dict[str, Any], milestone: str) -> bool:
    checkins = plan.get("checkins")
    entry = checkins.get(milestone) if isinstance(checkins, dict) else None
    return isinstance(entry, dict) and entry.get("notified_at") is not None


def _reminders_on(profile: dict[str, Any]) -> bool:
    prefs = profile.get("notification_prefs")
    return not (isinstance(prefs, dict) and prefs.get("reminders") is False)


async def _push(
    uid: str, profile: dict[str, Any], title: str, body: str, deep_link: str, users: UserRepository
) -> None:
    """Best effort: the notification is already stored, the push is the extra."""
    tokens = usable_tokens(profile)
    if not tokens:
        return
    try:
        invalid = await run_in_threadpool(send_push, tokens, title, body, deep_link)
    except (ValueError, FirebaseError) as exc:
        # Only the type: a message could echo the token.
        logger.warning("coach_checkin_push_failed error=%s", type(exc).__name__)
        return
    for token in invalid:
        try:
            await run_in_threadpool(users.remove_fcm_token, uid, token)
        except GoogleAPICallError:
            logger.warning("coach_checkin_token_cleanup_failed user=%s", hash_user_id(uid))


async def _remind(
    uid: str,
    plan_id: str,
    plan: dict[str, Any],
    milestone: str,
    plans: CoachPlanRepository,
    users: UserRepository,
    flags: FeatureFlagService,
    now: datetime,
) -> Outcome:
    """Remind one worker about one milestone of one plan, at most once.

    The notification is created under an id made from the plan and the milestone, and `create`
    fails if it exists: of two runs that overlap, or a run that died before it marked the plan,
    only the first sends the push. The marker on the plan is written last, so a failure before it
    is retried safely and a push is never repeated. The cost is that a run that dies between the
    notification and the push leaves the notification without a push.
    """
    if _already_sent(plan, milestone):
        return "already_sent"
    days = MILESTONES[milestone]
    try:
        due_on = date.fromisoformat(str(plan.get("departure_date"))) + timedelta(days=days)
    except ValueError:
        return "bad_date"
    if not await flags.is_enabled("coach", uid):
        return "flag_off"
    profile = await run_in_threadpool(users.get_profile, uid)
    if not _reminders_on(profile):
        return "reminders_off"
    # A changed answer makes a new plan and the old one stays: only the newest is the worker's.
    newest = await run_in_threadpool(plans.newest, uid)
    if newest is None or newest[0] != plan_id:
        return "superseded"

    language = reminder_language(profile.get("preferred_language"))
    title, body = checkin_text(language, days)
    deep_link = f"/coach/checkin/{plan_id}?m={days}"
    notification = {
        "type": "coach_checkin",
        "title": title,
        "body": body,
        "language": language,
        "deep_link": deep_link,
        "source": {
            "kind": "coach_checkin",
            "path": f"users/{uid}/coach_plans/{plan_id}",
            "milestone": milestone,
        },
        "read": False,
        "created_at": now,
        "schema_version": 1,
    }
    created = await run_in_threadpool(
        users.create_notification_once, uid, f"coach_checkin_{plan_id}_{milestone}", notification
    )
    if created:
        await _push(uid, profile, title, body, deep_link, users)
    await run_in_threadpool(plans.mark_checkin, uid, plan_id, milestone, due_on.isoformat(), now)
    return "notified" if created else "already_sent"


async def send_checkins(
    plans: CoachPlanRepository, users: UserRepository, flags: FeatureFlagService, now: datetime
) -> tuple[SendCheckinsResponse, bool]:
    """Send every reminder that is due on `now`'s day (UTC).

    Returns:
        The counts, and whether everything that was due was read and handled. A False answer
        is for Cloud Scheduler to retry: repeating a run is safe.
    """
    today = now.astimezone(UTC).date()
    outcomes: Counter[str] = Counter()
    found = failed = 0
    for milestone, days in MILESTONES.items():
        first, last = window_for(today, days)
        try:
            candidates = await run_in_threadpool(plans.departing_between, first, last)
        except GoogleAPICallError:
            # Most likely the group-scope index on departure_date is missing (D-114).
            logger.exception("coach_checkin_query_failed milestone=%s", milestone)
            failed += 1
            continue
        found += len(candidates)
        for uid, plan_id, plan in candidates:
            try:
                outcomes[
                    await _remind(uid, plan_id, plan, milestone, plans, users, flags, now)
                ] += 1
            except GoogleAPICallError:
                logger.exception(
                    "coach_checkin_failed milestone=%s user=%s", milestone, hash_user_id(uid)
                )
                failed += 1

    logger.info(
        "coach_checkins day=%s found=%d notified=%d already_sent=%d skipped=%s failed=%d",
        today,
        found,
        outcomes["notified"],
        outcomes["already_sent"],
        {reason: outcomes[reason] for reason in _SKIPPED if outcomes[reason]},
        failed,
    )
    response = SendCheckinsResponse(
        day=today,
        plans_found=found,
        notified=outcomes["notified"],
        already_sent=outcomes["already_sent"],
        skipped=sum(outcomes[reason] for reason in _SKIPPED),
        failed=failed,
        completed_at=now,
    )
    return response, failed == 0
