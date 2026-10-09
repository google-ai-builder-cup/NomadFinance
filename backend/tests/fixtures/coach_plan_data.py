"""Stand-ins and helpers for the 90-day plan tests (NF-FC-012).

The data is the real curated data (cost baselines, labor-law files, the World Bank corridors) and
the personas' fixed rates; the stand-in for Gemini writes sentences from the facts it is shown, so
a test exercises the real prompt rendering, the real checks and the real assembly.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.schemas.coach_plan_text import NoteText, PlanText, WeekText
from app.schemas.coach_profile import SLOT_NAMES
from app.services.coach.coach_scorer import CoachScorer
from app.services.coach.session_service import CoachSessions
from app.services.coach.session_types import SlotUpdate
from tests.fixtures.coach_personas import Persona
from tests.fixtures.coach_scoring_data import FakeBaselines, FakeLaws, FakeRates
from tests.fixtures.coach_sessions import NOW

UID = "worker-1"
PROCESSED = Path(__file__).resolve().parents[3] / "data-scripts" / "data" / "processed"
RPW: dict[str, Any] = json.loads((PROCESSED / "rpw_corridors.json").read_text(encoding="utf-8"))
RAW_CORRIDORS = {c["corridor_id"]: c for c in RPW["corridors"]}


class FakeCorridors:
    """`corridors/{id}` from the committed World Bank data, as the loader stores it."""

    def get_corridor(self, corridor_id: str) -> dict[str, Any] | None:
        raw = RAW_CORRIDORS.get(corridor_id)
        return {**raw, "source": RPW["source"]} if raw else None


class FakeRadar:
    def __init__(self, flagged: list[dict[str, Any]] | None = None) -> None:
        self.flagged = flagged or []

    def flagged_entities(self, entity_type: str) -> list[dict[str, Any]]:
        return self.flagged


class FakeUsers:
    def __init__(self, home_country: str | None) -> None:
        self.home_country = home_country

    def get_profile(self, uid: str) -> dict[str, Any]:
        return {"home_country": self.home_country} if self.home_country else {}


def persona_rates(persona: Persona) -> dict[str, float]:
    return {persona.expected_score.rate_pair: persona.expected_score.rate}


def persona_scorer(persona: Persona) -> CoachScorer:
    return CoachScorer(
        FakeBaselines(),  # type: ignore[arg-type]
        FakeLaws(),  # type: ignore[arg-type]
        FakeRates(persona_rates(persona)),  # type: ignore[arg-type]
    )


def persona_rate_repo(persona: Persona) -> FakeRates:
    return FakeRates(persona_rates(persona))


async def reach_plan_stage(service: CoachSessions, persona: Persona) -> str:
    """A session with every answer of the persona, confirmed, at the `plan` stage."""
    started = await service.start(UID, "en", restart=False, now=NOW)
    session_id = started.session.id
    slots = persona.expected_slots.model_dump(mode="json", exclude_none=True)
    updates = [SlotUpdate(name, slots[name], 0.95, True) for name in SLOT_NAMES if name in slots]  # type: ignore[arg-type]
    await service.record_turn(
        UID,
        session_id,
        language="en",
        now=NOW + timedelta(minutes=1),
        updates=updates,
        declined=persona.declined_slots,  # type: ignore[arg-type]
    )
    await service.confirm_review(UID, session_id, NOW + timedelta(minutes=2))
    return session_id


def _section(contents: str, tag: str) -> Any:
    found = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", contents, re.DOTALL)
    assert found, tag
    return found.group(1)


def money(value: float, currency: str) -> str:
    return f"{round(value):,} {currency}"


def compliant_text(contents: str) -> PlanText:
    """Sentences that use only the facts they were given, as a well-behaved model would."""
    facts = json.loads(_section(contents, "facts"))
    warnings = json.loads(_section(contents, "warnings_to_write"))
    checklist = json.loads(_section(contents, "checklist_to_write"))
    cur = facts["currency"]
    budget = facts["monthly_budget"]
    summary = (
        f"You will earn about {money(budget['income'], cur)} a month. "
        f"You plan to send {money(facts['remittance']['monthly_amount'], cur)} home each month."
    )
    weeks = [
        WeekText(
            week=n,
            title=f"Week {n}",
            actions=[
                f"Check your spending against the plan in week {n}.",
                "Keep your payslips and receipts safe.",
            ],
        )
        for n in range(1, 14)
    ]
    return PlanText(
        summary=summary,
        weeks=weeks,
        warnings=[
            NoteText(id=w["id"], text=f"Please look at this: {w['about']}") for w in warnings
        ],
        checklist=[NoteText(id=c["id"], text=c["about"]) for c in checklist],
    )


class WritingGemini:
    """Answers the plan call with `compliant_text`, or with what a test scripts first."""

    def __init__(self, *scripted: Any) -> None:
        self.scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> PlanText:
        self.calls.append(kwargs)
        if self.scripted:
            step = self.scripted.pop(0)
            if isinstance(step, Exception):
                raise step
            return step(kwargs["contents"]) if callable(step) else step  # type: ignore[no-any-return]
        return compliant_text(kwargs["contents"])


def make_plans(
    persona: Persona,
    *,
    home: str | None = "same",
    gemini: WritingGemini | None = None,
    rates: dict[str, float] | None = None,
    radar: FakeRadar | None = None,
) -> Any:
    """`CoachPlans` over in-memory storage for a persona. `home="same"` is the persona's own home
    country; `None` is a profile with no home country."""
    from app.services.coach.plan_generator import CoachPlanWriter
    from app.services.coach.plan_service import CoachPlans
    from tests.fixtures.coach_sessions import make_sessions

    service, session_repo, plan_repo = make_sessions()
    home_country = persona.corridor.split("-")[1] if home == "same" else home
    stub = gemini or WritingGemini()
    scorer = CoachScorer(
        FakeBaselines(),  # type: ignore[arg-type]
        FakeLaws(),  # type: ignore[arg-type]
        FakeRates(persona_rates(persona) if rates is None else rates),  # type: ignore[arg-type]
    )
    plans = CoachPlans(
        service,
        plan_repo,  # type: ignore[arg-type]
        scorer,
        CoachPlanWriter(stub),  # type: ignore[arg-type]
        FakeUsers(home_country),  # type: ignore[arg-type]
        FakeCorridors(),  # type: ignore[arg-type]
        FakeRates(persona_rates(persona)),  # type: ignore[arg-type]
        radar or FakeRadar(),  # type: ignore[arg-type]
    )
    return plans, service, session_repo, plan_repo, stub


async def persona_context(persona: Persona) -> Any:
    """Everything the plan is built from for a persona, and the `PlanContext` the writer takes:
    `(data, quote, ctx)`."""
    from datetime import UTC, datetime

    from app.services.coach.plan_facts import PlanContext
    from app.services.coach.plan_figures import compute_figures
    from app.services.coach.plan_inputs import plan_inputs, score_inputs_of
    from app.services.coach.plan_quote import cheapest_quote
    from app.services.coach.scoring import score_inputs

    profile = persona.expected_slots
    data = await persona_scorer(persona).load(profile)
    inputs = plan_inputs(profile, data)
    quote = await cheapest_quote(
        persona.corridor,  # type: ignore[arg-type]
        inputs.remittance,
        FakeCorridors(),  # type: ignore[arg-type]
        persona_rate_repo(persona),  # type: ignore[arg-type]
        FakeRadar(),  # type: ignore[arg-type]
        datetime(2026, 10, 9, 8, 0, tzinfo=UTC),
    )
    figures = compute_figures(inputs, persona.corridor, quote)  # type: ignore[arg-type]
    score = score_inputs(score_inputs_of(profile, data))
    ctx = PlanContext(
        inputs,
        figures,
        score,
        profile.bank_or_wallet or "none",
        profile.job_type or "other",
        profile.dependents,
        profile.departure_date,
    )
    return data, quote, ctx
