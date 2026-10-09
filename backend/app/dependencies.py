from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.core.logging import bind_user
from app.core.security import (
    InvalidTokenError,
    TokenVerificationUnavailableError,
    verify_app_check_token,
    verify_google_oidc_token,
    verify_id_token,
)
from app.integrations.cloud_storage import ExportStore, UserFileStore, get_export_store
from app.integrations.firebase_auth import delete_firebase_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.base import get_firestore_client
from app.repositories.coach_session_repo import (
    CoachPlanRepository,
    CoachSessionRepository,
    get_coach_plan_repository,
    get_coach_session_repository,
)
from app.repositories.config_repo import get_config_repository
from app.repositories.contract_repo import ContractRepository, get_contract_repository
from app.repositories.corridor_repo import CorridorRepository, get_corridor_repository
from app.repositories.cost_baseline_repo import (
    CostBaselineRepository,
    get_cost_baseline_repository,
)
from app.repositories.fib_repo import FibRepository, get_fib_repository
from app.repositories.labor_law_repo import LaborLawRepository, get_labor_law_repository
from app.repositories.radar_repo import RadarRepository, get_radar_repository
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.repositories.scam_check_repo import ScamCheckRepository, get_scam_check_repository
from app.repositories.scam_indicator_repo import (
    ScamIndicatorRepository,
    get_scam_indicator_repository,
)
from app.repositories.scam_pattern_repo import ScamPatternRepository, get_scam_pattern_repository
from app.repositories.scam_report_repo import ScamReportRepository, get_scam_report_repository
from app.repositories.scam_taxonomy_repo import (
    ScamTaxonomyRepository,
    get_scam_taxonomy_repository,
)
from app.repositories.user_repo import UserRepository, get_user_repository
from app.schemas.user import AuthenticatedUser
from app.services.auth_service import AccountService
from app.services.coach.coach_scorer import CoachScorer
from app.services.coach.guard import CoachGuard
from app.services.coach.plan_files import PlanFiles
from app.services.coach.plan_generator import CoachPlanWriter
from app.services.coach.plan_service import CoachPlans
from app.services.coach.plan_translator import CoachPlanTranslator
from app.services.coach.prefill import contract_prefill_finder
from app.services.coach.session_service import CoachSessions
from app.services.coach.slot_extractor import CoachSlotExtractor
from app.services.coach.turn_service import CoachTurns
from app.services.feature_flag_service import FeatureFlagService, FlagName
from app.services.scam.check_store import CheckStore
from app.services.scam.report import ScamReporter
from app.services.scam.retrieval import SimilarScamFinder

logger = logging.getLogger(__name__)

# auto_error=False so a missing token becomes our own 401 instead of FastAPI's default.
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    # FastAPI's own Depends()-in-default pattern; ruff's bugbear check doesn't know it.
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
) -> AuthenticatedUser:
    """Verify the request's Firebase Auth bearer token and return the caller's identity.

    Add `Depends(get_current_user)` to any endpoint that isn't public; endpoints
    that skip it must say so per the Backend Endpoint Definition of Done.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = verify_id_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    bind_user(claims["uid"])
    return AuthenticatedUser(
        uid=claims["uid"],
        email=claims.get("email"),
        email_verified=claims.get("email_verified", False),
        phone_number=claims.get("phone_number"),
        name=claims.get("name"),
        picture=claims.get("picture"),
        auth_time=claims.get("auth_time"),
    )


async def verify_app_check(
    token: Annotated[str | None, Header(alias="X-Firebase-AppCheck")] = None,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> None:
    """Reject a call that isn't from a verified instance of the app (NF-P3-025).

    Add `Depends(verify_app_check)` to an endpoint worth protecting from scripted abuse,
    distinct from `get_current_user`: App Check attests to the calling app, not the signed-in
    person. Off by default (`Settings.app_check_enabled`) until a real reCAPTCHA v3 site key
    is wired through the frontend for a deployed domain — enforcing before then would reject
    every real submission, not just bots (see the NF-P3-025 runbook, "Before this works in
    production").
    """
    if not settings.app_check_enabled:
        return
    if token is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing App Check token")
    try:
        await run_in_threadpool(verify_app_check_token, token)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except TokenVerificationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc


async def require_cloud_scheduler(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> str:
    """Allow only Cloud Scheduler's signed calls to /api/v1/internal/* and return its email.

    The Cloud Run service is public (user endpoints check Firebase tokens themselves),
    so this check is the only gate in front of the internal endpoints.
    """
    if not (settings.cron_service_account and settings.cron_audience):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal endpoints are not configured",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = await run_in_threadpool(
            verify_google_oidc_token, credentials.credentials, settings.cron_audience
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except TokenVerificationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    if (
        claims.get("email") != settings.cron_service_account
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Caller is not allowed")
    return settings.cron_service_account


@lru_cache
def get_account_service() -> AccountService:
    """The account-deletion service wired to real Firestore, Storage and Firebase Auth."""
    return AccountService(get_firestore_client(), UserFileStore(), delete_firebase_user)


@lru_cache
def get_feature_flag_service() -> FeatureFlagService:
    """One per process: the service holds the one-minute copy of `config/feature_flags`."""
    return FeatureFlagService(get_config_repository())


def get_similar_scam_finder(
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    patterns: Annotated[ScamPatternRepository, Depends(get_scam_pattern_repository)],
    reports: Annotated[RadarRepository, Depends(get_radar_repository)],
) -> SimilarScamFinder:
    """The Scam Analyzer's neighbour search (NF-SA-010), on the shared Gemini client."""
    return SimilarScamFinder(gemini, patterns, reports)


def get_scam_check_store(
    checks: Annotated[ScamCheckRepository, Depends(get_scam_check_repository)],
    indicators: Annotated[ScamIndicatorRepository, Depends(get_scam_indicator_repository)],
) -> CheckStore:
    """The worker's stored scam checks and the cache over them (NF-SA-012)."""
    return CheckStore(checks, indicators)


def get_coach_sessions(
    sessions: Annotated[CoachSessionRepository, Depends(get_coach_session_repository)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
    baselines: Annotated[CostBaselineRepository, Depends(get_cost_baseline_repository)],
    laws: Annotated[LaborLawRepository, Depends(get_labor_law_repository)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
    contracts: Annotated[ContractRepository, Depends(get_contract_repository)],
) -> CoachSessions:
    """The worker's Financial Coach sessions and their state machine (NF-FC-008), with the
    preparedness score from `review` on (NF-FC-011)."""
    return CoachSessions(
        sessions,
        plans,
        scorer=CoachScorer(baselines, laws, rates),
        prefills=contract_prefill_finder(contracts),
    )


def get_coach_plans(
    sessions: Annotated[CoachSessions, Depends(get_coach_sessions)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
    baselines: Annotated[CostBaselineRepository, Depends(get_cost_baseline_repository)],
    laws: Annotated[LaborLawRepository, Depends(get_labor_law_repository)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
    corridors: Annotated[CorridorRepository, Depends(get_corridor_repository)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    exports: Annotated[ExportStore, Depends(get_export_store)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
) -> CoachPlans:
    """The 90-day plan of the Financial Coach (NF-FC-012): the figures in code, the sentences
    from Gemini, the cheapest provider from Remittance X-Ray; its translations and PDF
    (NF-FC-014)."""
    return CoachPlans(
        sessions,
        plans,
        CoachScorer(baselines, laws, rates),
        CoachPlanWriter(gemini),
        users,
        corridors,
        rates,
        radar,
        PlanFiles(plans, CoachPlanTranslator(gemini), exports),
        fib,
    )


def get_coach_turns(
    sessions: Annotated[CoachSessions, Depends(get_coach_sessions)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> CoachTurns:
    """The Financial Coach's turn: the guardrails (NF-FC-013), slot extraction (NF-FC-010), then
    the streamed reply (NF-FC-009), all on the shared Gemini client."""
    return CoachTurns(
        sessions, gemini, extractor=CoachSlotExtractor(gemini), guard=CoachGuard(gemini)
    )


def get_scam_reporter(
    store: Annotated[CheckStore, Depends(get_scam_check_store)],
    reports: Annotated[ScamReportRepository, Depends(get_scam_report_repository)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    taxonomy: Annotated[ScamTaxonomyRepository, Depends(get_scam_taxonomy_repository)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
) -> ScamReporter:
    """The one-tap report of a scam check to Exploitation Radar (NF-SA-013)."""
    return ScamReporter(store, reports, radar, users, taxonomy, gemini)


def require_flag(flag: FlagName) -> Callable[..., Awaitable[None]]:
    """Guard a route behind a Future Scope flag (NF-F0-005).

    Use as `dependencies=[Depends(require_flag("scam"))]`. When the flag is off for the
    caller the answer is the same 404 an unknown path gets, so a disabled module cannot be
    told from a missing one; under `/api/v2` that is the standard error envelope with code
    `not_found`. It needs the caller's uid for the allow-list, so a request without a valid
    token is a 401 first, like every other route behind sign-in.
    """

    async def check(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        service: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
    ) -> None:
        if not await service.is_enabled(flag, user.uid):
            logger.info("feature_flag_off flag=%s", flag)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    return check
