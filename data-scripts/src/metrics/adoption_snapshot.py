"""The adoption numbers for the pitch, from what Firestore holds (NF-HR-015). Read-only.

Run from data-scripts/:  python -m src.metrics.adoption_snapshot [--json FILE] [--since YYYY-MM-DD]

The numbers are a function of the stored Coach sessions, plans and scam checks, so a second run
over the same data gives the same figures and only `generated_at` differs. That is what makes
this the saved query behind the pitch. Counts only: no uid, message, answer or amount is read
into the output (the fields asked of Firestore are listed in `COACH_FIELDS` and the others).

Breakdowns hide a cell under `MIN_CELL` (as the Partner API must, D-165): a corridor with two
checks describes two people. Totals are exact. Demo workers are left out unless asked for.

What the stored data cannot say: a check is kept 90 days and an interview 30, and a worker who
closes their account takes both away, so a figure is "what is stored now", not "ever".
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

from google.cloud.firestore import Client

from src.firestore_client import get_firestore_client

log = logging.getLogger(__name__)

MIN_CELL = 5
DEMO_UIDS = frozenset({"uid_priya_demo", "uid_rajesh_demo", "uid_miguel_demo"})

COACH_FIELDS = ["status", "stage", "language", "turn_count", "created_at", "completed_at"]
PLAN_FIELDS = ["score.band", "corridor_id", "checkins", "created_at"]
SCAM_FIELDS = [
    "verdict.is_scam",
    "verdict.scam_type",
    "verdict.risk_level",
    "corridor_id",
    "input_type",
    "reported_at",
    "check_count",
    "created_at",
]
MILESTONES = ("d30", "d60", "d90")


def _worker_of(path: str) -> str | None:
    """The uid in `users/{uid}/...`, or None for a document that is not under a worker."""
    parts = path.split("/")
    return parts[1] if len(parts) >= 4 and parts[0] == "users" else None


def _read(
    client: Client, group: str, fields: list[str], *, include_demo: bool, since: datetime | None
) -> list[tuple[str, dict[str, Any]]]:
    """`(uid, document)` for every stored document of a collection group, left out when it is a
    demo worker's, or created before `since`."""
    found: list[tuple[str, dict[str, Any]]] = []
    for snapshot in client.collection_group(group).select(fields).stream():
        uid = _worker_of(snapshot.reference.path)
        data = snapshot.to_dict() or {}
        if uid is None or (not include_demo and uid in DEMO_UIDS):
            continue
        created = data.get("created_at")
        if since is not None and isinstance(created, datetime) and created < since:
            continue
        found.append((uid, data))
    return found


def _get(data: dict[str, Any], path: str) -> Any:
    """A value at a dotted path, however the client returned it (nested, or as a flat key)."""
    if path in data:
        return data[path]
    node: Any = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def _cells(counter: Counter[str]) -> dict[str, int | str]:
    """A breakdown with every cell under `MIN_CELL` hidden, biggest first."""
    return {
        key: (n if n >= MIN_CELL else f"<{MIN_CELL}")
        for key, n in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    }


def coach_numbers(
    sessions: list[tuple[str, dict[str, Any]]], plans: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    status = Counter(str(data.get("status", "unknown")) for _, data in sessions)
    started, completed = len(sessions), status.get("completed", 0)
    finished = completed + status.get("abandoned", 0)
    workers_started = {uid for uid, _ in sessions}
    workers_done = {uid for uid, data in sessions if data.get("status") == "completed"}

    minutes = [
        (data["completed_at"] - data["created_at"]).total_seconds() / 60
        for _, data in sessions
        if data.get("status") == "completed"
        and isinstance(data.get("completed_at"), datetime)
        and isinstance(data.get("created_at"), datetime)
    ]
    turns = [
        int(data["turn_count"])
        for _, data in sessions
        if data.get("status") == "completed" and isinstance(data.get("turn_count"), int)
    ]
    answered: Counter[str] = Counter()
    for _, plan in plans:
        checkins = plan.get("checkins")
        if isinstance(checkins, dict):
            for milestone in MILESTONES:
                entry = checkins.get(milestone)
                if isinstance(entry, dict) and entry.get("answered_at") is not None:
                    answered[milestone] += 1
    return {
        "interviews_started": started,
        "interviews_completed": completed,
        "interviews_abandoned": status.get("abandoned", 0),
        "interviews_open": status.get("active", 0),
        "completion_rate": _rate(completed, started),
        "completion_rate_of_finished": _rate(completed, finished),
        "workers_started": len(workers_started),
        "workers_with_a_plan": len(workers_done),
        "worker_completion_rate": _rate(len(workers_done), len(workers_started)),
        "median_minutes_to_a_plan": round(statistics.median(minutes), 1) if minutes else None,
        "median_turns_to_a_plan": statistics.median(turns) if turns else None,
        "plans": len(plans),
        "plans_by_band": _cells(Counter(str(_get(p, "score.band")) for _, p in plans)),
        "plans_by_corridor": _cells(Counter(str(p.get("corridor_id", "none")) for _, p in plans)),
        "interviews_by_language": _cells(
            Counter(str(data.get("language", "unknown")) for _, data in sessions)
        ),
        "checkins_answered": {m: answered.get(m, 0) for m in MILESTONES},
    }


def scam_numbers(checks: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    total = len(checks)
    caught = [d for _, d in checks if _get(d, "verdict.is_scam") is True]
    high = [d for d in caught if _get(d, "verdict.risk_level") == "high"]
    reported = [d for _, d in checks if d.get("reported_at") is not None]
    # A repeat of a stored message raises `check_count` and is not a new document.
    times_asked = sum(int(d.get("check_count", 1) or 1) for _, d in checks)
    return {
        "messages_checked": total,
        "times_asked_including_repeats": times_asked,
        "workers_who_checked": len({uid for uid, _ in checks}),
        "scams_caught": len(caught),
        "scams_caught_high_risk": len(high),
        "share_that_were_scams": _rate(len(caught), total),
        "scams_reported_to_radar": len(reported),
        "caught_by_type": _cells(Counter(str(_get(d, "verdict.scam_type")) for d in caught)),
        "caught_by_corridor": _cells(Counter(str(d.get("corridor_id", "none")) for d in caught)),
        "checked_by_input": _cells(Counter(str(d.get("input_type", "unknown")) for _, d in checks)),
    }


def snapshot(
    client: Client, *, include_demo: bool = False, since: date | None = None
) -> dict[str, Any]:
    """Every figure, from three collection-group reads with a field mask."""
    start = datetime(since.year, since.month, since.day, tzinfo=UTC) if since else None
    sessions = _read(client, "coach_sessions", COACH_FIELDS, include_demo=include_demo, since=start)
    plans = _read(client, "coach_plans", PLAN_FIELDS, include_demo=include_demo, since=start)
    checks = _read(client, "scam_checks", SCAM_FIELDS, include_demo=include_demo, since=start)
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "since": since.isoformat() if since else None,
        "demo_workers_included": include_demo,
        "small_cells_hidden_under": MIN_CELL,
        "documents_read": {
            "coach_sessions": len(sessions),
            "coach_plans": len(plans),
            "scam_checks": len(checks),
        },
        "coach": coach_numbers(sessions, plans),
        "scam": scam_numbers(checks),
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def to_markdown(result: dict[str, Any]) -> str:
    """The headline numbers as a table for a slide or a README."""
    coach, scam = result["coach"], result["scam"]
    rows = [
        ("Coach interviews started", coach["interviews_started"]),
        ("Coach interviews that reached a 90-day plan", coach["interviews_completed"]),
        ("**Coach completion rate**", f"**{_pct(coach['completion_rate'])}**"),
        (
            "Of the interviews that ended (plan or given up)",
            _pct(coach["completion_rate_of_finished"]),
        ),
        (
            "Workers with a plan / workers who started",
            f"{coach['workers_with_a_plan']} / {coach['workers_started']}",
        ),
        ("Median minutes from start to plan", coach["median_minutes_to_a_plan"] or "n/a"),
        (
            "Check-ins answered (day 30 / 60 / 90)",
            " / ".join(str(coach["checkins_answered"][m]) for m in MILESTONES),
        ),
        ("Messages checked by the Scam Analyzer", scam["messages_checked"]),
        ("**Scams caught**", f"**{scam['scams_caught']}**"),
        ("Of which high risk", scam["scams_caught_high_risk"]),
        ("Warned other workers (reported to Radar)", scam["scams_reported_to_radar"]),
    ]
    lines = ["| Measure | Value |", "|---|---|"]
    lines += [f"| {name} | {value} |" for name, value in rows]
    window = f"since {result['since']}" if result["since"] else "all that is stored"
    lines.append("")
    lines.append(
        f"*{window}; generated {result['generated_at']}; cells under {MIN_CELL} are hidden.*"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Adoption numbers from Firestore (read-only).")
    parser.add_argument("--json", metavar="FILE", help="also write the full figures as JSON")
    parser.add_argument(
        "--since", type=date.fromisoformat, help="only documents created from this day (UTC)"
    )
    parser.add_argument("--include-demo", action="store_true", help="count the three demo workers")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = snapshot(get_firestore_client(), include_demo=args.include_demo, since=args.since)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        log.info("Wrote %s", args.json)
    print(to_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
