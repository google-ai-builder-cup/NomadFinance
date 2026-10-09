"""In-memory stand-ins for the Coach session storage, and an app wired to them (NF-FC-008 tests).

`FakeSessionRepo` keeps the contract of `CoachSessionRepository`: one active session per
worker (checked and created in one step), writes that must name the revision they read, and
copies on the way in and out so a test never changes a stored document by accident.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI

from app.dependencies import get_coach_sessions, get_current_user, get_feature_flag_service
from app.main import create_app
from app.repositories.coach_session_repo import (
    CoachPlanRepository,
    CoachSessionRepository,
    RevisionConflictError,
    SessionContentionError,
    SessionMissingError,
)
from app.schemas.user import AuthenticatedUser
from app.services.coach.session_service import CoachSessions
from app.services.feature_flag_service import FeatureFlagService

NOW = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)


class FakeSessionRepo:
    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}
        self._next = 0
        self.stale_next_write = False  # the next update finds a newer revision, as in a race
        self.contended = False  # the next start gives up under a burst of requests

    def new_id(self, uid: str) -> str:
        self._next += 1
        return f"s_{self._next:02d}"

    def get(self, uid: str, session_id: str) -> dict[str, Any] | None:
        stored = self.docs.get((uid, session_id))
        return copy.deepcopy(stored) if stored is not None else None

    def active(self, uid: str) -> list[tuple[str, dict[str, Any]]]:
        return [
            (sid, copy.deepcopy(doc))
            for (owner, sid), doc in self.docs.items()
            if owner == uid and doc["status"] == "active"
        ]

    def create_or_resume(
        self,
        uid: str,
        session_id: str,
        document: dict[str, Any],
        *,
        restart: bool,
        idle_before: datetime,
    ) -> tuple[str, dict[str, Any], bool]:
        if self.contended:
            raise SessionContentionError(uid)
        for sid, doc in self.active(uid):
            if restart or doc["last_active"] <= idle_before:
                self.docs[(uid, sid)]["status"] = "abandoned"
                continue
            return sid, doc, True
        self.docs[(uid, session_id)] = copy.deepcopy(document)
        return session_id, copy.deepcopy(document), False

    def update(
        self, uid: str, session_id: str, *, expected_revision: int, changes: dict[str, Any]
    ) -> dict[str, Any]:
        stored = self.docs.get((uid, session_id))
        if stored is None:
            raise SessionMissingError(session_id)
        if self.stale_next_write or stored["revision"] != expected_revision:
            self.stale_next_write = False
            raise RevisionConflictError(session_id)
        stored.update(copy.deepcopy(changes))
        stored["revision"] = expected_revision + 1
        return copy.deepcopy(stored)

    def plant(self, uid: str, session_id: str, document: dict[str, Any]) -> None:
        """Put a stored session in place, as a test's starting point."""
        self.docs[(uid, session_id)] = copy.deepcopy(document)


class FakePlanRepo:
    def __init__(self) -> None:
        self.plans: dict[str, list[tuple[str, dict[str, Any]]]] = {}

    def add(self, uid: str, plan_id: str, plan: dict[str, Any]) -> None:
        self.plans.setdefault(uid, []).append((plan_id, plan))

    def get(self, uid: str, plan_id: str) -> dict[str, Any] | None:
        found = [plan for pid, plan in self.plans.get(uid, []) if pid == plan_id]
        return copy.deepcopy(found[0]) if found else None

    def create(self, uid: str, plan_id: str, document: dict[str, Any]) -> bool:
        if self.get(uid, plan_id) is not None:
            return False
        self.add(uid, plan_id, copy.deepcopy(document))
        return True

    def newest(self, uid: str) -> tuple[str, dict[str, Any]] | None:
        mine = sorted(self.plans.get(uid, []), key=lambda p: p[1]["created_at"])
        return mine[-1] if mine else None


def make_sessions(
    repo: FakeSessionRepo | None = None, plans: FakePlanRepo | None = None
) -> tuple[CoachSessions, FakeSessionRepo, FakePlanRepo]:
    repo = repo or FakeSessionRepo()
    plans = plans or FakePlanRepo()
    service = CoachSessions(
        repo,  # type: ignore[arg-type]
        plans,  # type: ignore[arg-type]
    )
    return service, repo, plans


class _FakeFlags:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def get_feature_flags(self) -> dict[str, Any]:
        return {"flags": {"coach": {"enabled": self._enabled, "allow_uids": []}}}


def make_coach_app(
    service: CoachSessions, *, flag_on: bool = True, signed_in: bool = True, uid: str = "test-user"
) -> FastAPI:
    """The real app, with sign-in, the `coach` flag and storage replaced."""
    app = create_app()
    flags = FeatureFlagService(_FakeFlags(flag_on))  # type: ignore[arg-type]
    app.dependency_overrides[get_feature_flag_service] = lambda: flags
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)
    app.dependency_overrides[get_coach_sessions] = lambda: service
    return app


__all__ = [
    "CoachPlanRepository",
    "CoachSessionRepository",
    "FakePlanRepo",
    "FakeSessionRepo",
    "NOW",
    "make_coach_app",
    "make_sessions",
]
