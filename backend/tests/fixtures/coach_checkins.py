"""In-memory stand-ins for the check-in job's stores (NF-FC-016).

They behave like the Firestore-backed ones where the job depends on it: a range query returns only
plans that have the field, `create_notification_once` is atomic, and a marker is written by field
path so what sits beside it survives.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, cast

from google.api_core.exceptions import ServiceUnavailable

from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.user_repo import UserRepository
from app.services.feature_flag_service import FeatureFlagService

DEPARTURE = "2026-12-01"
# The day 30, 60 and 90 after DEPARTURE, as the data model's example shows them.
DUE = {"d30": "2026-12-31", "d60": "2027-01-30", "d90": "2027-03-01"}
PLAN_ID = "9f3a1c5e7b2d4a60c8e1"
NEWER_PLAN_ID = "1a2b3c4d5e6f70819a0b"


def at(day: str, hour: int = 2) -> datetime:
    """`day` (YYYY-MM-DD) at `hour` o'clock UTC: when the daily job runs."""
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=UTC)


def profile(**over: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "host_country": "AU",
        "home_country": "IN",
        "preferred_language": "hi",
        "notification_prefs": None,
        "fcm_tokens": ["token-1"],
    }
    return values | over


class FakePlans:
    """`users/{uid}/coach_plans`: (uid, plan id) to the stored document."""

    def __init__(self) -> None:
        self.plans: dict[tuple[str, str], dict[str, Any]] = {}
        self.fail_query_for: set[str] = set()
        self.fail_mark = False

    def add(
        self,
        uid: str = "u1",
        plan_id: str = PLAN_ID,
        departure_date: str | None = DEPARTURE,
        created_at: datetime = datetime(2026, 10, 20, tzinfo=UTC),
        **extra: Any,
    ) -> None:
        document: dict[str, Any] = {"created_at": created_at, "plan": {"weeks": []}} | extra
        if departure_date is not None:
            document["departure_date"] = departure_date
        self.plans[(uid, plan_id)] = document

    def departing_between(self, first: str, last: str) -> list[tuple[str, str, dict[str, Any]]]:
        if first in self.fail_query_for:
            raise ServiceUnavailable("index missing")
        return [
            (uid, plan_id, {k: v for k, v in doc.items() if k in ("departure_date", "checkins")})
            for (uid, plan_id), doc in self.plans.items()
            if first <= doc.get("departure_date", "") <= last and "departure_date" in doc
        ]

    def newest(self, uid: str) -> tuple[str, dict[str, Any]] | None:
        mine = [
            (doc["created_at"], plan_id, doc)
            for (u, plan_id), doc in self.plans.items()
            if u == uid
        ]
        if not mine:
            return None
        _, plan_id, doc = max(mine, key=lambda item: item[0])
        return plan_id, doc

    def mark_checkin(
        self, uid: str, plan_id: str, milestone: str, due_on: str, notified_at: datetime
    ) -> None:
        if self.fail_mark:
            raise ServiceUnavailable("write failed")
        entry = self.plans[(uid, plan_id)].setdefault("checkins", {}).setdefault(milestone, {})
        entry.update({"due_on": due_on, "notified_at": notified_at})

    def marker(self, uid: str = "u1", plan_id: str = PLAN_ID) -> dict[str, Any]:
        return cast(dict[str, Any], self.plans[(uid, plan_id)].get("checkins", {}))


class FakeUsers:
    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.notifications: dict[tuple[str, str], dict[str, Any]] = {}
        self.removed_tokens: list[tuple[str, str]] = []
        self.fail_cleanup = False
        self._lock = threading.Lock()

    def get_profile(self, uid: str) -> dict[str, Any]:
        return self.profiles.get(uid, {})

    def create_notification_once(
        self, uid: str, notification_id: str, notification: dict[str, Any]
    ) -> bool:
        with self._lock:
            if (uid, notification_id) in self.notifications:
                return False
            self.notifications[(uid, notification_id)] = notification
            return True

    def remove_fcm_token(self, uid: str, token: str) -> None:
        if self.fail_cleanup:
            raise ServiceUnavailable("write failed")
        self.removed_tokens.append((uid, token))


class FakeFlags:
    def __init__(self, on: set[str] | None = None) -> None:
        self.on = {"u1"} if on is None else on

    async def is_enabled(self, flag: str, uid: str) -> bool:
        return flag == "coach" and uid in self.on


class Pushes:
    """Replaces `send_push`: records every push; `invalid` lists the tokens FCM calls dead."""

    def __init__(self) -> None:
        self.sent: list[tuple[list[str], str, str, str]] = []
        self.invalid: list[str] = []
        self.error: Exception | None = None

    def __call__(self, tokens: list[str], title: str, body: str, deep_link: str) -> list[str]:
        if self.error is not None:
            raise self.error
        self.sent.append((tokens, title, body, deep_link))
        return [t for t in tokens if t in self.invalid]


def as_repos(
    plans: FakePlans, users: FakeUsers, flags: FakeFlags
) -> tuple[CoachPlanRepository, UserRepository, FeatureFlagService]:
    return (
        cast(CoachPlanRepository, plans),
        cast(UserRepository, users),
        cast(FeatureFlagService, flags),
    )
