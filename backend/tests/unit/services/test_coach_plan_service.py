"""Making and finding the plan: idempotency, the lock, failures and the corridor (NF-FC-012)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.integrations.gemini import GeminiUnavailableError
from app.integrations.gemini.errors import GeminiResponseError
from app.schemas.coach_plan import slot_hash
from app.services.coach.plan_service import (
    PlanInProgressError,
    PlanNotFoundError,
    PlanNotReadyError,
)
from app.services.coach.scoring_inputs import ScoreUnavailableError
from app.services.coach.session_types import SessionNotActiveError
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import (
    UID,
    FakeRadar,
    WritingGemini,
    make_plans,
    reach_plan_stage,
)
from tests.fixtures.coach_sessions import NOW

pytestmark = pytest.mark.anyio

PERSONAS = {p.id: p for p in load_personas().personas}
MARICEL = PERSONAS["p01_sg_ph_maricel"]
LATER = NOW + timedelta(minutes=10)


async def ready(persona=MARICEL, **options):  # type: ignore[no-untyped-def]
    plans, service, session_repo, plan_repo, gemini = make_plans(persona, **options)
    session_id = await reach_plan_stage(service, persona)
    return plans, service, session_repo, plan_repo, gemini, session_id


async def test_a_new_plan_is_stored_in_english_and_completes_the_session() -> None:
    plans, service, session_repo, plan_repo, gemini, session_id = await ready()

    result = await plans.create(UID, session_id, LATER)

    plan_id = slot_hash(MARICEL.expected_slots)[:20]
    assert result.created and result.response.id == plan_id
    assert result.response.language == "en" and result.response.available_languages == ["en"]
    assert result.response.corridor_id == "SG-PH" and result.response.home_country == "PH"
    assert result.response.score.total == 22
    stored = plan_repo.get(UID, plan_id)
    assert stored is not None
    assert stored["session_id"] == session_id and stored["language_generated"] == "en"
    assert stored["prompt_versions"] == {"coach.plan": 1} and stored["models"]["plan"]
    assert stored["grounding"]["baselines"]["host_country"] == "SG"
    assert stored["grounding"]["fx"][0]["pair"] == "SGD_PHP"
    assert stored["grounding"]["provider_quote"]["slug"]
    assert stored["rates_as_of"] <= LATER
    session = (await service.get(UID, session_id, LATER)).model_dump()
    assert session["status"] == "completed"
    assert len(gemini.calls) == 1


async def test_asking_again_returns_the_same_plan_without_another_call() -> None:
    plans, _, _, _, gemini, session_id = await ready()
    first = await plans.create(UID, session_id, LATER)

    again = await plans.create(UID, session_id, LATER + timedelta(minutes=1))

    assert not again.created and again.response == first.response.model_copy(
        update={"session_id": again.response.session_id}
    )
    assert len(gemini.calls) == 1


async def test_a_plan_that_exists_for_the_answers_is_returned_and_the_session_completed() -> None:
    plans, service, session_repo, plan_repo, gemini, session_id = await ready()
    first = await plans.create(UID, session_id, LATER)
    # The session was left at `plan` (the write after the plan failed once): the plan is found.
    document = session_repo.docs[(UID, session_id)]
    document.update(status="active", plan_id=None)

    again = await plans.create(UID, session_id, LATER + timedelta(minutes=1))

    assert not again.created and again.response.id == first.response.id
    assert session_repo.docs[(UID, session_id)]["status"] == "completed"
    assert len(gemini.calls) == 1


async def test_answers_that_are_not_confirmed_are_not_ready() -> None:
    plans, service, _, _, gemini = make_plans(MARICEL)
    started = await service.start(UID, "en", restart=False, now=NOW)

    with pytest.raises(PlanNotReadyError):
        await plans.create(UID, started.session.id, LATER)
    assert gemini.calls == []


async def test_an_abandoned_session_cannot_make_a_plan() -> None:
    plans, _, session_repo, _, _, session_id = await ready()
    session_repo.docs[(UID, session_id)]["status"] = "abandoned"

    with pytest.raises(SessionNotActiveError):
        await plans.create(UID, session_id, LATER)


async def test_a_second_request_while_the_first_runs_is_refused() -> None:
    plans, _, session_repo, _, gemini, session_id = await ready()
    session_repo.docs[(UID, session_id)]["plan_lock"] = {"hash": "x", "started_at": LATER}

    with pytest.raises(PlanInProgressError):
        await plans.create(UID, session_id, LATER + timedelta(seconds=30))
    assert gemini.calls == []


async def test_a_lock_left_by_a_dead_request_does_not_block_forever() -> None:
    plans, _, session_repo, _, _, session_id = await ready()
    session_repo.docs[(UID, session_id)]["plan_lock"] = {"hash": "x", "started_at": LATER}

    result = await plans.create(UID, session_id, LATER + timedelta(minutes=5))

    assert result.created


async def test_a_failed_plan_stores_nothing_and_frees_the_lock() -> None:
    gemini = WritingGemini(GeminiUnavailableError("down"))
    plans, _, session_repo, plan_repo, _, session_id = await ready(gemini=gemini)

    with pytest.raises(GeminiUnavailableError):
        await plans.create(UID, session_id, LATER)

    assert plan_repo.plans == {}
    assert session_repo.docs[(UID, session_id)]["plan_lock"] is None
    assert session_repo.docs[(UID, session_id)]["status"] == "active"
    retry = await plans.create(UID, session_id, LATER + timedelta(seconds=5))  # the next try works
    assert retry.created


async def test_sentences_with_made_up_figures_twice_are_a_bad_response_and_nothing_is_stored() -> (
    None
):
    def invented(contents: str):  # type: ignore[no-untyped-def]
        from tests.fixtures.coach_plan_data import compliant_text

        return compliant_text(contents).model_copy(update={"summary": "You will earn 99,999 SGD."})

    gemini = WritingGemini(invented, invented)
    plans, _, _, plan_repo, _, session_id = await ready(gemini=gemini)

    with pytest.raises(GeminiResponseError):
        await plans.create(UID, session_id, LATER)

    assert plan_repo.plans == {} and len(gemini.calls) == 2


async def test_a_missing_rate_makes_the_score_and_so_the_plan_unavailable() -> None:
    plans, _, session_repo, plan_repo, gemini, session_id = await ready(rates={})

    with pytest.raises(ScoreUnavailableError):
        await plans.create(UID, session_id, LATER)

    assert gemini.calls == [] and plan_repo.plans == {}
    assert session_repo.docs[(UID, session_id)]["plan_lock"] is None


@pytest.mark.parametrize("home", [None, "NP", "BD", "ID"])
async def test_a_route_outside_the_six_corridors_has_no_provider_quote(home: str | None) -> None:
    plans, _, _, _, _, session_id = await ready(home=home)

    result = await plans.create(UID, session_id, LATER)

    remittance = result.response.plan.remittance
    assert result.response.corridor_id is None and remittance.corridor_id is None
    assert remittance.provider is None and len(remittance.schedule) == 3
    assert "no_provider_quote" in [w.id for w in result.response.plan.warnings]
    assert (result.response.home_country or None) == home


async def test_a_provider_the_radar_flagged_is_not_the_one_chosen() -> None:
    plans, _, _, _, _, session_id = await ready()
    best = (await plans.create(UID, session_id, LATER)).response.plan.remittance.provider
    assert best is not None

    flagged = FakeRadar([{"slug": best.slug, "report_count": 9}])
    plans2, _, _, _, _, session2 = await ready(radar=flagged)
    chosen = (await plans2.create(UID, session2, LATER)).response.plan.remittance.provider

    assert chosen is not None and chosen.slug != best.slug


async def test_a_plan_is_the_workers_own() -> None:
    plans, _, _, _, _, session_id = await ready()
    created = await plans.create(UID, session_id, LATER)

    assert (await plans.get(UID, created.response.id, LATER)).id == created.response.id
    with pytest.raises(PlanNotFoundError):
        await plans.get("someone-else", created.response.id, LATER)
    with pytest.raises(PlanNotFoundError):
        await plans.get(UID, "0" * 20, LATER)


async def test_a_plan_outlives_its_session() -> None:
    plans, _, _, _, _, session_id = await ready()
    created = await plans.create(UID, session_id, LATER)

    read = await plans.get(UID, created.response.id, LATER + timedelta(days=40))

    assert created.response.session_id == session_id and read.session_id is None
    assert read.plan == created.response.plan


async def test_each_persona_makes_a_plan_through_the_service() -> None:
    for persona in PERSONAS.values():
        plans, _, _, _, _, session_id = await ready(persona)

        result = await plans.create(UID, session_id, LATER)

        assert result.created and result.response.corridor_id == persona.corridor
        assert result.response.score.total == persona.expected_score.total
