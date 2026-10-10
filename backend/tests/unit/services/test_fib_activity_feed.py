"""The unified activity feed (NF-HR-001)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.repositories.coach_session_repo import CoachPlanRepository
from app.repositories.fib_repo import EntryKind, FibRepository
from app.repositories.scam_check_repo import ScamCheckRepository
from app.services.feature_flag_service import FeatureFlagService
from app.services.fib.activity_feed import build_feed

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 15, 2, 0, tzinfo=UTC)


class FakeFib:
    def __init__(self, data: dict[str, list[tuple[str, dict[str, Any]]]]) -> None:
        self.data = data

    def list_entries(self, uid: str, kind: EntryKind) -> list[tuple[str, dict[str, Any]]]:
        return self.data.get(kind, [])


class FakePlans:
    def __init__(self, plans: list[tuple[str, dict[str, Any]]], fail: bool = False) -> None:
        self.plans = plans
        self.fail = fail
        self.asked = 0

    def activity(self, uid: str, limit: int) -> list[tuple[str, dict[str, Any]]]:
        self.asked += 1
        if self.fail:
            raise ServiceUnavailable("down")
        return self.plans


class FakeChecks:
    def __init__(self, checks: list[tuple[str, dict[str, Any]]], fail: bool = False) -> None:
        self.checks = checks
        self.fail = fail
        self.asked = 0
        self.since: datetime | None = None

    def activity_since(
        self, uid: str, since: datetime, limit: int
    ) -> list[tuple[str, dict[str, Any]]]:
        self.asked += 1
        self.since = since
        if self.fail:
            raise ServiceUnavailable("down")
        return self.checks


class FakeFlags:
    def __init__(self, on: set[str]) -> None:
        self.on = on

    async def is_enabled(self, flag: str, uid: str) -> bool:
        return flag in self.on


ENTRIES = {
    "income": [
        (
            "i1",
            {
                "entry_date": "2026-10-10",
                "amount": 650,
                "currency": "SGD",
                "category": "salary",
                "verified": True,
                "employer_name": "Mrs Tan Example",
                "notes": "paid in cash",
            },
        )
    ],
    "transfers": [
        (
            "t1",
            {
                "entry_date": "2026-10-11",
                "send_amount": 400,
                "send_currency": "SGD",
                "corridor_id": "SG-IN",
                "provider_name": "Wise",
            },
        )
    ],
    "bills": [
        (
            "b1",
            {
                "entry_date": "2026-10-09",
                "amount": 38.5,
                "currency": "SGD",
                "category": "phone_internet",
                "paid": True,
                "vendor": "Example Telecom",
            },
        )
    ],
    "savings": [
        (
            "s1",
            {"entry_date": "2026-10-08", "amount": 120, "currency": "SGD", "direction": "deposit"},
        )
    ],
}

PLANS = [
    (
        "p1",
        {
            "created_at": datetime(2026, 9, 20, 8, tzinfo=UTC),
            "corridor_id": "AU-IN",
            "departure_date": "2026-12-01",
            "checkins": {
                "d30": {
                    "answered_at": datetime(2026, 10, 12, 9, tzinfo=UTC),
                    "answers": {
                        "remittance": "on_track",
                        "savings": "behind",
                        "pay": "full_on_time",
                    },
                }
            },
        },
    )
]

CHECKS = [
    (
        "c1",
        {
            "last_checked_at": datetime(2026, 10, 13, 9, tzinfo=UTC),
            "verdict": {"is_scam": True, "risk_level": "high", "scam_type": "fake_job_offer"},
        },
    ),
    (
        "c2",
        {
            "last_checked_at": datetime(2026, 10, 1, 9, tzinfo=UTC),
            "verdict": {"is_scam": False, "risk_level": "low", "scam_type": None},
        },
    ),
]


async def _feed(
    *,
    days: int = 90,
    limit: int = 100,
    flags: set[str] | None = None,
    entries: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
    plans: FakePlans | None = None,
    checks: FakeChecks | None = None,
) -> Any:
    return await build_feed(
        "u1",
        days=days,
        limit=limit,
        now=NOW,
        fib=cast(FibRepository, FakeFib(ENTRIES if entries is None else entries)),
        plans=cast(CoachPlanRepository, plans or FakePlans(PLANS)),
        scam_checks=cast(ScamCheckRepository, checks or FakeChecks(CHECKS)),
        flags=cast(FeatureFlagService, FakeFlags({"coach", "scam"} if flags is None else flags)),
    )


async def test_the_money_log_the_coach_and_scam_checks_are_one_list_newest_first() -> None:
    feed = await _feed()

    assert [(item.kind, item.on.isoformat()) for item in feed.items] == [
        ("scam_check", "2026-10-13"),
        ("coach_checkin", "2026-10-12"),
        ("transfer", "2026-10-11"),
        ("income", "2026-10-10"),
        ("bill", "2026-10-09"),
        ("savings", "2026-10-08"),
        ("scam_check", "2026-10-01"),
        ("coach_plan", "2026-09-20"),
    ]
    assert feed.days == 90 and feed.truncated is False


async def test_items_carry_fixed_fields_and_never_a_note_name_or_text() -> None:
    feed = await _feed()

    dumped = json.dumps(feed.model_dump(mode="json"))
    for private in ("Mrs Tan", "paid in cash", "Example Telecom", "Wise", "fake job"):
        assert private not in dumped
    scam = next(i for i in feed.items if i.kind == "scam_check")
    assert scam.model_dump() == {
        "id": "c1",
        "on": scam.on,
        "kind": "scam_check",
        "is_scam": True,
        "risk_level": "high",
        "scam_type": "fake_job_offer",
    }


async def test_a_coach_check_in_names_its_milestone_and_the_three_choices() -> None:
    feed = await _feed()

    checkin = next(i for i in feed.items if i.kind == "coach_checkin")
    assert (checkin.milestone, checkin.remittance, checkin.savings, checkin.pay) == (
        "d30",
        "on_track",
        "behind",
        "full_on_time",
    )
    assert checkin.id == "p1"


async def test_coach_events_need_the_coach_flag_and_scam_checks_the_scam_flag() -> None:
    plans, checks = FakePlans(PLANS), FakeChecks(CHECKS)

    no_coach = await _feed(flags={"scam"}, plans=plans, checks=checks)
    no_scam = await _feed(flags={"coach"}, plans=FakePlans(PLANS), checks=FakeChecks(CHECKS))
    neither_plans, neither_checks = FakePlans(PLANS), FakeChecks(CHECKS)
    neither = await _feed(flags=set(), plans=neither_plans, checks=neither_checks)

    assert not any(i.kind.startswith("coach") for i in no_coach.items)
    assert any(i.kind == "scam_check" for i in no_coach.items)
    assert not any(i.kind == "scam_check" for i in no_scam.items)
    assert {i.kind for i in neither.items} == {"income", "transfer", "bill", "savings"}
    assert neither_plans.asked == 0 and neither_checks.asked == 0


async def test_the_feed_does_not_depend_on_the_reports_opt_in() -> None:
    # `signal_sharing` is not an input at all: it is about reports others read.
    feed = await _feed()

    assert any(i.kind == "coach_plan" for i in feed.items)
    assert any(i.kind == "scam_check" for i in feed.items)


async def test_days_bound_the_range() -> None:
    feed = await _feed(days=5)

    assert [i.on.isoformat() for i in feed.items] == [
        "2026-10-13",
        "2026-10-12",
        "2026-10-11",
        "2026-10-10",
    ]


async def test_limit_cuts_the_list_and_says_so() -> None:
    feed = await _feed(limit=3)

    assert len(feed.items) == 3
    assert feed.truncated is True
    assert feed.items[0].kind == "scam_check"


async def test_a_failed_coach_or_scam_read_leaves_the_rest() -> None:
    feed = await _feed(plans=FakePlans(PLANS, fail=True), checks=FakeChecks(CHECKS, fail=True))

    assert {i.kind for i in feed.items} == {"income", "transfer", "bill", "savings"}


async def test_an_entry_that_does_not_match_its_shape_is_left_out_not_fatal() -> None:
    entries = {
        "income": [
            ("bad", {"entry_date": "2026-10-10", "currency": "SGD"}),  # no amount
            ("worse", {"entry_date": "not a date", "amount": 1, "currency": "SGD"}),
            ENTRIES["income"][0],
        ]
    }

    feed = await _feed(entries=entries, flags=set())

    assert [i.id for i in feed.items] == ["i1"]


async def test_a_future_dated_or_old_entry_outside_the_range_is_not_listed() -> None:
    entries = {
        "income": [
            ("old", {"entry_date": "2026-01-01", "amount": 1, "currency": "SGD"}),
            ("new", {"entry_date": "2026-10-10", "amount": 1, "currency": "SGD"}),
        ]
    }

    feed = await _feed(entries=entries, flags=set(), days=30)

    assert [i.id for i in feed.items] == ["new"]


async def test_a_worker_with_nothing_gets_an_empty_list() -> None:
    feed = await _feed(entries={}, plans=FakePlans([]), checks=FakeChecks([]))

    assert feed.items == [] and feed.truncated is False


async def test_the_window_in_days_is_the_one_asked_of_the_scam_repository() -> None:
    checks = FakeChecks([])

    await _feed(days=30, checks=checks)

    assert checks.asked == 1
    assert checks.since == datetime(2026, 9, 15, tzinfo=UTC)
