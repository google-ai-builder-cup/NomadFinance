"""Load the curated scam taxonomy into Firestore `scam_taxonomy/{id}` (NF-SA-001).

Run from data-scripts/:  python -m src.loaders.scam_taxonomy
Reads data/source/scam-taxonomy/types.json and tactics.json, validates both with the checker's
model, and only then writes, in one atomic batch:

    scam_taxonomy/{id}       one document per type and per tactic (the id is unique across both)
    scam_taxonomy/_meta      version, content hash, updated_at; only when the content changed

A document whose id is no longer in the files is deleted in the same batch, so the collection
always matches the files. `_meta.version` is what a stored scam check records as
`taxonomy_version`, and the check cache ignores checks made under another version: it must go
up when the wording the classifier or the worker reads changes, and not on a plain re-run.
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

from src.config import SCAM_TAXONOMY_DIR
from src.firestore_client import get_firestore_client
from src.validators.scam_taxonomy import Taxonomy, load_taxonomy

log = logging.getLogger(__name__)

SCAM_TAXONOMY_COLLECTION = "scam_taxonomy"
META_ID = "_meta"
SCHEMA_VERSION = 1

# Who curated an entry and where it came from do not change what a check says, so they stay out
# of the hash: re-checking a source page or a change of curator must not retire every cached
# verdict.
_NOT_HASHED = ("sources", "curator")


@dataclass(frozen=True)
class LoadResult:
    """What happened in one load."""

    types: int
    tactics: int
    removed: int
    version: int
    status: str  # "new", "changed" or "unchanged"


def _documents(taxonomy: Taxonomy) -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for kind, entries in (("type", taxonomy.types), ("tactic", taxonomy.tactics)):
        for entry_id, entry in entries.items():
            payload = entry.model_dump(mode="json", exclude_none=True)
            payload.update(kind=kind, schema_version=SCHEMA_VERSION)
            docs[entry_id] = payload
    return docs


def content_hash(taxonomy: Taxonomy) -> str:
    """SHA-256 of the taxonomy in canonical form, over the fields a check depends on."""
    hashed = {
        entry_id: {k: v for k, v in doc.items() if k not in _NOT_HASHED}
        for entry_id, doc in _documents(taxonomy).items()
    }
    canonical = json.dumps(hashed, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _next_version(stored: dict[str, Any] | None, digest: str) -> tuple[int, str]:
    """Decide the version from what Firestore already holds: (version, status)."""
    if stored is None:
        return 1, "new"
    version = int(stored["version"])
    if stored.get("content_hash") == digest:
        return version, "unchanged"
    return version + 1, "changed"


def load_taxonomy_docs(
    client: Client, taxonomy: Taxonomy, *, collection: str = SCAM_TAXONOMY_COLLECTION
) -> LoadResult:
    """Write the whole taxonomy in a single batch so a crash never leaves it half-loaded."""
    coll = client.collection(collection)
    docs = _documents(taxonomy)
    stale = [d.id for d in coll.stream() if d.id != META_ID and d.id not in docs]

    meta_ref = coll.document(META_ID)
    snapshot = meta_ref.get()
    digest = content_hash(taxonomy)
    version, status = _next_version(snapshot.to_dict() if snapshot.exists else None, digest)

    batch = client.batch()
    for doc_id, payload in docs.items():
        batch.set(coll.document(doc_id), payload)
    for doc_id in stale:
        batch.delete(coll.document(doc_id))
    if status != "unchanged":
        batch.set(
            meta_ref,
            {"version": version, "content_hash": digest, "updated_at": firestore.SERVER_TIMESTAMP},
        )
    batch.commit()
    return LoadResult(len(taxonomy.types), len(taxonomy.tactics), len(stale), version, status)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load the curated scam taxonomy into Firestore.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=SCAM_TAXONOMY_DIR,
        help="Folder with types.json, tactics.json",
    )
    parser.add_argument(
        "--collection", default=SCAM_TAXONOMY_COLLECTION, help="Target Firestore collection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        taxonomy = load_taxonomy(args.input_dir)
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

    log.info(
        "Validated %d type(s) and %d tactic(s), content hash %s",
        len(taxonomy.types),
        len(taxonomy.tactics),
        content_hash(taxonomy)[:12],
    )
    if args.dry_run:
        log.info(
            "[dry-run] would write %d documents to %s (+ _meta if changed)",
            len(taxonomy.types) + len(taxonomy.tactics),
            args.collection,
        )
        return 0

    result = load_taxonomy_docs(get_firestore_client(), taxonomy, collection=args.collection)
    log.info(
        "Loaded %d type(s) and %d tactic(s) into %r: version %d, %s, %d removed",
        result.types,
        result.tactics,
        args.collection,
        result.version,
        result.status,
        result.removed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
