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
from app.schemas.remittance_compare import CorridorId
from app.services.coach.plan_figures import PLAN_RULES_VERSION
from app.services.coach.scoring import RUBRIC_VERSION

SCHEMA_VERSION = 1
ENGLISH = "en"


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
    plan_id: str, document: dict[str, Any], *, session_id: str | None
) -> CoachPlanResponse:
    """The contract's view of a stored plan, in English."""
    return CoachPlanResponse(
        id=plan_id,
        session_id=session_id,
        language=ENGLISH,
        available_languages=[ENGLISH],
        host_country=document["host_country"],
        home_country=document.get("home_country"),
        corridor_id=document.get("corridor_id"),
        departure_date=document.get("departure_date"),
        reporting_currency=cast(Currency, document["reporting_currency"]),
        slots=document["slots"],
        rates_as_of=document["rates_as_of"],
        score=CoachScore.model_validate(document["score"]),
        plan=CoachPlan.model_validate(document["plan"]),
        created_at=document["created_at"],
    )
