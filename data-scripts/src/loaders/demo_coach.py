"""Load the demo workers' completed Coach session and plan into Firestore (NF-HR-003).

Run from data-scripts/:  python -m src.loaders.demo_coach
For each file in data/seed/coach/ it writes, in one atomic batch:

    users/{uid}/coach_sessions/demo_s_01            the completed session
    users/{uid}/coach_plans/{planId}                the plan, with its check-in answers
    users/{uid}/coach_plans/{planId}/translations/{language}
    users/{uid}.signal_sharing                      the opt-in of NF-HR-001 (merged)

The files hold the documents exactly as the backend stores them, built by the backend's own plan
flow, with the days relative: the worker leaves `departure_in_days` from today and the plan was
made `plan_created_days_ago` days ago. Every instant is moved together by the same amount, so the
plan's rates stay older than the plan, as they were. The plan id is the first 20 characters of the
SHA-256 of the answers, as the backend works it out (the departure day is one of the answers), so
a later run on another day makes another plan and removes the one it replaced: only documents
marked `demo_seed` are ever removed. The user's own document must exist already (run
`python -m src.loaders.seed` first). No Firebase Auth user is created and no profile is written:
the weekly job takes the goals from the newest plan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from src.config import SEED_COACH_DIR
from src.firestore_client import get_firestore_client
from src.utils import parse_iso, replace_value, shift_times
from src.validators.demo_coach import DEPARTURE, MILESTONE_DAYS, CoachSeed, is_blank, load

log = logging.getLogger(__name__)

SESSION_KEEP = timedelta(days=30)
MARK = "demo_seed"


def slot_hash(slots: dict[str, Any]) -> str:
    """SHA-256 of the answers as the backend writes them (`coach_plan.slot_hash`): sorted keys,
    no spaces, UTF-8. `backend/tests/unit/test_demo_seed_drift.py` holds this to the backend's."""
    canonical = json.dumps(slots, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass
class Documents:
    plan_id: str
    session_id: str
    session: dict[str, Any]
    plan: dict[str, Any]
    translations: dict[str, dict[str, Any]]
    departure: date
    notes: list[str] = field(default_factory=list)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


def checkins_for(seed: CoachSeed, departure: date) -> dict[str, Any]:
    """The check-ins the worker has had by today: a reminder at 02:00 UTC on the due day (what the
    daily job writes), and the answers where the file has them."""
    entries: dict[str, Any] = {}
    today_offset = 0
    for milestone, days in MILESTONE_DAYS.items():
        if seed.departure_in_days + days > today_offset:
            continue
        due = departure + timedelta(days=days)
        entry: dict[str, Any] = {"due_on": due.isoformat(), "notified_at": _at(due, 2)}
        answered = seed.checkins.get(milestone)  # type: ignore[call-overload]
        if answered is not None:
            when = due + timedelta(days=answered.answered_days_after_due)
            entry |= {
                "answered_at": _at(when, 9, 12),
                "answers": dict(answered.answers),
            }
        entries[milestone] = entry
    return entries


def build_documents(seed: CoachSeed, now: datetime) -> Documents:
    today = now.date()
    departure = today + timedelta(days=seed.departure_in_days)
    created = parse_iso(seed.plan["created_at"])
    delta = (now - timedelta(days=seed.plan_created_days_ago)) - created
    iso = departure.isoformat()

    plan = replace_value(shift_times(seed.plan, delta), DEPARTURE, iso)
    session = replace_value(shift_times(seed.session, delta), DEPARTURE, iso)
    plan_id = slot_hash(plan["slots"])[:20]
    plan |= {
        "slot_hash": slot_hash(plan["slots"]),
        "session_id": seed.session_id,
        "checkins": checkins_for(seed, departure),
        MARK: True,
    }
    if not plan["checkins"]:
        del plan["checkins"]
    session |= {
        "plan_id": plan_id,
        # A completed session is kept 30 days after its last turn; the file's plan is older than
        # that, so it is kept 30 days from the load instead of being swept the next day.
        "expires_at": now + SESSION_KEEP,
        MARK: True,
    }
    translations = {
        lang: {**shift_times(doc, delta), MARK: True} for lang, doc in seed.translations.items()
    }
    return Documents(plan_id, seed.session_id, session, plan, translations, departure)


@dataclass
class LoadResult:
    plan_id: str
    removed: int = 0


def load_worker(client: Client, seed: CoachSeed, now: datetime) -> LoadResult:
    """Write one worker's documents and remove the demo plan and session an earlier run left."""
    user = client.collection("users").document(seed.uid)
    if not user.get().exists:
        raise LookupError(
            f"users/{seed.uid} does not exist: run `python -m src.loaders.seed` first"
        )
    docs = build_documents(seed, now)
    result = LoadResult(docs.plan_id)
    plans = user.collection("coach_plans")
    sessions = user.collection("coach_sessions")

    batch = client.batch()
    batch.set(user, {"signal_sharing": seed.signal_sharing.model_dump()}, merge=True)
    batch.set(sessions.document(docs.session_id), docs.session)
    batch.set(plans.document(docs.plan_id), docs.plan)
    for lang, translation in docs.translations.items():
        batch.set(
            plans.document(docs.plan_id).collection("translations").document(lang), translation
        )
    for old in plans.where(filter=FieldFilter(MARK, "==", True)).stream():
        if old.id != docs.plan_id:
            for tr in plans.document(old.id).collection("translations").stream():
                batch.delete(plans.document(old.id).collection("translations").document(tr.id))
            batch.delete(plans.document(old.id))
            result.removed += 1
    for old in sessions.stream():
        if old.id.startswith("demo_s_") and old.id != docs.session_id:
            batch.delete(sessions.document(old.id))
            result.removed += 1
    batch.commit()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the demo Coach sessions and plans.")
    parser.add_argument("--input-dir", type=Path, default=SEED_COACH_DIR)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="file names without .json")
    parser.add_argument("--dry-run", action="store_true", help="Validate without Firestore")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    files = sorted(args.input_dir.glob("*.json"))
    if args.only:
        files = [f for f in files if f.stem in set(args.only)]
    seeds: list[tuple[Path, CoachSeed]] = []
    failed = False
    for path in files:
        if is_blank(path):
            log.info("%s: empty, skipped", path.name)
            continue
        try:
            seeds.append((path, load(path)))
        except (ValidationError, ValueError, OSError) as exc:
            failed = True
            log.error("%s: %s", path.name, exc)
    if failed:
        log.error("Nothing was written: fix the file(s) and run again.")
        return 1

    now = datetime.now(UTC)
    client = None if args.dry_run else get_firestore_client()
    for path, seed in seeds:
        docs = build_documents(seed, now)
        if client is None:
            log.info(
                "[dry-run] %s -> users/%s/coach_plans/%s (leaves %s)",
                path.name,
                seed.uid,
                docs.plan_id,
                docs.departure,
            )
            continue
        try:
            result = load_worker(client, seed, now)
        except LookupError as exc:
            log.error("%s: %s", path.name, exc)
            return 1
        log.info(
            "%s -> users/%s: plan %s, session %s, %d check-in(s), removed %d stale",
            path.name,
            seed.uid,
            result.plan_id,
            docs.session_id,
            len(docs.plan.get("checkins", {})),
            result.removed,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
