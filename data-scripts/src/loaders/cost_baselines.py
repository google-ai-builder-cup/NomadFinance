"""Load the curated cost-of-living baselines into Firestore `cost_baselines/{host}` (NF-FC-003).

Run from data-scripts/:  python -m src.loaders.cost_baselines
Reads data/source/cost-baselines/{host}.json, validates every selected file with the checker's
model, and only then writes all the countries in one atomic batch. Each document carries its own
`version` and `content_hash`: the Coach plan records `grounding.baselines.version`, so the version
must go up when a figure or its meaning changes, and not on a plain re-run.

A host without a file is left alone, and nothing is ever deleted: South Korea, Malaysia, Japan and
Hong Kong are curated by other tasks (NF-FC-004, NF-FC-005) and may be loaded before or after.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client
from pydantic import ValidationError

from src.config import COST_BASELINES_DIR
from src.firestore_client import get_firestore_client
from src.validators.cost_baselines import CostBaseline, load_baselines

log = logging.getLogger(__name__)

COST_BASELINES_COLLECTION = "cost_baselines"
SCHEMA_VERSION = 1

# Which page a figure was read from, and who read it, do not change what a plan is built from, so
# they stay out of the hash: re-checking a page that still says the same must not raise the version.
_NOT_HASHED = ("source", "other_sources", "curator")


@dataclass(frozen=True)
class LoadResult:
    """What happened to one host in one load."""

    host: str
    version: int
    status: str  # "new", "changed", "refreshed" (sources only) or "unchanged"


def _content(baseline: CostBaseline) -> dict[str, Any]:
    return baseline.model_dump(mode="json", exclude_none=True)


def _strip(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k not in _NOT_HASHED}
    return node


def content_hash(baseline: CostBaseline) -> str:
    """SHA-256 of the figures and their wording in canonical form, without sources or curator."""
    canonical = json.dumps(
        _strip(_content(baseline)), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _document(baseline: CostBaseline, version: int, digest: str) -> dict[str, Any]:
    payload = _content(baseline)
    payload.update(version=version, content_hash=digest, schema_version=SCHEMA_VERSION)
    return payload


def load_baseline_docs(
    client: Client,
    baselines: dict[str, CostBaseline],
    *,
    collection: str = COST_BASELINES_COLLECTION,
) -> list[LoadResult]:
    """Write every given country in a single batch so a crash never leaves a half-load."""
    coll = client.collection(collection)
    batch = client.batch()
    results: list[LoadResult] = []
    writes = 0
    for host, baseline in baselines.items():
        ref = coll.document(host)
        snapshot = ref.get()
        stored = snapshot.to_dict() if snapshot.exists else None
        digest = content_hash(baseline)
        if stored is None:
            version, status = 1, "new"
        elif stored.get("content_hash") != digest:
            version, status = int(stored["version"]) + 1, "changed"
        else:
            version, status = int(stored["version"]), "refreshed"
        payload = _document(baseline, version, digest)
        if stored is not None and {k: v for k, v in stored.items() if k != "updated_at"} == payload:
            status = "unchanged"
        else:
            batch.set(ref, {**payload, "updated_at": firestore.SERVER_TIMESTAMP})
            writes += 1
        results.append(LoadResult(host, version, status))
    if writes:
        batch.commit()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load the cost-of-living baselines into Firestore."
    )
    parser.add_argument(
        "--input-dir", type=Path, default=COST_BASELINES_DIR, help="Folder with {host}.json files"
    )
    parser.add_argument(
        "--only", nargs="+", metavar="HOST", help="Load only these hosts, for example SG AU"
    )
    parser.add_argument(
        "--collection", default=COST_BASELINES_COLLECTION, help="Target Firestore collection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        baselines = load_baselines(args.input_dir, args.only)
    except ValidationError as exc:
        log.error("%d problem(s)", exc.error_count())
        for err in exc.errors()[:25]:
            log.error("    %s: %s", ".".join(str(p) for p in err["loc"]), err["msg"])
        log.error("Nothing was written: fix the files above and run again.")
        return 1
    except (ValueError, OSError) as exc:
        log.error("%s", exc)
        log.error("Nothing was written: fix the files above and run again.")
        return 1

    for host, baseline in baselines.items():
        log.info(
            "Validated %s (%s), content hash %s",
            host,
            baseline.currency,
            content_hash(baseline)[:12],
        )
    if args.dry_run:
        log.info("[dry-run] would write %d document(s) to %s", len(baselines), args.collection)
        return 0

    results = load_baseline_docs(get_firestore_client(), baselines, collection=args.collection)
    for result in results:
        log.info(
            "Loaded %s into %r: version %d, %s",
            result.host,
            args.collection,
            result.version,
            result.status,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
