"""NF-FC-016: who gets a day 30, 60 or 90 reminder, exactly once, and in what words."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import get_args

import pytest

from app.schemas.coach_checkin import SendCheckinsResponse
from app.schemas.contract import ReportLanguage
from app.services.coach import checkin_job
from app.services.coach.checkin_job import CATCH_UP_DAYS, send_checkins, window_for
from app.services.coach.checkin_texts import BODY, TITLE, checkin_text, reminder_language
from tests.fixtures.coach_checkins import (
    DEPARTURE,
    DUE,
    NEWER_PLAN_ID,
    PLAN_ID,
    FakeFlags,
    FakePlans,
    FakeUsers,
    Pushes,
    as_repos,
    at,
    profile,
)

pytestmark = pytest.mark.anyio

DEPARTED = date.fromisoformat(DEPARTURE)


def day(after_departure: int) -> str:
    return (DEPARTED + timedelta(days=after_departure)).isoformat()


class World:
    """One worker, `u1`, with a plan, a profile and the coach flag on."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.plans = FakePlans()
        self.users = FakeUsers()
        self.flags = FakeFlags()
        self.pushes = Pushes()
        self.plans.add()
        self.users.profiles["u1"] = profile()
        monkeypatch.setattr(checkin_job, "send_push", self.pushes)

    async def run(self, after_departure: int) -> tuple[SendCheckinsResponse, bool]:
        return await send_checkins(
            *as_repos(self.plans, self.users, self.flags), at(day(after_departure))
        )

    def notified_milestones(self) -> list[str]:
        return sorted(n["source"]["milestone"] for n in self.users.notifications.values())


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> World:
    return World(monkeypatch)


# --- the dates ---------------------------------------------------------------------------


def test_the_window_is_the_day_and_the_catch_up_days_before_it() -> None:
    assert CATCH_UP_DAYS == 3
    assert window_for(date(2026, 12, 31), 30) == ("2026-11-28", "2026-12-01")
    assert window_for(date(2027, 3, 1), 90) == ("2026-11-28", "2026-12-01")


def test_the_windows_of_two_milestones_never_overlap() -> None:
    spans = sorted(window_for(date(2027, 6, 15), days) for days in (30, 60, 90))
    for (_, previous_last), (next_first, _) in zip(spans, spans[1:], strict=False):
        assert previous_last < next_first


# --- one reminder per milestone ----------------------------------------------------------


async def test_a_plan_on_its_day_30_gets_a_notification_a_push_and_a_marker(world: World) -> None:
    result, complete = await world.run(30)

    assert complete
    assert (result.plans_found, result.notified, result.already_sent, result.failed) == (1, 1, 0, 0)
    (((uid, notification_id), notification),) = world.users.notifications.items()
    assert (uid, notification_id) == ("u1", f"coach_checkin_{PLAN_ID}_d30")
    assert notification == {
        "type": "coach_checkin",
        "title": "दिन 30 की जाँच",
        "body": BODY["hi"].format(days=30),
        "language": "hi",
        "deep_link": f"/coach/checkin/{PLAN_ID}?m=30",
        "source": {
            "kind": "coach_checkin",
            "path": f"users/u1/coach_plans/{PLAN_ID}",
            "milestone": "d30",
        },
        "read": False,
        "created_at": at(day(30)),
        "schema_version": 1,
    }
    assert world.pushes.sent == [
        (
            ["token-1"],
            "दिन 30 की जाँच",
            BODY["hi"].format(days=30),
            f"/coach/checkin/{PLAN_ID}?m=30",
        )
    ]
    assert world.plans.marker()["d30"] == {"due_on": DUE["d30"], "notified_at": at(day(30))}


@pytest.mark.parametrize("after_departure", [-5, 0, 29])
async def test_nothing_goes_out_before_day_30(world: World, after_departure: int) -> None:
    result, complete = await world.run(after_departure)

    assert complete and result.plans_found == 0
    assert world.users.notifications == {} and world.pushes.sent == []


async def test_the_whole_life_of_a_plan_sends_three_reminders_and_no_more(world: World) -> None:
    """The time-travel test, with in-memory stores: the job runs every day for 110 days."""
    sent_on: list[int] = []
    for after_departure in range(-3, 108):
        result, complete = await world.run(after_departure)
        assert complete
        sent_on += [after_departure] * result.notified

    assert sent_on == [30, 60, 90]
    assert world.notified_milestones() == ["d30", "d60", "d90"]
    assert len(world.pushes.sent) == 3
    assert {m: world.plans.marker()[m]["due_on"] for m in ("d30", "d60", "d90")} == DUE


async def test_running_the_job_twice_on_one_day_sends_once(world: World) -> None:
    first, _ = await world.run(60)
    second, _ = await world.run(60)

    assert (first.notified, second.notified, second.already_sent) == (1, 0, 1)
    assert len(world.users.notifications) == 1 and len(world.pushes.sent) == 1


async def test_two_runs_at_the_same_moment_push_once(world: World) -> None:
    results = await asyncio.gather(world.run(90), world.run(90))

    assert sum(result.notified for result, _ in results) == 1
    assert len(world.users.notifications) == 1 and len(world.pushes.sent) == 1


async def test_a_run_that_missed_the_day_still_sends_within_the_catch_up_days(world: World) -> None:
    result, _ = await world.run(30 + CATCH_UP_DAYS)

    assert result.notified == 1
    # The marker says the milestone's own day, not the day the reminder went out.
    assert world.plans.marker()["d30"]["due_on"] == DUE["d30"]


async def test_a_reminder_missed_for_longer_than_the_catch_up_is_not_sent(world: World) -> None:
    result, _ = await world.run(30 + CATCH_UP_DAYS + 1)

    assert result.plans_found == 0 and world.users.notifications == {}


async def test_a_plan_with_no_departure_date_gets_no_reminder(world: World) -> None:
    world.plans.plans.clear()
    world.plans.add(departure_date=None)

    for after_departure in (30, 60, 90):
        result, _ = await world.run(after_departure)
        assert result.plans_found == 0

    assert world.users.notifications == {}


async def test_a_departure_date_that_is_not_a_date_is_skipped_and_counted(world: World) -> None:
    world.plans.plans.clear()
    world.plans.add(departure_date="2026-12-00")
    result, complete = await send_checkins(
        *as_repos(world.plans, world.users, world.flags), at("2027-01-01")
    )

    assert complete and result.plans_found == 1 and result.skipped == 1 and result.notified == 0


# --- who is left out ---------------------------------------------------------------------


async def test_a_worker_without_the_coach_flag_gets_nothing_and_no_marker(world: World) -> None:
    world.flags.on = set()

    result, complete = await world.run(30)

    assert complete and (result.notified, result.skipped) == (0, 1)
    assert world.users.notifications == {} and world.plans.marker() == {}
    # The flag turned on two days later: still inside the catch-up days, so the reminder goes.
    world.flags.on = {"u1"}
    assert (await world.run(32))[0].notified == 1


@pytest.mark.parametrize(
    ("prefs", "expected"),
    [
        (None, 1),
        ({}, 1),
        ({"radar_alerts": False}, 1),
        ({"reminders": True}, 1),
        ({"reminders": False}, 0),
        ("not a map", 1),
    ],
)
async def test_reminders_follow_the_workers_reminder_preference(
    world: World, prefs: object, expected: int
) -> None:
    world.users.profiles["u1"] = profile(notification_prefs=prefs)

    result, _ = await world.run(30)

    assert result.notified == expected
    assert (result.skipped == 1) == (expected == 0)
    assert len(world.pushes.sent) == expected


async def test_only_the_workers_newest_plan_counts(world: World) -> None:
    """Changing the date makes a second plan and the first one stays in storage."""
    world.plans.add(plan_id=NEWER_PLAN_ID, departure_date=day(20), created_at=at("2026-11-20"))

    old, _ = await world.run(30)  # the first plan's day 30; the newer one leaves in 20 days
    assert (old.plans_found, old.notified, old.skipped) == (1, 0, 1)

    newer, _ = await world.run(20 + 30)
    assert newer.notified == 1
    assert [n["source"]["path"] for n in world.users.notifications.values()] == [
        f"users/u1/coach_plans/{NEWER_PLAN_ID}"
    ]


async def test_a_second_plan_with_the_same_date_does_not_double_the_reminder(world: World) -> None:
    world.plans.add(plan_id=NEWER_PLAN_ID, created_at=at("2026-11-20"))

    result, _ = await world.run(30)

    assert (result.plans_found, result.notified, result.skipped) == (2, 1, 1)


async def test_two_workers_each_get_their_own_reminder(world: World) -> None:
    world.plans.add(uid="u2", plan_id=NEWER_PLAN_ID)
    world.users.profiles["u2"] = profile(preferred_language="id", fcm_tokens=["token-2"])
    world.flags.on = {"u1", "u2"}

    result, _ = await world.run(30)

    assert result.notified == 2
    assert sorted(tokens[0] for tokens, *_ in world.pushes.sent) == ["token-1", "token-2"]
    languages = {uid: n["language"] for (uid, _), n in world.users.notifications.items()}
    assert languages == {"u1": "hi", "u2": "id"}


# --- the push is the extra ---------------------------------------------------------------


@pytest.mark.parametrize("tokens", [[], None, "x", [{"a": 1}, "", 7]])
async def test_a_worker_with_no_usable_token_still_gets_the_notification(
    world: World, tokens: object
) -> None:
    world.users.profiles["u1"] = profile(fcm_tokens=tokens)

    result, _ = await world.run(30)

    assert result.notified == 1 and world.pushes.sent == []
    assert world.plans.marker()["d30"]["notified_at"] is not None


async def test_a_failing_push_does_not_undo_the_notification_or_the_marker(world: World) -> None:
    world.pushes.error = ValueError("rejected")

    result, complete = await world.run(30)

    assert complete and result.notified == 1 and result.failed == 0
    assert len(world.users.notifications) == 1
    assert "d30" in world.plans.marker()


async def test_a_token_that_fcm_reports_gone_is_removed(world: World) -> None:
    world.users.profiles["u1"] = profile(fcm_tokens=["good", "gone"])
    world.pushes.invalid = ["gone"]

    await world.run(30)

    assert world.users.removed_tokens == [("u1", "gone")]


async def test_a_failed_token_cleanup_does_not_fail_the_reminder(world: World) -> None:
    world.users.profiles["u1"] = profile(fcm_tokens=["gone"])
    world.pushes.invalid = ["gone"]
    world.users.fail_cleanup = True

    result, complete = await world.run(30)

    assert complete and result.notified == 1 and result.failed == 0
    assert "d30" in world.plans.marker()


# --- a failure is for the retry ----------------------------------------------------------


async def test_a_failed_marker_is_retried_without_a_second_push(world: World) -> None:
    world.plans.fail_mark = True
    first, complete = await world.run(30)
    assert not complete and first.failed == 1 and first.notified == 0
    assert len(world.pushes.sent) == 1 and len(world.users.notifications) == 1

    world.plans.fail_mark = False
    second, complete = await world.run(30)

    assert complete and (second.notified, second.already_sent, second.failed) == (0, 1, 0)
    assert len(world.pushes.sent) == 1 and len(world.users.notifications) == 1
    assert world.plans.marker()["d30"]["notified_at"] is not None


async def test_a_failed_query_leaves_the_other_milestones_to_run(world: World) -> None:
    today = date.fromisoformat(day(60))
    world.plans.fail_query_for = {window_for(today, 30)[0]}  # the day 30 query fails

    result, complete = await world.run(60)

    # The failed query counts as failed; day 60 was still sent.
    assert not complete and (result.failed, result.notified) == (1, 1)


# --- what the worker reads ---------------------------------------------------------------


def test_every_app_language_has_a_title_and_a_body() -> None:
    languages = set(get_args(ReportLanguage))
    assert set(TITLE) == languages and set(BODY) == languages


@pytest.mark.parametrize("language", get_args(ReportLanguage))
@pytest.mark.parametrize("days", [30, 60, 90])
def test_a_reminder_names_the_day_in_plain_digits_and_is_short(language: str, days: int) -> None:
    title, body = checkin_text(language, days)

    for text in (title, body):
        assert str(days) in text and "{" not in text and "}" not in text
        assert not any(c.isdigit() and not c.isascii() for c in text)
    assert len(title) <= 40 and len(body) <= 150
    assert "3" in body  # three questions, as the tracker says


@pytest.mark.parametrize(
    ("language", "low", "high"),
    [("hi", "ऀ", "ॿ"), ("ne", "ऀ", "ॿ"), ("bn", "ঀ", "৿")],
)
def test_the_indic_languages_are_written_in_their_own_script(
    language: str, low: str, high: str
) -> None:
    title, body = checkin_text(language, 30)

    for text in (title, body):
        assert any(low <= c <= high for c in text)


@pytest.mark.parametrize("stored", [None, "", "xx", 7, ["hi"], "HI"])
def test_a_missing_or_odd_language_reads_as_english(stored: object) -> None:
    assert reminder_language(stored) == "en"
    assert checkin_text(reminder_language(stored), 60)[0] == "Day 60 check-in"
