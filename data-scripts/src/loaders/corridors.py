"""Load parsed World Bank RPW corridor data into Firestore `corridors/{corridor_id}`.

Run from data-scripts/:  python -m src.loaders.corridors
Reads data-scripts/data/processed/rpw_corridors.json (built by NF-P1-016's dependency,
NF-P1-015) and writes it as-is; this script does not touch the World Bank Excel or
re-derive any values.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client

from src.config import RPW_OUTPUT_FILE
from src.firestore_client import get_firestore_client
from src.validators.corridor import CorridorDoc, RpwCorridorFile, SourceInfo

log = logging.getLogger(__name__)

CORRIDORS_COLLECTION = "corridors"


def load_corridor_file(path: Path = RPW_OUTPUT_FILE) -> RpwCorridorFile:
    """Read and re-validate the parser's output; refuses to load a file that fails the schema."""
    return RpwCorridorFile.model_validate_json(path.read_text(encoding="utf-8"))


def _document_payload(source: SourceInfo, doc: CorridorDoc) -> dict[str, Any]:
    """Build one Firestore document body: the corridor plus the two loader-added fields."""
    payload = doc.model_dump(mode="json")
    # Only these three are shown to users; file_name/sheet are parser bookkeeping, not attribution.
    payload["source"] = {
        "name": source.name,
        "url": source.url,
        "attribution": source.attribution,
    }
    payload["loaded_at"] = firestore.SERVER_TIMESTAMP
    return payload


def load_corridors(
    output: RpwCorridorFile, client: Client, *, collection: str = CORRIDORS_COLLECTION
) -> int:
    """Write one document per corridor with a plain `set`; re-running replaces, never duplicates."""
    ref = client.collection(collection)
    for doc in output.corridors:
        ref.document(doc.corridor_id).set(_document_payload(output.source, doc))
        log.info("%s  %3d providers  written", doc.corridor_id, doc.provider_count)
    return len(output.corridors)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load parsed RPW corridor data into Firestore.")
    parser.add_argument("--input", type=Path, default=RPW_OUTPUT_FILE, help="Parsed corridor JSON")
    parser.add_argument(
        "--collection", default=CORRIDORS_COLLECTION, help="Target Firestore collection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without writing to Firestore"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    output = load_corridor_file(args.input)
    total = sum(c.provider_count for c in output.corridors)
    log.info(
        "Validated %s: %d corridors, %d providers, period %s",
        args.input,
        len(output.corridors),
        total,
        output.period,
    )

    if args.dry_run:
        for doc in output.corridors:
            log.info(
                "[dry-run] would write %s/%s  %3d providers",
                args.collection,
                doc.corridor_id,
                doc.provider_count,
            )
        return 0

    client = get_firestore_client()
    written = load_corridors(output, client, collection=args.collection)
    log.info("Wrote %d corridor documents to %r", written, args.collection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
