"""Embed the scam pattern library and load it into Firestore `scam_patterns/{id}` (NF-SA-006).

Run from data-scripts/:  python -m src.loaders.scam_patterns [--dry-run]
Reads data/source/scam-patterns/*.jsonl, validates every row and the library as a whole, and only
then embeds and writes:

    scam_patterns/{id}   text, type, tactics, language, corridor, a 768-number vector

Safe to run again. Each document stores a hash of what its vector depends on (the text, the
labels, the model and the size); a row whose hash is unchanged is neither embedded nor written,
so a second run makes no Gemini call and no write. A document whose id left the files is
deleted. Every embedding is made before the first write, so a Gemini failure writes nothing.

Needs GEMINI_API_KEY in the environment, and either FIRESTORE_EMULATOR_HOST or Application
Default Credentials with write access to the project (src/firestore_client.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client
from google.cloud.firestore_v1.vector import Vector

from src.config import SCAM_PATTERNS_DIR
from src.embedding import CachedEmbedder, Embedder, EmbeddingQuotaError, GeminiEmbedder
from src.firestore_client import get_firestore_client
from src.validators.scam_patterns import PatternRow, check_library, load_all

log = logging.getLogger(__name__)

SCAM_PATTERNS_COLLECTION = "scam_patterns"
SCHEMA_VERSION = 1
SOURCE = "curated"
_WRITES_PER_BATCH = 400  # Firestore allows 500 operations in one batch


@dataclass(frozen=True)
class LoadResult:
    """What happened in one load."""

    new: int
    changed: int
    unchanged: int
    removed: int

    @property
    def embedded(self) -> int:
        return self.new + self.changed


def content_hash(row: PatternRow, model: str, dimension: int) -> str:
    """SHA-256 of what the stored vector depends on. The curator is left out on purpose: a change
    of who reviewed a row does not change its vector, so it must not cost an embedding call."""
    payload = {
        "text": row.text,
        "scam_type": row.scam_type,
        "language": row.language,
        "tactics": row.tactics,
        "corridor_id": row.corridor_id,
        "model": model,
        "dimension": dimension,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _document(
    row: PatternRow, vector: list[float], embedder: Embedder, digest: str
) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "scam_type": row.scam_type,
        "tactics": row.tactics,
        "language": row.language,
        "text": row.text,
        "embedding": Vector(vector),
        "embedding_model": embedder.model,
        "dimension": embedder.dimension,
        "source": SOURCE,
        "curator": row.curator,
        "schema_version": SCHEMA_VERSION,
        "content_hash": digest,
    }
    if row.corridor_id is not None:
        doc["corridor_id"] = row.corridor_id
    return doc


def _chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def load_pattern_docs(
    client: Client,
    rows: list[PatternRow],
    embedder: Embedder,
    *,
    collection: str = SCAM_PATTERNS_COLLECTION,
) -> LoadResult:
    """Make the collection match `rows`, embedding and writing only what changed."""
    coll = client.collection(collection)
    stored = {snap.id: (snap.to_dict() or {}) for snap in coll.stream()}
    wanted = {row.id for row in rows}
    stale = sorted(stored.keys() - wanted)

    pending: list[tuple[PatternRow, str, bool]] = []  # (row, hash, is_new)
    unchanged = 0
    for row in rows:
        digest = content_hash(row, embedder.model, embedder.dimension)
        current = stored.get(row.id)
        if current is not None and current.get("content_hash") == digest:
            unchanged += 1
        else:
            pending.append((row, digest, current is None))

    vectors = embedder.embed([row.text for row, _, _ in pending]) if pending else []
    if len(vectors) != len(pending):
        raise RuntimeError(f"embedded {len(vectors)} of {len(pending)} templates; nothing written")

    writes: list[tuple[str, dict[str, Any], bool]] = []
    for (row, digest, is_new), vector in zip(pending, vectors, strict=True):
        doc = _document(row, vector, embedder, digest)
        if row.corridor_id is None and not is_new:
            doc["corridor_id"] = firestore.DELETE_FIELD  # merge would otherwise keep the old one
        if is_new:
            doc["created_at"] = firestore.SERVER_TIMESTAMP
        writes.append((row.id, doc, is_new))

    for chunk in _chunks(writes, _WRITES_PER_BATCH):
        batch = client.batch()
        for doc_id, doc, is_new in chunk:
            # merge keeps the original `created_at` when a template is re-embedded
            batch.set(coll.document(doc_id), doc, merge=not is_new)
        batch.commit()
    for chunk in _chunks(stale, _WRITES_PER_BATCH):
        batch = client.batch()
        for doc_id in chunk:
            batch.delete(coll.document(doc_id))
        batch.commit()

    new = sum(1 for _, _, is_new in pending if is_new)
    return LoadResult(new, len(pending) - new, unchanged, len(stale))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed and load the scam pattern library.")
    parser.add_argument("--input-dir", type=Path, default=SCAM_PATTERNS_DIR)
    parser.add_argument("--collection", default=SCAM_PATTERNS_COLLECTION)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count without calling Gemini or touching Firestore",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    rows, problems = load_all(args.input_dir)
    if not problems:
        problems = check_library(rows)
    if problems:
        log.error("%d problem(s)", len(problems))
        for problem in problems[:25]:
            log.error("    %s", problem)
        log.error("Nothing was written: fix the files above and run again.")
        return 1

    log.info("Validated %d templates", len(rows))
    if args.dry_run:
        log.info(
            "[dry-run] would embed and write up to %d documents to %s", len(rows), args.collection
        )
        return 0

    try:
        result = load_pattern_docs(
            get_firestore_client(),
            rows,
            CachedEmbedder(GeminiEmbedder()),
            collection=args.collection,
        )
    except EmbeddingQuotaError as exc:
        # Every embedding is made before the first write, so nothing was written.
        log.error("%s", exc)
        return 2  # not a failure of the data: run again later
    log.info(
        "Loaded %r: %d new, %d changed, %d unchanged, %d removed (%d embedded)",
        args.collection,
        result.new,
        result.changed,
        result.unchanged,
        result.removed,
        result.embedded,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
