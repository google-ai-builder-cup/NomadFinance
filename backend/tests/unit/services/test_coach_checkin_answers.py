"""NF-FC-022: storing a worker's answers to a day 30, 60 or 90 check-in, once."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from app.repositories.coach_session_repo import CoachPlanRepository, SessionContentionError
from app.schemas.coach_checkin import CheckinAnswerRequest, CheckinAnswers, Milestone
from app.services.coach.checkin_answers import CheckinNotDueError, answer_checkin
from app.services.coach.plan_service import PlanNotFoundError
from tests.fixtures.coach_checkins import DUE, PLAN_ID, FakePlans, at

pytestmark = pytest.mark.anyio

ANSWERS = CheckinAnswers(remittance="on_track", savings="behind", pay="full_on_time")
OTHER = CheckinAnswers(remittance="not_yet", savings="not_yet", pay="not_paid")


def repo(plans: FakePlans) -> CoachPlanRepository:
    return cast(CoachPlanRepository, plans)


@pytest.fixture
def plans() -> FakePlans:
    store = FakePlans()
    store.add()
    return store


async def test_the_first_answers_are_stored_beside_the_reminders_markers(
    plans: FakePlans,
) -> None:
    plans.mark_checkin("u1", PLAN_ID, "d30", DUE["d30"], at(DUE["d30"]))

    result = await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, at(DUE["d30"], 9))

    assert result.already_answered is False
    assert result.answers == ANSWERS and result.milestone == "d30" and result.plan_id == PLAN_ID
    stored = plans.marker()["d30"]
    assert stored["answers"] == ANSWERS.model_dump() and stored["answered_at"] == at(DUE["d30"], 9)
    # The reminder's own fields are still there: the write is by field path.
    assert stored["due_on"] == DUE["d30"] and stored["notified_at"] == at(DUE["d30"])


async def test_a_second_answer_changes_nothing_and_returns_the_first(plans: FakePlans) -> None:
    first = await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, at(DUE["d30"], 9))

    again = await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", OTHER, at(DUE["d30"], 20))

    assert again.already_answered is True
    assert again.answers == ANSWERS and again.answered_at == first.answered_at
    assert plans.marker()["d30"]["answers"] == ANSWERS.model_dump()


async def test_each_milestone_is_answered_on_its_own(plans: FakePlans) -> None:
    await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, at(DUE["d30"]))

    sixty = await answer_checkin(repo(plans), "u1", PLAN_ID, "d60", OTHER, at(DUE["d60"]))

    assert sixty.already_answered is False and sixty.answers == OTHER
    assert set(plans.marker()) == {"d30", "d60"}


@pytest.mark.parametrize("milestone", ["d30", "d60", "d90"])
async def test_the_day_itself_is_open_and_the_day_before_is_not(
    plans: FakePlans, milestone: Milestone
) -> None:
    due = at(DUE[milestone], 0)

    with pytest.raises(CheckinNotDueError):
        await answer_checkin(
            repo(plans), "u1", PLAN_ID, milestone, ANSWERS, due - timedelta(days=1)
        )
    assert plans.marker() == {}

    opened = await answer_checkin(repo(plans), "u1", PLAN_ID, milestone, ANSWERS, due)
    assert opened.already_answered is False


async def test_a_late_answer_is_accepted(plans: FakePlans) -> None:
    result = await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, at("2027-06-01"))

    assert result.already_answered is False


@pytest.mark.parametrize("departure", [None, "not-a-date"])
async def test_a_plan_without_a_usable_departure_date_has_no_check_in(
    departure: str | None,
) -> None:
    plans = FakePlans()
    plans.add(departure_date=departure)

    with pytest.raises(CheckinNotDueError):
        await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, datetime.now(UTC))


async def test_another_workers_plan_and_a_missing_plan_are_the_same_error(
    plans: FakePlans,
) -> None:
    for uid, plan_id in (("someone-else", PLAN_ID), ("u1", "0" * 20)):
        with pytest.raises(PlanNotFoundError):
            await answer_checkin(repo(plans), uid, plan_id, "d30", ANSWERS, at(DUE["d30"]))


async def test_contention_is_passed_on_for_the_route_to_answer_retry(plans: FakePlans) -> None:
    plans.contended = True

    with pytest.raises(SessionContentionError):
        await answer_checkin(repo(plans), "u1", PLAN_ID, "d30", ANSWERS, at(DUE["d30"]))


def test_only_the_listed_choices_and_the_three_questions_are_accepted() -> None:
    good = {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"}
    assert CheckinAnswerRequest.model_validate({"answers": good})
    for bad in (
        {**good, "pay": "on_track"},  # a choice of another question
        {**good, "savings": "sometimes"},
        {**good, "note": "free text"},  # nothing a worker types is stored
        {"remittance": "on_track", "savings": "behind"},  # all three are required
    ):
        with pytest.raises(ValidationError):
            CheckinAnswerRequest.model_validate({"answers": bad})
