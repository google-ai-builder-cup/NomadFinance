"""Load the curated labor-law files into Firestore `labor_laws/{country}` (NF-P1-018).

Run from data-scripts/:  python -m src.loaders.ilo_natlex
Reads data/source/labor-laws/<CC>.json (curated for NF-P1-017 from ILO NATLEX and the official
law portals), validates every file with the same model the checker uses, and only then writes.
Per country it writes, in one atomic batch:

    labor_laws/{CC}                  header
    labor_laws/{CC}/rules/{category} the 15 rules
    labor_laws/{CC}/_meta/current    version, only when the rules changed

`_meta/current.version` is what stored contract reports are cached against, so it must go up
when a country's rules change and must NOT go up on a plain re-run.
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

from src.config import LABOR_LAWS_DIR
from src.firestore_client import get_firestore_client
from src.validators.labor_law import CATEGORY_IDS, COUNTRIES, LaborLawFile, load

log = logging.getLogger(__name__)

LABOR_LAWS_COLLECTION = "labor_laws"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class LoadResult:
    """What happened to one country in a load."""

    country: str
    version: int
    status: str  # "new", "changed" or "unchanged"


def content_hash(parsed: LaborLawFile) -> str:
    """SHA-256 of the country's rules in canonical form.

    Hashing the validated rules, not the file bytes, means line endings, JSON layout, reviewer
    names and file-level notes never bump the version; only a change to a rule does.
    """
    rules = parsed.model_dump(mode="json")["rules"]
    canonical = json.dumps(
        {"country": parsed.country, "rules": rules},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_country_files(
    directory: Path, only: list[str] | None = None
) -> tuple[dict[str, LaborLawFile], list[str], list[str]]:
    """Validate every country file; returns (valid files, stubs skipped, problems found)."""
    valid: dict[str, LaborLawFile] = {}
    skipped: list[str] = []
    problems: list[str] = []
    for path in sorted(directory.glob("*.json")):
        if only and path.stem not in only:
            continue
        try:
            if json.loads(path.read_text(encoding="utf-8-sig")) == {}:
                skipped.append(path.stem)
                continue
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
    return valid, skipped, problems


def _rule_payload(parsed: LaborLawFile, category: str) -> dict[str, Any]:
    payload = parsed.rules[category].model_dump(mode="json")
    payload.update(country=parsed.country, category=category, schema_version=SCHEMA_VERSION)
    return payload


def _header_payload(parsed: LaborLawFile) -> dict[str, Any]:
    return {
        "country": parsed.country,
        "name": parsed.name,
        "rule_count": len(parsed.rules),
        "updated_at": firestore.SERVER_TIMESTAMP,
    }


def _meta_payload(parsed: LaborLawFile, version: int, digest: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": version,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "category_ids": list(CATEGORY_IDS),
        "content_hash": digest,
        "curated_by": parsed.curated_by,
        "reviewed_by": parsed.reviewed_by,
        "last_verified_on": parsed.last_verified_on.isoformat(),
        "schema_version": SCHEMA_VERSION,
    }
    if parsed.notes:
        payload["notes"] = parsed.notes
    return payload


def _next_version(stored: dict[str, Any] | None, digest: str) -> tuple[int, str]:
    """Decide the version from what Firestore already holds: (version, status)."""
    if stored is None:
        return 1, "new"
    version = int(stored["version"])
    if stored.get("content_hash") == digest:
        return version, "unchanged"
    return version + 1, "changed"


def load_country(
    client: Client, parsed: LaborLawFile, *, collection: str = LABOR_LAWS_COLLECTION
) -> LoadResult:
    """Write one country in a single batch so a crash never leaves it half-loaded."""
    country_ref = client.collection(collection).document(parsed.country)
    meta_ref = country_ref.collection("_meta").document("current")

    snapshot = meta_ref.get()
    digest = content_hash(parsed)
    version, status = _next_version(snapshot.to_dict() if snapshot.exists else None, digest)

    batch = client.batch()
    for category in CATEGORY_IDS:
        batch.set(
            country_ref.collection("rules").document(category), _rule_payload(parsed, category)
        )
    batch.set(country_ref, _header_payload(parsed))
    if status != "unchanged":
        batch.set(meta_ref, _meta_payload(parsed, version, digest))
    batch.commit()
    return LoadResult(parsed.country, version, status)


def load_labor_laws(
    client: Client,
    files: dict[str, LaborLawFile],
    *,
    collection: str = LABOR_LAWS_COLLECTION,
) -> list[LoadResult]:
    results: list[LoadResult] = []
    for country in COUNTRIES:
        if country not in files:
            continue
        result = load_country(client, files[country], collection=collection)
        log.info(
            "%s  %2d rules  version %d  %s",
            result.country,
            len(CATEGORY_IDS),
            result.version,
            result.status,
        )
        results.append(result)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load curated labor laws into Firestore.")
    parser.add_argument(
        "--input-dir", type=Path, default=LABOR_LAWS_DIR, help="Folder of <CC>.json files"
    )
    parser.add_argument("--only", nargs="+", choices=COUNTRIES, help="Load just these countries")
    parser.add_argument(
        "--collection", default=LABOR_LAWS_COLLECTION, help="Target Firestore collection"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    parser.add_argument(
        "--require-all", action="store_true", help="Fail if a country file is still a {} stub"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    files, skipped, problems = read_country_files(args.input_dir, args.only)

    for problem in problems:
        log.error(problem)
    for country in skipped:
        log.warning("%s.json is still an empty stub, skipped", country)
    if problems:
        log.error("Nothing was written: fix the files above and run again.")
        return 1
    if skipped and args.require_all:
        log.error("--require-all: %s not curated yet", ", ".join(skipped))
        return 1
    if not files:
        log.error("No curated files found in %s", args.input_dir)
        return 1

    for country in COUNTRIES:
        if country in files:
            log.info(
                "Validated %s: 15 rules, content hash %s",
                country,
                content_hash(files[country])[:12],
            )

    if args.dry_run:
        for country in COUNTRIES:
            if country in files:
                log.info(
                    "[dry-run] would write %s/%s: 15 rules + header (+ _meta if changed)",
                    args.collection,
                    country,
                )
        return 0

    results = load_labor_laws(get_firestore_client(), files, collection=args.collection)
    counts = {s: sum(r.status == s for r in results) for s in ("new", "changed", "unchanged")}
    log.info(
        "Loaded %d countries into %r: %d new, %d changed, %d unchanged",
        len(results),
        args.collection,
        counts["new"],
        counts["changed"],
        counts["unchanged"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
