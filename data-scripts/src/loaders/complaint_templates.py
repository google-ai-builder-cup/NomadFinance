"""Load the curated complaint templates into Firestore `complaint_templates/{country}` (NF-P2-006).

Run from data-scripts/:  python -m src.loaders.complaint_templates
Reads data/source/complaint-templates/<CC>.json, validates every file with the same model the
checker uses, and only then writes. Per country it writes, in one atomic batch:

    complaint_templates/{CC}                 header
    complaint_templates/{CC}/types/{type}    one document per template type

A type that was removed from the file is deleted from Firestore in the same batch, so the
collection always matches the files. Unlike labor laws there is no version number: a report
keeps the letter it was made with, and a changed template only reaches new letters.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from firebase_admin import firestore  # type: ignore[import-untyped]
from google.cloud.firestore import Client
from pydantic import ValidationError

from src.config import COMPLAINT_TEMPLATES_DIR
from src.firestore_client import get_firestore_client
from src.validators.complaint_template import ComplaintTemplateFile, load
from src.validators.labor_law import COUNTRIES

log = logging.getLogger(__name__)

COMPLAINT_TEMPLATES_COLLECTION = "complaint_templates"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LoadResult:
    """What was written for one country."""

    country: str
    written: int
    removed: int


def read_country_files(
    directory: Path, only: list[str] | None = None
) -> tuple[dict[str, ComplaintTemplateFile], list[str]]:
    """Validate every country file; returns (valid files, problems found)."""
    valid: dict[str, ComplaintTemplateFile] = {}
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
        if only and path.stem not in only:
            continue
        try:
            parsed = load(path)
        except ValidationError as exc:
            problems.append(f"{path.name}: {exc.error_count()} problem(s)")
            problems.extend(
                f"    {'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
                for err in exc.errors()[:10]
            )
        except (ValueError, OSError) as exc:
            problems.append(f"{path.name}: {exc}")
        else:
            valid[parsed.country] = parsed
    return valid, problems


def _type_payload(parsed: ComplaintTemplateFile, type_id: str) -> dict[str, Any]:
    payload = parsed.types[type_id].model_dump(mode="json")
    payload.update(country=parsed.country, type=type_id, schema_version=SCHEMA_VERSION)
    return payload


def load_country(
    client: Client,
    parsed: ComplaintTemplateFile,
    *,
    collection: str = COMPLAINT_TEMPLATES_COLLECTION,
) -> LoadResult:
    """Write one country in a single batch so a crash never leaves it half-loaded."""
    country_ref = client.collection(collection).document(parsed.country)
    types_ref = country_ref.collection("types")
    stale = [doc.id for doc in types_ref.stream() if doc.id not in parsed.types]

    batch = client.batch()
    for type_id in parsed.types:
        batch.set(types_ref.document(type_id), _type_payload(parsed, type_id))
    for type_id in stale:
        batch.delete(types_ref.document(type_id))
    batch.set(
        country_ref,
        {
            "country": parsed.country,
            "template_count": len(parsed.types),
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
    )
    batch.commit()
    return LoadResult(parsed.country, len(parsed.types), len(stale))


def load_templates(
    client: Client,
    files: dict[str, ComplaintTemplateFile],
    *,
    collection: str = COMPLAINT_TEMPLATES_COLLECTION,
) -> list[LoadResult]:
    results: list[LoadResult] = []
    for country in COUNTRIES:
        if country not in files:
            continue
        result = load_country(client, files[country], collection=collection)
        log.info("%s  %d template(s) written, %d removed", country, result.written, result.removed)
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load curated complaint templates into Firestore.")
    parser.add_argument(
        "--input-dir", type=Path, default=COMPLAINT_TEMPLATES_DIR, help="Folder of <CC>.json files"
    )
    parser.add_argument("--only", nargs="+", choices=COUNTRIES, help="Load just these countries")
    parser.add_argument(
        "--collection", default=COMPLAINT_TEMPLATES_COLLECTION, help="Target Firestore collection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    parser.add_argument(
        "--require-all", action="store_true", help="Fail if a country has no template file"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    files, problems = read_country_files(args.input_dir, args.only)

    for problem in problems:
        log.error(problem)
    if problems:
        log.error("Nothing was written: fix the files above and run again.")
        return 1
    if args.require_all:
        missing = [c for c in COUNTRIES if c not in files]
        if missing:
            log.error("--require-all: no template file for %s", ", ".join(missing))
            return 1
    if not files:
        log.error("No template files found in %s", args.input_dir)
        return 1

    for country in COUNTRIES:
        if country in files:
            log.info(
                "Validated %s: %s",
                country,
                ", ".join(files[country].types),
            )

    if args.dry_run:
        for country in COUNTRIES:
            if country in files:
                log.info(
                    "[dry-run] would write %s/%s: %d template(s) + header",
                    args.collection,
                    country,
                    len(files[country].types),
                )
        return 0

    results = load_templates(get_firestore_client(), files, collection=args.collection)
    log.info("Loaded %d countries into %r", len(results), args.collection)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
