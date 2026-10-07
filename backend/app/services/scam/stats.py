from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol, get_args

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.schemas.scam import CorridorId
from app.schemas.scam_stats import AggregateScamStatsResponse

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
# A worker whose route is none of the six corridors (a Nepali worker in Singapore, say).
NO_CORRIDOR = "none"
BENIGN = "benign"
INPUT_TYPES = ("text", "screenshot")
# The week in progress and the one before it. Checks are deleted 90 days after they were made,
# so a week left to recompute for months would shrink: a closed week is written one last time
# in the run after it closes, then left alone.
WEEKS_RECOMPUTED = 2


class StatsRepository(Protocol):
    def checks_created_between(self, start: datetime, end: datetime) -> list[dict[str, Any]]: ...

    def write_weeks(
        self, corridors: dict[str, dict[str, Any]], week: str, now: datetime
    ) -> int: ...


@dataclass(frozen=True)
class IsoWeek:
    """An ISO 8601 week in UTC: Monday 00:00 up to the next Monday."""

    label: str  # "2026-W45"
    start: datetime
    end: datetime


def iso_week_of(moment: datetime) -> IsoWeek:
    year, week, _ = moment.astimezone(UTC).isocalendar()
    monday = date.fromisocalendar(year, week, 1)
    start = datetime.combine(monday, time.min, tzinfo=UTC)
    return IsoWeek(f"{year}-W{week:02d}", start, start + timedelta(days=7))


def weeks_to_compute(now: datetime) -> list[IsoWeek]:
    """The previous week and the current one, oldest first."""
    current = iso_week_of(now)
    weeks = [
        iso_week_of(current.start - timedelta(days=7 * back)) for back in range(1, WEEKS_RECOMPUTED)
    ]
    return [*reversed(weeks), current]


def corridor_keys() -> tuple[str, ...]:
    return (*get_args(CorridorId), NO_CORRIDOR)


def _empty(corridor: str, week: IsoWeek, now: datetime) -> dict[str, Any]:
    return {
        "corridor_id": corridor,
        "iso_week": week.label,
        "week_start": week.start,
        "week_end": week.end,
        "checks": 0,
        "scams": 0,
        "benign": 0,
        "by_type": {},
        "by_input": {name: 0 for name in INPUT_TYPES},
        "reported": 0,
        "computed_at": now,
        "schema_version": SCHEMA_VERSION,
    }


def tally(
    checks: Iterable[Mapping[str, Any]], week: IsoWeek, now: datetime
) -> tuple[dict[str, dict[str, Any]], int]:
    """Counts per corridor for one week, and how many checks were too damaged to count.

    Every corridor gets a document, with zeros when nothing was checked there, so a reader sees
    the whole grid. Only numbers and ids of the fixed lists come out: the input is a field-masked
    copy of the checks, and nothing the worker wrote is read, kept or returned.
    """
    known = set(corridor_keys())
    out = {corridor: _empty(corridor, week, now) for corridor in corridor_keys()}
    by_type: dict[str, Counter[str]] = {corridor: Counter() for corridor in out}
    skipped = 0
    for check in checks:
        verdict = check.get("verdict")
        if not isinstance(verdict, Mapping) or not isinstance(verdict.get("is_scam"), bool):
            skipped += 1
            continue
        corridor = check.get("corridor_id")
        key = corridor if corridor in known and corridor != NO_CORRIDOR else NO_CORRIDOR
        row = out[key]
        row["checks"] += 1
        if verdict["is_scam"]:
            row["scams"] += 1
            by_type[key][str(verdict.get("scam_type") or "other_scam")] += 1
        else:
            row["benign"] += 1
        input_type = check.get("input_type")
        if input_type in INPUT_TYPES:
            row["by_input"][input_type] += 1
        if check.get("reported_at") is not None:
            row["reported"] += 1
    for key, counts in by_type.items():
        out[key]["by_type"] = dict(sorted(counts.items()))
    return out, skipped


async def run_scam_stats(
    repo: StatsRepository, now: datetime
) -> tuple[AggregateScamStatsResponse, bool]:
    """Write the counts of the current and the previous ISO week; returns the answer and whether
    every week was written.

    Safe to run as often as wanted: each run reads the checks again and replaces the documents
    with what it counted, so nothing is added up across runs.
    """
    labels: list[str] = []
    counted = written = 0
    complete = True
    for week in weeks_to_compute(now):
        try:
            checks = await run_in_threadpool(repo.checks_created_between, week.start, week.end)
            documents, skipped = tally(checks, week, now)
            written += await run_in_threadpool(repo.write_weeks, documents, week.label, now)
        except GoogleAPICallError:
            # The other week is still worth writing; the scheduler retries the whole run, which
            # is harmless because every write replaces.
            logger.exception("scam_stats_week_failed week=%s", week.label)
            complete = False
            continue
        labels.append(week.label)
        counted += len(checks) - skipped
        if skipped:
            logger.warning("scam_stats_skipped_checks week=%s count=%d", week.label, skipped)
    logger.info("scam_stats weeks=%s checks=%d documents=%d", labels, counted, written)
    return (
        AggregateScamStatsResponse(
            weeks=labels, checks_counted=counted, documents_written=written, completed_at=now
        ),
        complete,
    )
