"""The plan's targets as goals of the Financial Identity profile (NF-FC-015)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound, ServiceUnavailable

from app.integrations.gemini import GeminiClient
from app.repositories.fib_repo import FibRepository
from app.repositories.rate_repo import RateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.coach_plan import CoachPlanResponse
from app.services.coach.plan_goals import goals_for, newest_plan_goals
from app.services.fib.profile_builder import recompute_profile
from tests.fixtures.coach_mocks import MOCKS
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import UID, make_plans, reach_plan_stage
from tests.fixtures.coach_sessions import NOW, FakePlanRepo
from tests.unit.services.test_fib_profile_builder import (
    FakeFib,
    FakeGemini,
    FakeRates,
    FakeUsers,
    _priya,
)

pytestmark = pytest.mark.anyio

PERSONAS = load_personas().personas
LATER = NOW + timedelta(minutes=10)


def mock_plan() -> CoachPlanResponse:
    import json

    body = json.loads((MOCKS / "plan-01-created.json").read_text(encoding="utf-8"))["body"]
    return CoachPlanResponse.model_validate(body)


def test_the_goals_are_the_plans_own_targets() -> None:
    goals = goals_for("abc", mock_plan().plan, LATER)

    assert goals == {
        "plan_id": "abc",
        "savings_rate_target_pct": 9.5,  # saving 400 of an income of 4,200
        "remittance": {"amount": 900.0, "currency": "AUD", "cadence": "monthly"},
        "emergency_fund_target": {"amount": 6465.0, "currency": "AUD"},
        "set_at": LATER,
    }


def test_a_plan_with_no_remittance_or_no_saving_gives_zero_goals_not_errors() -> None:
    plan = mock_plan().plan.model_copy(deep=True)
    plan.emergency_fund.monthly_saving.amount = 0.0
    plan.remittance.monthly_amount.amount = 0.0

    goals = goals_for("abc", plan, LATER)

    assert goals["savings_rate_target_pct"] == 0.0 and goals["remittance"]["amount"] == 0.0


def test_the_newest_plan_gives_the_goals_and_no_plan_gives_none() -> None:
    plans = FakePlanRepo()
    source = newest_plan_goals(plans)  # type: ignore[arg-type]
    assert source("u1") is None

    body = mock_plan()
    plans.add("u1", "old", {"plan": body.plan.model_dump(mode="json"), "created_at": NOW})
    plans.add("u1", "new", {"plan": body.plan.model_dump(mode="json"), "created_at": LATER})
    plans.add("u1", "broken", {"created_at": LATER + timedelta(days=1)})

    found = source("u1")
    assert found is None  # the newest document has no plan: nothing is guessed
    plans.plans["u1"].pop()
    found = source("u1")
    assert found is not None and found["plan_id"] == "new" and found["set_at"] == LATER


# --- stored on the profile, and kept across a recompute ---------------------------------------


def _profile_document(client: MagicMock) -> MagicMock:
    users = client.collection.return_value
    return users.document.return_value.collection.return_value.document.return_value  # type: ignore[no-any-return]


def test_goals_are_written_into_the_existing_profile() -> None:
    client = MagicMock()

    assert FibRepository(client).set_goals("u1", {"plan_id": "p"}) is True
    _profile_document(client).update.assert_called_once_with({"goals": {"plan_id": "p"}})


def test_with_no_profile_yet_the_goals_wait_for_the_recompute() -> None:
    client = MagicMock()
    _profile_document(client).update.side_effect = NotFound("no profile")

    assert FibRepository(client).set_goals("u1", {"plan_id": "p"}) is False


def test_a_recompute_keeps_the_goals_like_the_pdf_export() -> None:
    client = MagicMock()
    document = _profile_document(client)
    document.get.return_value = MagicMock(exists=True)
    document.get.return_value.to_dict.return_value = {
        "overall_score": 50,
        "goals": {"plan_id": "p"},
        "latest_export": {"storage_path": "exports/u1/report.pdf"},
    }

    FibRepository(client).save_profile("u1", {"overall_score": 80})

    document.set.assert_called_once_with(
        {
            "overall_score": 80,
            "goals": {"plan_id": "p"},
            "latest_export": {"storage_path": "exports/u1/report.pdf"},
            "schema_version": 1,
        }
    )


async def _recompute(goals_source: Any = None) -> dict[str, Any]:
    fib = FakeFib({"u1": _priya()})
    await recompute_profile(
        "u1",
        cast(GeminiClient, FakeGemini()),
        cast(FibRepository, fib),
        cast(UserRepository, FakeUsers({"u1": {"home_country": "IN"}})),
        cast(RateRepository, FakeRates()),
        datetime(2026, 10, 15, tzinfo=UTC),
        goals_source,
    )
    return fib.saved["u1"]


async def test_a_profile_built_after_the_plan_takes_the_goals_from_the_newest_plan() -> None:
    goals = {"plan_id": "p", "savings_rate_target_pct": 9.5}

    profile = await _recompute(lambda uid: goals)

    assert profile["goals"] == goals


async def test_a_profile_with_no_plan_has_no_goals() -> None:
    assert "goals" not in await _recompute(lambda uid: None)
    assert "goals" not in await _recompute()


# --- written when the plan is made ------------------------------------------------------------


class FakeFibGoals:
    def __init__(self, *, has_profile: bool = True, fails: bool = False) -> None:
        self.has_profile = has_profile
        self.fails = fails
        self.written: list[tuple[str, dict[str, Any]]] = []

    def set_goals(self, uid: str, goals: dict[str, Any]) -> bool:
        if self.fails:
            raise ServiceUnavailable("down")
        self.written.append((uid, goals))
        return self.has_profile


async def made(fib: FakeFibGoals | None) -> tuple[Any, Any, Any]:
    persona = PERSONAS[0]
    plans, service, _, _, _ = make_plans(persona)
    if fib is not None:
        plans._fib = fib  # noqa: SLF001
    session_id = await reach_plan_stage(service, persona)
    return plans, session_id, persona


async def test_making_a_plan_writes_its_goals_to_the_workers_profile() -> None:
    fib = FakeFibGoals()
    plans, session_id, _ = await made(fib)

    result = await plans.create(UID, session_id, "en", LATER)

    uid, goals = fib.written[0]
    plan = result.response.plan
    assert uid == UID and goals["plan_id"] == result.response.id and goals["set_at"] == LATER
    assert goals["emergency_fund_target"]["amount"] == plan.emergency_fund.target.amount
    assert goals["remittance"]["amount"] == plan.remittance.monthly_amount.amount
    assert goals["savings_rate_target_pct"] == round(
        plan.emergency_fund.monthly_saving.amount / plan.monthly_budget.income.amount * 100, 1
    )


async def test_asking_again_does_not_write_the_goals_again() -> None:
    fib = FakeFibGoals()
    plans, session_id, _ = await made(fib)
    await plans.create(UID, session_id, "en", LATER)

    await plans.create(UID, session_id, "en", LATER + timedelta(minutes=1))
    await plans.create(UID, session_id, "hi", LATER + timedelta(minutes=2))

    assert len(fib.written) == 1


async def test_a_failed_write_never_fails_the_plan() -> None:
    plans, session_id, _ = await made(FakeFibGoals(fails=True))

    result = await plans.create(UID, session_id, "en", LATER)

    assert result.created


async def test_without_a_profile_the_plan_is_still_made() -> None:
    plans, session_id, _ = await made(FakeFibGoals(has_profile=False))

    assert (await plans.create(UID, session_id, "en", LATER)).created


async def test_every_persona_gets_goals_that_match_their_plan() -> None:
    for persona in PERSONAS:
        fib = FakeFibGoals()
        plans, service, *_ = make_plans(persona)
        plans._fib = fib  # noqa: SLF001
        session_id = await reach_plan_stage(service, persona)

        result = await plans.create(UID, session_id, "en", LATER)

        goals = fib.written[0][1]
        assert goals["remittance"]["currency"] == result.response.reporting_currency, persona.id
        assert 0 <= goals["savings_rate_target_pct"] <= 100, persona.id
