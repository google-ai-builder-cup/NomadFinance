from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Any

from google.api_core.exceptions import Aborted
from google.cloud.firestore import (
    Client,
    CollectionReference,
    FieldFilter,
    Query,
    Transaction,
    transactional,
)

from app.repositories.base import get_firestore_client

# Requests that start a session at the same moment retry each other's transaction; a few more
# attempts than the default 5 keep a burst of taps from failing a request.
MAX_ATTEMPTS = 15


class SessionMissingError(LookupError):
    """No such session for this worker."""


class SessionContentionError(RuntimeError):
    """Too many requests were changing the session at once; the transaction gave up."""


class RevisionConflictError(RuntimeError):
    """The session changed since it was read (another tab, or a double tap)."""


def _contention(exc: Exception) -> Exception:
    """A lock timeout or exhausted retries is contention; any other ValueError is a bug."""
    if isinstance(exc, Aborted) or str(exc).startswith("Failed to commit transaction"):
        return SessionContentionError(str(exc))
    return exc


class CoachSessionRepository:
    """users/{uid}/coach_sessions/{sessionId}: one interview per document (coach.md).

    Only the backend writes here, with the Admin SDK; the owner reads through the API. Every
    write that depends on what was read goes through a transaction, so two requests at once
    cannot start two active sessions or overwrite each other's turn.
    """

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def _sessions(self, uid: str) -> CollectionReference:
        sessions: CollectionReference = (
            self._client.collection("users").document(uid).collection("coach_sessions")
        )
        return sessions

    def new_id(self, uid: str) -> str:
        return str(self._sessions(uid).document().id)

    def get(self, uid: str, session_id: str) -> dict[str, Any] | None:
        snapshot = self._sessions(uid).document(session_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def active(self, uid: str) -> list[tuple[str, dict[str, Any]]]:
        """The worker's sessions marked active (at most one in practice), without changing any."""
        query = self._sessions(uid).where(filter=FieldFilter("status", "==", "active")).limit(5)
        return [(str(doc.id), doc.to_dict() or {}) for doc in query.stream()]

    def create_or_resume(
        self,
        uid: str,
        session_id: str,
        document: dict[str, Any],
        *,
        restart: bool,
        idle_before: datetime,
    ) -> tuple[str, dict[str, Any], bool]:
        """The worker's active session, or `document` stored as a new one, in one transaction.

        A session whose `last_active` is `idle_before` or older is closed as `abandoned`, and
        so is any active one when `restart` is true; a new session is then created. Returns the
        session's id, its stored document and whether it already existed.
        """
        sessions = self._sessions(uid)

        @transactional
        def run(transaction: Transaction) -> tuple[str, dict[str, Any], bool]:
            query = sessions.where(filter=FieldFilter("status", "==", "active")).limit(5)
            for snapshot in query.stream(transaction=transaction):
                stored = snapshot.to_dict() or {}
                idle = stored.get("last_active") is None or stored["last_active"] <= idle_before
                if restart or idle:
                    transaction.update(snapshot.reference, {"status": "abandoned"})
                    continue
                return str(snapshot.id), stored, True
            transaction.set(sessions.document(session_id), document)
            return session_id, document, False

        try:
            result: tuple[str, dict[str, Any], bool] = run(
                self._client.transaction(max_attempts=MAX_ATTEMPTS)
            )
        except (Aborted, ValueError) as exc:
            raise _contention(exc) from exc
        return result

    def update(
        self, uid: str, session_id: str, *, expected_revision: int, changes: dict[str, Any]
    ) -> dict[str, Any]:
        """Apply `changes` if the session is still at `expected_revision`; returns the result.

        Raises:
            SessionMissingError: The session does not exist.
            RevisionConflictError: Its revision is not `expected_revision`.
        """
        reference = self._sessions(uid).document(session_id)

        @transactional
        def run(transaction: Transaction) -> dict[str, Any]:
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                raise SessionMissingError(session_id)
            stored = snapshot.to_dict() or {}
            if stored.get("revision") != expected_revision:
                raise RevisionConflictError(session_id)
            merged = {**changes, "revision": expected_revision + 1}
            transaction.update(reference, merged)
            return {**stored, **merged}

        try:
            result: dict[str, Any] = run(self._client.transaction(max_attempts=MAX_ATTEMPTS))
        except (Aborted, ValueError) as exc:
            raise _contention(exc) from exc
        return result


class CoachPlanRepository:
    """users/{uid}/coach_plans/{planId}, read-only here: the newest plan, for the overview."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def newest(self, uid: str) -> tuple[str, dict[str, Any]] | None:
        plans = self._client.collection("users").document(uid).collection("coach_plans")
        for snapshot in plans.order_by("created_at", direction=Query.DESCENDING).limit(1).stream():
            return str(snapshot.id), snapshot.to_dict() or {}
        return None


@lru_cache
def get_coach_session_repository() -> CoachSessionRepository:
    return CoachSessionRepository(get_firestore_client())


@lru_cache
def get_coach_plan_repository() -> CoachPlanRepository:
    return CoachPlanRepository(get_firestore_client())
