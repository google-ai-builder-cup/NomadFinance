"""The preparedness score of a worker's answers, from stored data (NF-FC-011).

Reads the three things the rubric needs, then hands them to the pure engine: the living costs of
the destination (`cost_baselines`), the legal fee cap (`labor_laws`) and the exchange rates
(`rates_cache`). Anything missing makes the score unavailable, never a guess: the session then
shows `score: null`, which the contract allows ("try again").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.repositories.cost_baseline_repo import CostBaselineRepository
from app.repositories.labor_law_repo import LaborLawRepository
from app.repositories.rate_repo import RateRepository
from app.schemas.coach_plan import CoachScore
from app.schemas.coach_profile import CoachProfile
from app.services.coach.scoring import NotScorableError, score_inputs
from app.services.coach.scoring_inputs import (
    HOST_CURRENCY,
    ScoreUnavailableError,
    build_inputs,
    currencies_to_convert,
    essentials_from,
    fee_cap_months,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringData:
    """What the stored collections gave for one profile, so the plan reads the same figures."""

    baseline: dict[str, Any]
    law_version: int | None
    rules: dict[str, dict[str, Any]]
    rates: dict[str, float]
    rate_times: dict[str, datetime | None]
    rate_providers: dict[str, str]


class CoachScorer:
    def __init__(
        self, baselines: CostBaselineRepository, laws: LaborLawRepository, rates: RateRepository
    ) -> None:
        self._baselines = baselines
        self._laws = laws
        self._rates = rates

    async def load(self, profile: CoachProfile) -> ScoringData:
        """The baseline, the law and the rates a profile needs.

        Raises:
            ScoreUnavailableError: An answer, the baseline or the fee rule is missing.
        """
        host, job = profile.destination_country, profile.job_type
        if host is None or job is None:
            raise ScoreUnavailableError("incomplete")
        baseline = await run_in_threadpool(self._baselines.get_baseline, host)
        if baseline is None:
            raise ScoreUnavailableError(f"no_baseline:{host}")
        if baseline.get("currency") != HOST_CURRENCY[host]:
            raise ScoreUnavailableError(f"baseline_currency:{host}")
        version = await run_in_threadpool(self._laws.get_version, host)
        rules = await run_in_threadpool(self._laws.get_rules, host, version)
        if "recruitment_fees" not in rules:
            raise ScoreUnavailableError(f"no_fee_rule:{host}")
        rates, times, providers = await self._rates_for(profile, host)
        return ScoringData(baseline, version, rules, rates, times, providers)

    async def score(self, profile: CoachProfile) -> CoachScore:
        """The score of a complete profile.

        Raises:
            ScoreUnavailableError: An answer, the baseline, the law or a rate is missing.
        """
        data = await self.load(profile)
        inputs = build_inputs(
            profile,
            essentials=essentials_from(data.baseline, profile.job_type or ""),
            cap_months=fee_cap_months(data.rules),
            rates=data.rates,
        )
        try:
            return score_inputs(inputs)
        except NotScorableError as exc:
            raise ScoreUnavailableError(f"not_scorable:{exc}") from exc

    async def __call__(self, profile: CoachProfile) -> CoachScore | None:
        """The score, or None when it cannot be worked out now (the reason is logged)."""
        try:
            return await self.score(profile)
        except ScoreUnavailableError as exc:
            logger.warning("coach_score_unavailable reason=%s", exc.reason)
            return None

    async def _rates_for(
        self, profile: CoachProfile, host: str
    ) -> tuple[dict[str, float], dict[str, datetime | None], dict[str, str]]:
        rates: dict[str, float] = {}
        times: dict[str, datetime | None] = {}
        providers: dict[str, str] = {}
        for currency in sorted(currencies_to_convert(profile, host)):
            pair = f"{HOST_CURRENCY[host]}_{currency}"
            stored: dict[str, Any] | None = await run_in_threadpool(self._rates.get_rate, pair)
            if stored is not None and isinstance(stored.get("rate"), (int, float)):
                rates[pair] = float(stored["rate"])
                fetched = stored.get("fetched_at")
                times[pair] = fetched if isinstance(fetched, datetime) else None
                providers[pair] = str(stored.get("provider", ""))
        return rates, times, providers
