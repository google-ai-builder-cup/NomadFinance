"""Load the demo users' Financial Identity history into Firestore (NF-P3-015).

Run from data-scripts/:  python -m src.loaders.seed
For each file in data/seed/users/ (empty stubs are skipped) it writes, in one atomic batch:

    users/{uid}/income|transfers|bills|savings/{demo_*}   the entries in the file
    users/{uid}                                           only if it does not exist yet

It never creates a Firebase Auth user and never writes `financial_profile`: the weekly job
(`fib-recompute`, NF-P3-013) computes that from these entries, so the scores and the report
text come from the real pipeline.

Dates are `months_ago` and `day` in the file, turned into real dates relative to the day the
loader runs, so the history always ends today. An entry that would fall after today is left
out (the next run adds it). Entry ids start with `demo_`: writing again replaces them, and a
`demo_` entry that was removed from the file is deleted; entries of any other id are never
touched. Field names and values follow docs/data-model/collections/fib.md.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from google.cloud.firestore import Client
from pydantic import ValidationError

from src.config import SEED_USERS_DIR
from src.firestore_client import get_firestore_client
from src.validators.demo_user import UserSeed, is_blank, load, seed_files

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
KINDS = ("income", "transfers", "bills", "savings")
DEMO_PREFIX = "demo_"


def entry_date(today: date, months_ago: int, day: int) -> date:
    """The date `months_ago` calendar months before today's month, on `day` (1 to 28)."""
    index = today.year * 12 + today.month - 1 - months_ago
    return date(index // 12, index % 12 + 1, day)


def _timestamp(day: date, now: datetime) -> datetime:
    """Noon UTC on the entry's day, but never later than now."""
    return min(datetime.combine(day, time(12), tzinfo=UTC), now)


def _optional(source: dict[str, Any], *names: str) -> dict[str, Any]:
    return {name: source[name] for name in names if source.get(name) is not None}


def entry_documents(
    seed: UserSeed, today: date, now: datetime
) -> tuple[dict[str, dict[str, dict[str, Any]]], int]:
    """The documents of every entry dated up to today, by collection and id, and how many
    entries were left out because their date is still ahead."""
    documents: dict[str, dict[str, dict[str, Any]]] = {kind: {} for kind in KINDS}
    ahead = 0
    groups: tuple[tuple[str, list[Any], str], ...] = (
        ("income", seed.income, "manual"),
        ("transfers", seed.transfers, "remittance_log"),
        ("bills", seed.bills, ""),
        ("savings", seed.savings, "manual"),
    )
    for kind, entries, source in groups:
        for entry in entries:
            day = entry_date(today, entry.months_ago, entry.day)
            if day > today:
                ahead += 1
                continue
            data = entry.model_dump(exclude={"id", "months_ago", "day"}, exclude_none=True)
            doc: dict[str, Any] = {
                "entry_date": day.isoformat(),
                **data,
                "source": data.get("source", source),
                "created_at": _timestamp(day, now),
                "updated_at": _timestamp(day, now),
                "schema_version": SCHEMA_VERSION,
            }
            if kind == "income":
                # A worker's own entry: the category is theirs and nothing backs it up.
                doc |= {"category_source": "user", "verified": False}
            if kind == "bills":
                bill_day = doc.pop("bill_day", None)
                if bill_day is not None:
                    doc["bill_date"] = entry_date(today, entry.months_ago, bill_day).isoformat()
            documents[kind][entry.id] = doc
    return documents, ahead


def user_document(seed: UserSeed, now: datetime) -> dict[str, Any]:
    """`users/{uid}`, as onboarding would have left it (users.md)."""
    corridors = sorted({t.corridor_id for t in seed.transfers})
    return {
        **seed.user.model_dump(),
        "onboarding_completed_at": now,
        "notification_prefs": {
            "radar_alerts": True,
            "radar_corridors": corridors,
            "reminders": True,
        },
        "fcm_tokens": [],
        "created_at": now,
        "updated_at": now,
        "schema_version": SCHEMA_VERSION,
    }


@dataclass
class LoadResult:
    written: dict[str, int] = field(default_factory=dict)
    ahead: int = 0
    removed: int = 0
    user_created: bool = False


def load_user(client: Client, seed: UserSeed, uid: str, today: date, now: datetime) -> LoadResult:
    """Write one user's entries in one batch; see the module docstring for the rules."""
    user_ref = client.collection("users").document(uid)
    documents, ahead = entry_documents(seed, today, now)
    result = LoadResult(ahead=ahead)

    batch = client.batch()
    if not user_ref.get().exists:
        batch.set(user_ref, user_document(seed, now))
        result.user_created = True
    for kind in KINDS:
        collection = user_ref.collection(kind)
        for doc_id, doc in documents[kind].items():
            batch.set(collection.document(doc_id), doc)
        result.written[kind] = len(documents[kind])
        for existing in collection.stream():
            if existing.id.startswith(DEMO_PREFIX) and existing.id not in documents[kind]:
                batch.delete(collection.document(existing.id))
                result.removed += 1
    batch.commit()
    return result


def _select(directory: Path, only: list[str] | None) -> list[Path]:
    files = seed_files(directory)
    if only:
        wanted = set(only)
        files = [f for f in files if f.stem in wanted]
        missing = wanted - {f.stem for f in files}
        if missing:
            raise ValueError(f"no such seed file: {', '.join(sorted(missing))}")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load demo user history into Firestore.")
    parser.add_argument("--input-dir", type=Path, default=SEED_USERS_DIR)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="file names without .json")
    parser.add_argument(
        "--uid",
        help="write under this Firebase uid instead of the file's own (one user only): the "
        "uid of the account that will show the demo",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        files = _select(args.input_dir, args.only)
    except ValueError as exc:
        log.error("%s", exc)
        return 1

    seeds: list[tuple[Path, UserSeed]] = []
    failed = False
    for path in files:
        if is_blank(path):
            log.info("%s: empty, skipped", path.name)
            continue
        try:
            seeds.append((path, load(path)))
        except ValidationError as exc:
            failed = True
            log.error("%s: %d problem(s)", path.name, exc.error_count())
            for err in exc.errors()[:10]:
                log.error("    %s: %s", ".".join(str(p) for p in err["loc"]), err["msg"])
        except (ValueError, OSError) as exc:
            failed = True
            log.error("%s: %s", path.name, exc)
    if failed:
        log.error("Nothing was written: fix the file(s) and run again.")
        return 1
    if args.uid and len(seeds) != 1:
        log.error("--uid needs exactly one user: add --only <name>")
        return 1

    now = datetime.now(UTC)
    today = now.date()
    client = None if args.dry_run else get_firestore_client()
    for path, seed in seeds:
        uid = args.uid or seed.uid
        documents, ahead = entry_documents(seed, today, now)
        counts = ", ".join(f"{len(documents[k])} {k}" for k in KINDS)
        if args.dry_run:
            log.info(
                "[dry-run] %s -> users/%s: %s (%d dated after today)", path.name, uid, counts, ahead
            )
            continue
        assert client is not None
        result = load_user(client, seed, uid, today, now)
        log.info(
            "%s -> users/%s: wrote %s; %d dated after today left out; removed %d stale; "
            "user document %s",
            path.name,
            uid,
            counts,
            result.ahead,
            result.removed,
            "created" if result.user_created else "left as it was",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
