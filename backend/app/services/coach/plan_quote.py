"""The cheapest provider Remittance X-Ray finds for the plan's monthly transfer (NF-FC-012)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import cast

from app.repositories.corridor_repo import CorridorRepository
from app.repositories.radar_repo import RadarRepository
from app.repositories.rate_repo import RateRepository
from app.schemas.coach_profile import Currency
from app.schemas.remittance_compare import CorridorId
from app.services.coach.plan_figures import Quote
from app.services.cross_pillar.radar_to_remittance import flag_providers
from app.services.remittance.engine import (
    AmountOutOfRangeError,
    CorridorNotFoundError,
    compare_remittance,
)
from app.services.remittance.recommender import RecommendationIncompleteError, recommended_provider
from app.utils.slugs import slugify

logger = logging.getLogger(__name__)


def _quoted_at(fetched_at: datetime | None, surveyed_to: str) -> datetime:
    """When the rate was fetched; for a survey-only rate, the end of the survey."""
    if fetched_at is not None:
        return fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(surveyed_to).replace(tzinfo=UTC)
    except ValueError:
        return datetime.now(UTC)


async def cheapest_quote(
    corridor_id: CorridorId,
    amount: float,
    corridors: CorridorRepository,
    rates: RateRepository,
    radar: RadarRepository,
    now: datetime,
) -> Quote | None:
    """The top-ranked service not flagged on the Exploitation Radar, or None if no price can be
    worked out (the plan then says so and has no provider)."""
    try:
        comparison = await compare_remittance(corridor_id, amount, corridors, rates, now)
        comparison = await flag_providers(comparison, radar)
        best = recommended_provider(comparison)
    except (CorridorNotFoundError, AmountOutOfRangeError, RecommendationIncompleteError) as exc:
        logger.warning("coach_plan_no_quote corridor=%s reason=%s", corridor_id, type(exc).__name__)
        return None
    if best.recipient_receives is None or best.fee >= amount:
        return None
    return Quote(
        slug=slugify(best.firm),
        name=best.firm,
        fee=best.fee,
        receives=best.recipient_receives,
        receive_currency=_currency(comparison.receive_currency),
        quoted_at=_quoted_at(comparison.rate.fetched_at, comparison.survey.surveyed_to),
    )


def _currency(code: str) -> Currency:
    return cast(Currency, code)
