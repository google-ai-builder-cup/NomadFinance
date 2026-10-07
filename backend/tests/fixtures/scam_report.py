"""In-memory stand-ins for the report route's storage (NF-SA-013 tests).

`FakeReportRepo` keeps the semantics of the real transaction (a check is reported once; the
indicator counters come from the real `merge_indicator`), so the endpoint and the service can be
tested without Firestore. The transaction itself is tested against the emulator
(`tests/integration/repositories/test_scam_report_repository.py`).
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from datetime import datetime
from typing import Any, cast

from google.api_core.exceptions import ServiceUnavailable

from app.integrations.gemini import GeminiClient, GeminiUnavailableError
from app.repositories.radar_repo import RadarRepository, SimilarReport
from app.repositories.scam_report_repo import (
    CheckGoneError,
    CommitResult,
    IndicatorUpdate,
    ScamReportRepository,
    merge_indicator,
)
from app.repositories.scam_taxonomy_repo import ScamTaxonomyRepository
from app.repositories.user_repo import UserRepository
from app.schemas.radar import RadarReport
from app.services.scam.check_store import CheckStore
from app.services.scam.report import ScamReporter
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_checks import FakeCheckRepo, FakeIndicatorRepo
from tests.fixtures.scam_classify import load_taxonomy

VECTOR = [0.1] * 768


class EmbedGemini(FakeGemini):
    """`FakeGemini` that can also embed, as the real client does."""

    def __init__(self, *, fail: bool = False) -> None:
        super().__init__()
        self.fail = fail
        self.embedded: list[tuple[str, str]] = []

    async def embed_text(self, text: str, *, operation: str) -> list[float]:
        self.embedded.append((text, operation))
        if self.fail:
            raise GeminiUnavailableError("embedding is down")
        return VECTOR


class FakeRadar:
    """The parts of `RadarRepository` a report touches."""

    def __init__(self) -> None:
        self.reports: dict[str, dict[str, Any]] = {}
        self.embeddings: list[dict[str, Any]] = []
        self.entities: dict[str, dict[str, Any]] = {}
        self.neighbours: list[SimilarReport] = []
        self.embedding_store_down = False
        self._count = 0

    def new_report_id(self) -> str:
        self._count += 1
        return f"r_{self._count:02d}"

    def get(self, report_id: str) -> dict[str, Any] | None:
        stored = self.reports.get(report_id)
        return copy.deepcopy(stored) if stored is not None else None

    def find_similar(self, embedding: list[float], corridor_id: str, limit: int) -> list[Any]:
        return self.neighbours

    def get_cluster_id(self, report_id: str) -> str | None:
        stored = self.reports.get(report_id)
        return str(stored["cluster_id"]) if stored else None

    def create_embedding(self, report_id: str, embedding: list[float], **fields: Any) -> None:
        if self.embedding_store_down:
            raise ServiceUnavailable("firestore is down")  # type: ignore[no-untyped-call]
        self.embeddings.append({"report_id": report_id, "length": len(embedding), **fields})

    def get_entity(self, slug: str) -> dict[str, Any] | None:
        return self.entities.get(slug)

    def set_entity(self, entity: Any) -> None:
        self.entities[entity.slug] = entity.model_dump()


class FakeUsers:
    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile if profile is not None else {"host_country": "SG"}

    def get_profile(self, uid: str) -> dict[str, Any]:
        return dict(self.profile)


class FakeReportRepo:
    """`ScamReportRepository.commit_report` with the real counters and the same once-only rule."""

    def __init__(self, checks: FakeCheckRepo, indicators: FakeIndicatorRepo, radar: FakeRadar):
        self.checks = checks
        self.indicators = indicators
        self.radar = radar
        self.calls = 0
        self.before_commit: Callable[[], None] | None = None  # to let "another tap" win first

    def commit_report(
        self,
        *,
        uid: str,
        check_id: str,
        report_id: str,
        report: RadarReport,
        updates: list[IndicatorUpdate],
        scam_type: str,
        now: datetime,
    ) -> CommitResult:
        self.calls += 1
        if self.before_commit:
            self.before_commit()
        document = self.checks.docs.get((uid, check_id))
        if document is None:
            raise CheckGoneError(check_id)
        if document.get("reported_report_id"):
            return CommitResult(str(document["reported_report_id"]), created=False)
        self.radar.reports[report_id] = report.model_dump(exclude_none=True)
        for update in updates:
            self.indicators.docs[update.doc_id] = merge_indicator(
                self.indicators.docs.get(update.doc_id),
                update,
                scam_type=scam_type,
                corridor_id=report.corridor_id,
                host_country=report.host_country,
                new_incident=report.cluster_id == report_id,
                now=now,
            )
        document["reported_report_id"] = report_id
        document["reported_at"] = now
        return CommitResult(report_id, created=True)


class ReportWorld:
    """Everything one report touches, sharing state, with a reporter built on it."""

    def __init__(
        self,
        checks: FakeCheckRepo | None = None,
        indicators: FakeIndicatorRepo | None = None,
        *,
        profile: dict[str, Any] | None = None,
        embed_fails: bool = False,
    ) -> None:
        self.checks = checks or FakeCheckRepo()
        self.indicators = indicators or FakeIndicatorRepo()
        self.radar = FakeRadar()
        self.users = FakeUsers(profile)
        self.reports = FakeReportRepo(self.checks, self.indicators, self.radar)
        self.gemini = EmbedGemini(fail=embed_fails)
        self.store = CheckStore(
            cast(Any, self.checks),
            cast(Any, self.indicators),
        )
        self.reporter = ScamReporter(
            self.store,
            cast(ScamReportRepository, self.reports),
            cast(RadarRepository, self.radar),
            cast(UserRepository, self.users),
            cast(ScamTaxonomyRepository, _Taxonomy()),
            cast(GeminiClient, self.gemini),
        )


class _Taxonomy:
    def get_taxonomy(self) -> Any:
        return load_taxonomy()
