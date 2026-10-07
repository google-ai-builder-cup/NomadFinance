"""In-memory stand-ins for the stored scam checks and indicator counts (NF-SA-012 tests)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any, cast

from google.api_core.exceptions import ServiceUnavailable

from app.repositories.scam_check_repo import ScamCheckRepository
from app.repositories.scam_indicator_repo import ScamIndicatorRepository
from app.services.scam.check_store import CheckStore

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


class FakeCheckRepo:
    """`ScamCheckRepository` with the same semantics: ids per worker, newest first, `touch`."""

    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], dict[str, Any]] = {}
        self.saves = 0
        self.touches = 0
        self.down = False  # every call fails like an unreachable Firestore

    def _check_up(self) -> None:
        if self.down:
            raise ServiceUnavailable("firestore is down")

    def get(self, uid: str, check_id: str) -> dict[str, Any] | None:
        self._check_up()
        stored = self.docs.get((uid, check_id))
        return copy.deepcopy(stored) if stored is not None else None

    def save(self, uid: str, check_id: str, data: dict[str, Any]) -> None:
        self._check_up()
        self.saves += 1
        self.docs[(uid, check_id)] = copy.deepcopy(data)

    def touch(
        self, uid: str, check_id: str, *, last_checked_at: datetime, expires_at: datetime
    ) -> None:
        self._check_up()
        self.touches += 1
        stored = self.docs[(uid, check_id)]
        stored["check_count"] = stored.get("check_count", 0) + 1
        stored["last_checked_at"] = last_checked_at
        stored["expires_at"] = expires_at

    def list_newest(
        self, uid: str, limit: int, *, before: datetime | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        self._check_up()
        rows = [
            (check_id, copy.deepcopy(doc))
            for (owner, check_id), doc in self.docs.items()
            if owner == uid and (before is None or doc["created_at"] < before)
        ]
        rows.sort(key=lambda row: row[1]["created_at"], reverse=True)
        return rows[:limit]

    def mine(self, uid: str) -> list[dict[str, Any]]:
        return [doc for (owner, _), doc in self.docs.items() if owner == uid]


class FakeIndicatorRepo:
    def __init__(self, docs: dict[str, dict[str, Any]] | None = None) -> None:
        self.docs = docs or {}
        self.down = False

    def get_many(self, doc_ids: list[str]) -> dict[str, dict[str, Any]]:
        if self.down:
            raise ServiceUnavailable("firestore is down")
        return {i: copy.deepcopy(self.docs[i]) for i in doc_ids if i in self.docs}


def make_store(
    checks: FakeCheckRepo | None = None, indicators: FakeIndicatorRepo | None = None
) -> CheckStore:
    return CheckStore(
        cast(ScamCheckRepository, checks or FakeCheckRepo()),
        cast(ScamIndicatorRepository, indicators or FakeIndicatorRepo()),
    )


def mock_check(case: str = "high", **changes: Any) -> Any:
    """A `ScamAnalyzeResponse` from one of the contract's mocks, with a fixed clock."""
    from app.schemas.scam import ScamAnalyzeResponse
    from app.services.scam.check_store import CHECK_TTL
    from tests.fixtures.scam_classify import load_mock_body

    body = load_mock_body(case)
    return ScamAnalyzeResponse.model_validate(
        {**body, "cached": False, "created_at": NOW, "expires_at": NOW + CHECK_TTL, **changes}
    )


def put_check(
    repo: FakeCheckRepo,
    uid: str,
    check: Any,
    *,
    taxonomy_version: int = 1,
    **document_changes: Any,
) -> str:
    """Store `check` as the analyzer would have, under the id its text and language give."""
    from app.services.scam.check_store import cache_key, check_id_for, to_document

    key = cache_key(check.redacted_text, check.language)
    check_id = check_id_for(key)
    document = to_document(
        check.model_copy(update={"id": check_id}),
        key=key,
        taxonomy_version=taxonomy_version,
        check_count=1,
        last_checked_at=check.created_at,
        reported_at=None,
    )
    repo.docs[(uid, check_id)] = {**document, **document_changes}
    return check_id
