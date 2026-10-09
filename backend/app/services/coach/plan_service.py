"""Making and reading the 90-day plan (NF-FC-012).

`CoachPlans.create` is `POST /coach/sessions/{id}/plan`: it looks the plan up by the hash of the
answers and returns it if it exists; otherwise it works out the score and the figures in code, asks
Remittance X-Ray for the cheapest provider, has the model word the plan (checked, see
`plan_generator.py`), stores it and marks the session `completed`. Translation and the PDF are
NF-FC-014's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, cast

from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.config import get_settings
from app.integrations.gemini.model_tiers import ModelTier, model_for
from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.corridor_repo import CorridorRepository
from app.repositories.radar_repo import RadarRepository
from app.repositories.rate_repo import RateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.coach_plan import CoachPlanResponse, slot_hash
from app.schemas.coach_profile import CoachProfile
from app.schemas.remittance_compare import CorridorId
from app.services.coach.coach_scorer import CoachScorer, ScoringData
from app.services.coach.plan_document import build_document, to_response
from app.services.coach.plan_facts import PlanContext
from app.services.coach.plan_figures import Quote, compute_figures
from app.services.coach.plan_generator import PLAN_PROMPT, CoachPlanWriter
from app.services.coach.plan_inputs import plan_inputs, score_inputs_of
from app.services.coach.plan_quote import cheapest_quote
from app.services.coach.scoring import NotScorableError, score_inputs
from app.services.coach.scoring_inputs import ScoreUnavailableError
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import (
    SessionConflictError,
    SessionNotActiveError,
    SessionNotFoundError,
)
from app.utils.corridors import CORRIDOR_HOST_HOME

logger = logging.getLogger(__name__)

# A plan takes 20 to 40 s and the writer may ask twice; a lock older than this was left by a
# request that died.
LOCK_FOR = timedelta(seconds=150)


class PlanNotReadyError(RuntimeError):
    """The worker has not confirmed their answers yet (the stage is not `plan`)."""


class PlanInProgressError(RuntimeError):
    """The plan for these answers is being made by another request."""


class PlanNotFoundError(LookupError):
    """No such plan for this worker."""


@dataclass(frozen=True)
class PlanResult:
    response: CoachPlanResponse
    created: bool


def corridor_of(host: str, home: str | None) -> CorridorId | None:
    """The corridor of a (host, home) pair, or None if it is not one of the six."""
    for corridor_id, pair in CORRIDOR_HOST_HOME.items():
        if pair == (host, home):
            return cast(CorridorId, corridor_id)
    return None


class CoachPlans:
    def __init__(
        self,
        sessions: CoachSessions,
        plans: CoachPlanRepository,
        scorer: CoachScorer,
        writer: CoachPlanWriter,
        users: UserRepository,
        corridors: CorridorRepository,
        rates: RateRepository,
        radar: RadarRepository,
    ) -> None:
        self._sessions = sessions
        self._plans = plans
        self._scorer = scorer
        self._writer = writer
        self._users = users
        self._corridors = corridors
        self._rates = rates
        self._radar = radar

    async def create(self, uid: str, session_id: str, now: datetime) -> PlanResult:
        """The plan for the session's confirmed answers: the stored one, or a new one.

        Raises:
            SessionNotFoundError, SessionNotActiveError: No such session, or it is abandoned.
            PlanNotReadyError: The answers are not confirmed yet.
            PlanInProgressError: Another request is making this plan.
            ScoreUnavailableError: The score (so the plan) cannot be worked out now.
            GeminiError: The sentences failed (`GeminiResponseError` when unusable twice).
        """
        document = await self._sessions.document(uid, session_id, now)
        if document["status"] == "completed" and document.get("plan_id"):
            return PlanResult(await self.get(uid, document["plan_id"], now), created=False)
        if document["status"] != "active":
            raise SessionNotActiveError(document["status"])
        profile = self._confirmed_profile(document)
        plan_id = slot_hash(profile)[:20]
        if await run_in_threadpool(self._plans.get, uid, plan_id) is not None:
            await self._finish(uid, session_id, plan_id, now)
            return PlanResult(await self.get(uid, plan_id, now), created=False)

        await self._lock(uid, session_id, document, plan_id, now)
        try:
            stored = await self._make(uid, session_id, profile, now)
            await self._finish(uid, session_id, plan_id, now)
        except BaseException:
            await self._unlock(uid, session_id, now)
            raise
        return PlanResult(to_response(plan_id, stored, session_id=session_id), created=True)

    async def get(self, uid: str, plan_id: str, now: datetime) -> CoachPlanResponse:
        """A stored plan, in English (other languages: NF-FC-014).

        Raises:
            PlanNotFoundError: No such plan for this worker.
        """
        document = await run_in_threadpool(self._plans.get, uid, plan_id)
        if document is None:
            raise PlanNotFoundError(plan_id)
        session_id: str | None = document.get("session_id")
        try:
            if session_id is not None:
                await self._sessions.document(uid, session_id, now)
        except SessionNotFoundError:
            session_id = None
        return to_response(plan_id, document, session_id=session_id)

    @staticmethod
    def _confirmed_profile(document: dict[str, Any]) -> CoachProfile:
        if document["stage"] != "plan":
            raise PlanNotReadyError(document["stage"])
        try:
            return CoachProfile.model_validate(
                {name: record["value"] for name, record in document["slots"].items()}
            )
        except ValidationError as exc:
            raise PlanNotReadyError("answers") from exc

    async def _lock(
        self, uid: str, session_id: str, document: dict[str, Any], plan_id: str, now: datetime
    ) -> None:
        lock = document.get("plan_lock")
        if lock and now - lock["started_at"] < LOCK_FOR:
            raise PlanInProgressError(plan_id)
        try:
            await self._sessions.write_fields(
                uid, session_id, {"plan_lock": {"hash": plan_id, "started_at": now}}, document
            )
        except SessionConflictError as exc:
            raise PlanInProgressError(plan_id) from exc

    async def _unlock(self, uid: str, session_id: str, now: datetime) -> None:
        try:
            latest = await self._sessions.document(uid, session_id, now)
            await self._sessions.write_fields(uid, session_id, {"plan_lock": None}, latest)
        except (SessionNotFoundError, SessionConflictError):
            logger.warning("coach_plan_unlock_failed")

    async def _finish(self, uid: str, session_id: str, plan_id: str, now: datetime) -> None:
        document = await self._sessions.document(uid, session_id, now)
        if document["status"] == "active":
            await self._sessions.complete(uid, session_id, plan_id, now)

    async def _make(
        self, uid: str, session_id: str, profile: CoachProfile, now: datetime
    ) -> dict[str, Any]:
        data = await self._scorer.load(profile)
        try:
            score = score_inputs(score_inputs_of(profile, data))
        except NotScorableError as exc:
            raise ScoreUnavailableError(f"not_scorable:{exc}") from exc
        inputs = plan_inputs(profile, data)
        host = profile.destination_country or ""
        home = await self._home_country(uid)
        corridor_id = corridor_of(host, home)
        quote: Quote | None = None
        if corridor_id is not None and inputs.remittance > 0:
            quote = await cheapest_quote(
                corridor_id, inputs.remittance, self._corridors, self._rates, self._radar, now
            )
        figures = compute_figures(inputs, corridor_id, quote)
        ctx = PlanContext(
            inputs=inputs,
            figures=figures,
            score=score,
            account=profile.bank_or_wallet or "none",
            job_type=profile.job_type or "other",
            dependents=profile.dependents,
            departure_date=profile.departure_date,
        )
        plan = await self._writer.write(ctx)
        settings = get_settings()
        document = build_document(
            profile=profile,
            session_id=session_id,
            home_country=home,
            corridor_id=corridor_id,
            score=score,
            plan=plan,
            grounding=_grounding(host, data, quote),
            rates_as_of=_rates_as_of(data, quote, now),
            models={"plan": model_for(ModelTier(settings.gemini_coach_plan_tier), settings)},
            prompt_versions={PLAN_PROMPT.key: PLAN_PROMPT.version},
            now=now,
        )
        plan_id = str(document["slot_hash"])[:20]
        await run_in_threadpool(self._plans.create, uid, plan_id, document)
        return document

    async def _home_country(self, uid: str) -> str | None:
        profile = await run_in_threadpool(self._users.get_profile, uid)
        home = profile.get("home_country")
        return home if isinstance(home, str) and len(home) == 2 else None


def _grounding(host: str, data: ScoringData, quote: Quote | None) -> dict[str, Any]:
    """What the figures came from, so a reviewer can check them (data model: `grounding`)."""
    return {
        "baselines": {"host_country": host, "version": data.baseline.get("version")},
        "labor_law": {"country": host, "version": data.law_version},
        "fx": [
            {
                "pair": pair,
                "rate": rate,
                "fetched_at": data.rate_times.get(pair),
                "provider": data.rate_providers.get(pair),
            }
            for pair, rate in sorted(data.rates.items())
        ],
        "provider_quote": (
            None
            if quote is None
            else {"slug": quote.slug, "name": quote.name, "fetched_at": quote.quoted_at}
        ),
    }


def _rates_as_of(data: ScoringData, quote: Quote | None, now: datetime) -> datetime:
    """The oldest rate or quote the plan used; the time of the plan when it used none."""
    times = [t for t in data.rate_times.values() if t is not None]
    if quote is not None:
        times.append(quote.quoted_at)
    return min(times) if times else now
