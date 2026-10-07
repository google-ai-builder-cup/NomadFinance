"""An app wired for the Scam Analyzer's endpoint tests (NF-SA-007, -008, -010, -012).

Auth, the `scam` flag, Gemini, the taxonomy, the similar-scam search and the stored checks are
replaced; everything else (middleware, error handlers, rate limits, routing) is the real app,
so a test sees what a client would.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from app.dependencies import (
    get_current_user,
    get_feature_flag_service,
    get_scam_check_store,
    get_scam_reporter,
    get_similar_scam_finder,
)
from app.integrations.gemini import get_gemini_client
from app.main import create_app
from app.repositories.scam_taxonomy_repo import ScamTaxonomy, get_scam_taxonomy_repository
from app.schemas.errors import ErrorEnvelope
from app.schemas.user import AuthenticatedUser
from app.services.feature_flag_service import FeatureFlagService
from app.services.scam.check_store import CheckStore
from app.services.scam.report import ScamReporter
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_checks import make_store
from tests.fixtures.scam_classify import load_taxonomy
from tests.fixtures.scam_similar import FakeFinder


class FakeFlags:
    def __init__(self, enabled: bool) -> None:
        self._enabled = enabled

    def get_feature_flags(self) -> dict[str, Any]:
        return {"flags": {"scam": {"enabled": self._enabled, "allow_uids": []}}}


class FakeTaxonomyRepo:
    def __init__(self, taxonomy: ScamTaxonomy | None) -> None:
        self._taxonomy = taxonomy

    def get_taxonomy(self) -> ScamTaxonomy | None:
        return self._taxonomy


def make_app(
    gemini: FakeGemini,
    *,
    flag_on: bool = True,
    signed_in: bool = True,
    taxonomy: ScamTaxonomy | None = None,
    finder: FakeFinder | None = None,
    store: CheckStore | None = None,
    uid: str = "test-user",
    reporter: ScamReporter | None = None,
) -> FastAPI:
    app = create_app()
    flags = FeatureFlagService(FakeFlags(flag_on))  # type: ignore[arg-type]
    app.dependency_overrides[get_feature_flag_service] = lambda: flags
    if signed_in:
        app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(uid=uid)
    app.dependency_overrides[get_gemini_client] = lambda: gemini
    repo = FakeTaxonomyRepo(taxonomy or load_taxonomy())
    app.dependency_overrides[get_scam_taxonomy_repository] = lambda: repo
    # No Firestore and no embedding call in an endpoint test: the search is faked.
    fake_finder = finder or FakeFinder()
    app.dependency_overrides[get_similar_scam_finder] = lambda: fake_finder
    # No Firestore either: checks are stored in memory, so each app starts with an empty history.
    fake_store = store or make_store()
    app.dependency_overrides[get_scam_check_store] = lambda: fake_store
    # The report route gets a reporter on in-memory storage unless a test brings its own world.
    if reporter is None:
        from tests.fixtures.scam_report import ReportWorld

        reporter = ReportWorld().reporter
    fake_reporter = reporter
    app.dependency_overrides[get_scam_reporter] = lambda: fake_reporter
    return app


def assert_envelope(response: Any, status: int, code: str) -> ErrorEnvelope:
    assert response.status_code == status
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.code == code
    assert envelope.request_id == response.headers["X-Request-ID"]
    return envelope
