"""Load the demo workers' stored scam checks into Firestore (NF-HR-003).

Run from data-scripts/:  python -m src.loaders.demo_scam
For each file in data/seed/scam-checks/ it writes, in one atomic batch,
`users/{uid}/scam_checks/{first 32 characters of the cache key}` for each of the five checks.

The files hold each check exactly as the backend's analyzer stores it (built by
`backend/tests/fixtures/demo_seed.py`). The id and the cache key are the backend's, so a worker who
pastes one of these messages again, in the language it was checked in, is answered from the stored
check with no Gemini call, as the backend serves any repeated message. For that the stored check
must carry the taxonomy version the backend now has: it is read from `scam_taxonomy/_meta` (the
version in the file is used, with a warning, when the taxonomy is not loaded). The days are
relative: a check was made `days_ago` days before the loader runs, at `hour_utc`, and expires 90
days after it was last checked. Only documents marked `demo_seed` are ever removed.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from src.config import SEED_SCAM_DIR
from src.firestore_client import get_firestore_client
from src.validators.demo_scam import CheckSeed, ScamSeed, is_blank, load, message_key

log = logging.getLogger(__name__)

CHECK_TTL = timedelta(days=90)
MARK = "demo_seed"


def check_document(check: CheckSeed, now: datetime, taxonomy_version: int | None) -> dict[str, Any]:
    """The document as stored: the file's, with the times and the taxonomy version set."""
    when = datetime.combine(
        (now - timedelta(days=check.days_ago)).date(), time(check.hour_utc), tzinfo=UTC
    )
    when = min(when, now)
    document = dict(check.document)
    document |= {
        "created_at": when,
        "last_checked_at": when,
        "expires_at": when + CHECK_TTL,
        "cache_key": message_key(check.document),
        MARK: True,
    }
    if taxonomy_version is not None:
        document["taxonomy_version"] = taxonomy_version
    return document


def check_id(document: dict[str, Any]) -> str:
    return str(document["cache_key"])[:32]


def taxonomy_version_of(client: Client) -> int | None:
    snapshot = client.collection("scam_taxonomy").document("_meta").get()
    data = snapshot.to_dict() if snapshot.exists else None
    version = (data or {}).get("version")
    return int(version) if isinstance(version, int) else None


@dataclass
class LoadResult:
    written: int = 0
    removed: int = 0


def load_worker(
    client: Client, seed: ScamSeed, now: datetime, taxonomy_version: int | None
) -> LoadResult:
    user = client.collection("users").document(seed.uid)
    if not user.get().exists:
        raise LookupError(
            f"users/{seed.uid} does not exist: run `python -m src.loaders.seed` first"
        )
    checks = user.collection("scam_checks")
    documents = {
        check_id(doc): doc
        for doc in (check_document(c, now, taxonomy_version) for c in seed.checks)
    }
    result = LoadResult()
    batch = client.batch()
    for doc_id, document in documents.items():
        batch.set(checks.document(doc_id), document)
        result.written += 1
    for old in checks.where(filter=FieldFilter(MARK, "==", True)).stream():
        if old.id not in documents:
            batch.delete(checks.document(old.id))
            result.removed += 1
    batch.commit()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the demo workers' scam checks.")
    parser.add_argument("--input-dir", type=Path, default=SEED_SCAM_DIR)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="file names without .json")
    parser.add_argument("--dry-run", action="store_true", help="Validate without Firestore")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    files = sorted(args.input_dir.glob("*.json"))
    if args.only:
        files = [f for f in files if f.stem in set(args.only)]
    seeds: list[tuple[Path, ScamSeed]] = []
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
    version = None if client is None else taxonomy_version_of(client)
    if client is not None and version is None:
        log.warning(
            "scam_taxonomy/_meta is not loaded: the checks keep the file's taxonomy version and "
            "will not answer a repeated message until it matches "
            "(python -m src.loaders.scam_taxonomy)"
        )
    for path, seed in seeds:
        if client is None:
            log.info("[dry-run] %s -> users/%s: %d checks", path.name, seed.uid, len(seed.checks))
            continue
        try:
            result = load_worker(client, seed, now, version)
        except LookupError as exc:
            log.error("%s: %s", path.name, exc)
            return 1
        log.info(
            "%s -> users/%s: wrote %d checks, removed %d stale",
            path.name,
            seed.uid,
            result.written,
            result.removed,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
