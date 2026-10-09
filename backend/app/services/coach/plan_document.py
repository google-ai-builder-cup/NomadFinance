"""The stored plan and its view (NF-FC-012): `users/{uid}/coach_plans/{planId}`.

The document is what `docs/data-model/collections/coach.md` lists; `to_response` is the contract's
`CoachPlanResponse`. The plan is stored in English; other languages come with NF-FC-014.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from app.schemas.coach_plan import (
    HOST_CURRENCY,
    CoachPlan,
    CoachPlanResponse,
    CoachScore,
    slot_hash,
)
from app.schemas.coach_profile import CoachProfile, Currency
from app.schemas.contract import ReportLanguage
from app.schemas.remittance_compare import CorridorId
from app.services.coach.coach_scorer import ScoringData
from app.services.coach.plan_figures import PLAN_RULES_VERSION, Quote
from app.services.coach.scoring import RUBRIC_VERSION

SCHEMA_VERSION = 1
ENGLISH: ReportLanguage = "en"


def build_document(
    *,
    profile: CoachProfile,
    session_id: str,
    home_country: str | None,
    corridor_id: CorridorId | None,
    score: CoachScore,
    plan: CoachPlan,
    grounding: dict[str, Any],
    rates_as_of: datetime,
    models: dict[str, str],
    prompt_versions: dict[str, int],
    now: datetime,
) -> dict[str, Any]:
    """The plan as stored. Absent values are left out, as the data model says."""
    host = profile.destination_country or ""
    document: dict[str, Any] = {
        "slot_hash": slot_hash(profile),
        "session_id": session_id,
        "slots": profile.model_dump(mode="json", exclude_none=True),
        "host_country": host,
        "reporting_currency": HOST_CURRENCY[host],
        "score": score.model_dump(mode="json"),
        "plan": plan.model_dump(mode="json"),
        "grounding": grounding,
        "rates_as_of": rates_as_of,
        "language_generated": ENGLISH,
        "models": models,
        "prompt_versions": prompt_versions,
        "plan_rules_version": PLAN_RULES_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "created_at": now,
        "updated_at": now,
        "schema_version": SCHEMA_VERSION,
    }
    optional = {
        "home_country": home_country,
        "corridor_id": corridor_id,
        "departure_date": profile.departure_date,
    }
    document.update({key: value for key, value in optional.items() if value})
    return document


def to_response(
    plan_id: str,
    document: dict[str, Any],
    *,
    session_id: str | None,
    language: ReportLanguage = ENGLISH,
    plan: CoachPlan | None = None,
    available: list[ReportLanguage] | None = None,
) -> CoachPlanResponse:
    """The contract's view of a stored plan: in English, or in `language` when `plan` is the
    translation (`available` lists the languages stored)."""
    return CoachPlanResponse(
        id=plan_id,
        session_id=session_id,
        language=language,
        available_languages=available or [ENGLISH],
        host_country=document["host_country"],
        home_country=document.get("home_country"),
        corridor_id=document.get("corridor_id"),
        departure_date=document.get("departure_date"),
        reporting_currency=cast(Currency, document["reporting_currency"]),
        slots=document["slots"],
        rates_as_of=document["rates_as_of"],
        score=CoachScore.model_validate(document["score"]),
        plan=plan or CoachPlan.model_validate(document["plan"]),
        created_at=document["created_at"],
    )


def grounding_of(host: str, data: ScoringData, quote: Quote | None) -> dict[str, Any]:
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


def rates_as_of(data: ScoringData, quote: Quote | None, now: datetime) -> datetime:
    """The oldest rate or quote the plan used; the time of the plan when it used none."""
    times = [t for t in data.rate_times.values() if t is not None]
    if quote is not None:
        times.append(quote.quoted_at)
    return min(times) if times else now
