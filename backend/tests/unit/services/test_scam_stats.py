from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.api_core.exceptions import ServiceUnavailable

from app.services.scam.stats import (
    SCHEMA_VERSION,
    corridor_keys,
    iso_week_of,
    run_scam_stats,
    tally,
    weeks_to_compute,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)  # a Wednesday, 2026-W45
WEEK = iso_week_of(NOW)


def _check(
    *,
    scam: bool = True,
    kind: str | None = "illegal_recruitment_fee",
    corridor: str | None = "SG-IN",
    input_type: str = "text",
    reported: bool = False,
) -> dict[str, Any]:
    check: dict[str, Any] = {
        "verdict": {"is_scam": scam, "scam_type": kind if scam else None},
        "input_type": input_type,
    }
    if corridor is not None:
        check["corridor_id"] = corridor
    if reported:
        check["reported_at"] = NOW
    return check


# --- the ISO week -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "label", "monday"),
    [
        (datetime(2026, 11, 4, 9, 30, tzinfo=UTC), "2026-W45", datetime(2026, 11, 2, tzinfo=UTC)),
        (datetime(2026, 11, 2, 0, 0, tzinfo=UTC), "2026-W45", datetime(2026, 11, 2, tzinfo=UTC)),
        (datetime(2026, 11, 1, 23, 59, tzinfo=UTC), "2026-W44", datetime(2026, 10, 26, tzinfo=UTC)),
        # The year's first days can belong to the last week of the year before, and the other
        # way round: the calendar year is not the ISO year.
        (datetime(2024, 12, 30, tzinfo=UTC), "2025-W01", datetime(2024, 12, 30, tzinfo=UTC)),
        (datetime(2027, 1, 1, tzinfo=UTC), "2026-W53", datetime(2026, 12, 28, tzinfo=UTC)),
    ],
)
def test_the_iso_week_runs_monday_to_monday_in_utc(
    moment: datetime, label: str, monday: datetime
) -> None:
    week = iso_week_of(moment)

    assert (week.label, week.start) == (label, monday)
    assert week.end == monday + timedelta(days=7)


def test_a_moment_in_another_time_zone_is_placed_by_its_utc_time() -> None:
    from datetime import timezone

    late_sunday_utc = datetime(2026, 11, 1, 23, 30, tzinfo=UTC)
    in_india = late_sunday_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))  # Monday

    assert iso_week_of(in_india).label == "2026-W44"


def test_the_weeks_computed_are_the_previous_one_then_the_current_one() -> None:
    assert [w.label for w in weeks_to_compute(NOW)] == ["2026-W44", "2026-W45"]
    assert [w.label for w in weeks_to_compute(datetime(2027, 1, 5, tzinfo=UTC))] == [
        "2026-W53",
        "2027-W01",
    ]


# --- the counts -------------------------------------------------------------------------------


def test_every_corridor_gets_a_document_even_with_nothing_checked() -> None:
    documents, skipped = tally([], WEEK, NOW)

    assert tuple(documents) == corridor_keys() == (
        "SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH", "none",
    )  # fmt: skip
    assert skipped == 0
    for corridor, document in documents.items():
        assert document["checks"] == document["scams"] == document["benign"] == 0
        assert document["corridor_id"] == corridor and document["iso_week"] == "2026-W45"


def test_checks_are_counted_by_corridor_type_input_and_report() -> None:
    checks = [
        _check(),
        _check(kind="loan_app_trap", input_type="screenshot", reported=True),
        _check(kind="loan_app_trap"),
        _check(scam=False),
        _check(corridor="AU-PH", kind="lottery"),
        _check(corridor=None, scam=False),
    ]

    documents, _ = tally(checks, WEEK, NOW)

    sg_in = documents["SG-IN"]
    assert (sg_in["checks"], sg_in["scams"], sg_in["benign"]) == (4, 3, 1)
    assert sg_in["by_type"] == {"illegal_recruitment_fee": 1, "loan_app_trap": 2}
    assert sg_in["by_input"] == {"text": 3, "screenshot": 1}
    assert sg_in["reported"] == 1
    assert documents["AU-PH"]["by_type"] == {"lottery": 1}
    assert (documents["none"]["checks"], documents["none"]["benign"]) == (1, 1)


def test_a_route_outside_the_six_counts_as_none() -> None:
    documents, _ = tally([_check(corridor="KR-NP"), _check(corridor="none")], WEEK, NOW)

    assert documents["none"]["checks"] == 2
    assert sum(d["checks"] for d in documents.values()) == 2


def test_a_scam_without_a_type_counts_as_other_scam() -> None:
    documents, _ = tally([_check(kind=None)], WEEK, NOW)

    assert documents["SG-IN"]["by_type"] == {"other_scam": 1}


def test_a_damaged_check_is_skipped_and_reported_not_guessed() -> None:
    damaged: list[dict[str, Any]] = [{}, {"verdict": None}, {"verdict": {"is_scam": "yes"}}]

    documents, skipped = tally([*damaged, _check()], WEEK, NOW)

    assert skipped == 3
    assert sum(d["checks"] for d in documents.values()) == 1


def test_a_document_holds_counts_and_labels_only_never_what_a_worker_wrote() -> None:
    # What the repository reads is already a field-masked copy, but if anything else ever came
    # with it (a message, a link, an explainer), it must still not reach the document.
    leaky = _check() | {
        "redacted_text": "Pay 800 SGD to [ACCOUNT]",
        "indicators": [{"kind": "url", "value": "sg-careers-visa.example"}],
        "explainer": {"scammer_wants": "your money"},
        "uid": "worker-1",
    }

    documents, _ = tally([leaky], WEEK, NOW)

    allowed_strings = {
        *corridor_keys(),
        "2026-W45",
        "illegal_recruitment_fee",
        "text",
        "screenshot",
    }
    for document in documents.values():
        assert set(document) == {
            "corridor_id", "iso_week", "week_start", "week_end", "checks", "scams", "benign",
            "by_type", "by_input", "reported", "computed_at", "schema_version",
        }  # fmt: skip
        assert document["schema_version"] == SCHEMA_VERSION
        strings = _strings(document)
        assert strings <= allowed_strings, strings - allowed_strings


def _strings(document: dict[str, Any]) -> set[str]:
    """Every string a document holds as a value, and the names inside its two count maps."""
    found = {v for v in document.values() if isinstance(v, str)}
    return found | set(document["by_type"]) | set(document["by_input"])


# --- the run ----------------------------------------------------------------------------------


class FakeRepo:
    def __init__(self, checks: list[dict[str, Any]] | None = None, fail_week: str | None = None):
        self.checks = checks or []
        self.fail_week = fail_week
        self.asked: list[tuple[datetime, datetime]] = []
        self.written: dict[tuple[str, str], dict[str, Any]] = {}

    def checks_created_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        self.asked.append((start, end))
        if self.fail_week and iso_week_of(start).label == self.fail_week:
            raise ServiceUnavailable("read failed")
        return self.checks

    def write_weeks(self, corridors: dict[str, dict[str, Any]], week: str, now: datetime) -> int:
        for corridor, document in corridors.items():
            self.written[(corridor, week)] = document
        return len(corridors)


async def test_a_run_reads_each_week_by_its_own_bounds_and_writes_every_corridor() -> None:
    repo = FakeRepo([_check()])

    result, complete = await run_scam_stats(repo, NOW)

    assert complete and result.weeks == ["2026-W44", "2026-W45"]
    assert [(s.day, e.day) for s, e in repo.asked] == [(26, 2), (2, 9)]
    assert result.documents_written == 14 and result.checks_counted == 2
    assert {week for _, week in repo.written} == {"2026-W44", "2026-W45"}


async def test_running_again_gives_exactly_the_same_documents() -> None:
    repo = FakeRepo([_check(), _check(scam=False), _check(corridor="MY-ID", kind="lottery")])

    await run_scam_stats(repo, NOW)
    first = {key: dict(value) for key, value in repo.written.items()}
    await run_scam_stats(repo, NOW)

    assert repo.written == first


async def test_a_later_run_replaces_the_counts_it_does_not_add_to_them() -> None:
    repo = FakeRepo([_check(), _check()])
    await run_scam_stats(repo, NOW)

    repo.checks = [_check()]  # one check has gone (the worker closed the account)
    await run_scam_stats(repo, NOW + timedelta(hours=1))

    assert repo.written[("SG-IN", "2026-W45")]["checks"] == 1


async def test_a_week_that_cannot_be_read_does_not_stop_the_other_and_asks_for_a_retry() -> None:
    repo = FakeRepo([_check()], fail_week="2026-W44")

    result, complete = await run_scam_stats(repo, NOW)

    assert not complete
    assert result.weeks == ["2026-W45"]
    assert ("SG-IN", "2026-W45") in repo.written and ("SG-IN", "2026-W44") not in repo.written
