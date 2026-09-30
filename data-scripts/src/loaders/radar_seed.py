"""Load the demo Exploitation Radar data into Firestore (NF-P3-005).

Run from data-scripts/:  python -m src.loaders.radar_seed
Writes, in one atomic batch:

    radar_reports/{seed_NN}       the reports in data/seed/radar-reports/seed_reports.json
    radar_entities/{slug}         each business's profile, worked out from those reports

Reports get `source: "seed"`, so they are never mistaken for worker reports. Profiles use the
same rating and risk rules as backend/app/services/radar/aggregation.py; keep the two in step.
Timestamps are set relative to the moment the loader runs (`hours_ago`), so the alert cron's
7-day window sees the reports as recent: run it shortly before a demo. Alerts are not written
here; the cron makes them. No embeddings either (that needs Gemini), so new worker reports
will not cluster with these.
"""

from __future__ import annotations

import argparse
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from src.config import RADAR_SEED_FILE
from src.firestore_client import get_firestore_client
from src.validators.radar_seed import SeedFile, SeedReport, load

log = logging.getLogger(__name__)

REPORTS_COLLECTION = "radar_reports"
ENTITIES_COLLECTION = "radar_entities"
SCHEMA_VERSION = 1

# Same numbers as backend/app/services/radar/aggregation.py.
MIN_INCIDENTS_TO_RATE = 2
MIN_INCIDENTS_TO_FLAG = 2
MIN_INCIDENTS_FOR_HIGH_RISK = 5
RATING_START = 5.0
RATING_STEP_PER_INCIDENT = 0.5


def report_document(report: SeedReport, now: datetime) -> dict[str, Any]:
    """The `radar_reports` document for one seed report."""
    doc: dict[str, Any] = {
        "entity_type": report.entity_type,
        "entity_name": report.entity_name,
        "entity_slug": report.entity_slug,
        "violation_type": report.violation_type,
        "host_country": report.host_country,
        "description": report.description,
        "language": report.language,
        "cluster_id": report.cluster_id,
        "source": "seed",
        # No model ran: fixed values that say so, like contract_signal reports.
        "validation": {"spam_score": 0, "category_confidence": 1, "model": "seed"},
        "created_at": now - timedelta(hours=report.hours_ago),
        "schema_version": SCHEMA_VERSION,
    }
    if report.corridor_id is not None:
        doc["corridor_id"] = report.corridor_id
    return doc


def _risk_level(incidents: int) -> str:
    if incidents >= MIN_INCIDENTS_FOR_HIGH_RISK:
        return "high"
    if incidents >= MIN_INCIDENTS_TO_FLAG:
        return "medium"
    return "low"


def entity_documents(seed: SeedFile, now: datetime) -> dict[str, dict[str, Any]]:
    """One `radar_entities` profile per business, keyed by slug."""
    by_slug: dict[str, list[SeedReport]] = {}
    for report in seed.reports:
        by_slug.setdefault(report.entity_slug, []).append(report)

    entities: dict[str, dict[str, Any]] = {}
    for slug, reports in by_slug.items():
        incidents = len({r.cluster_id for r in reports})
        times = [now - timedelta(hours=r.hours_ago) for r in reports]
        rating = (
            round(max(0.0, RATING_START - RATING_STEP_PER_INCIDENT * incidents), 1)
            if incidents >= MIN_INCIDENTS_TO_RATE
            else None
        )
        entities[slug] = {
            "name": reports[0].entity_name,
            "slug": slug,
            "entity_type": reports[0].entity_type,
            "aliases": [],
            "corridors": sorted({r.corridor_id for r in reports if r.corridor_id}),
            "host_countries": sorted({r.host_country for r in reports}),
            "report_count": len(reports),
            "incident_count": incidents,
            "violation_counts": dict(Counter(r.violation_type for r in reports)),
            "first_reported_at": min(times),
            "last_reported_at": max(times),
            "community_rating": rating,
            "risk_level": _risk_level(incidents),
            "flagged": incidents >= MIN_INCIDENTS_TO_FLAG,
            "updated_at": now,
            "schema_version": SCHEMA_VERSION,
        }
    return entities


def _has_real_reports(client: Client, slug: str) -> bool:
    """True if a non-seed report exists for this business (its profile is not ours to overwrite)."""
    query = client.collection(REPORTS_COLLECTION).where(
        filter=FieldFilter("entity_slug", "==", slug)
    )
    return any(doc.get("source") != "seed" for doc in query.stream())


def load_seed(client: Client, seed: SeedFile, now: datetime) -> tuple[int, int, int]:
    """Write reports and profiles in one batch; returns (reports, entities, stale removed).

    Re-running replaces the same document ids, so it never duplicates. A seed report that was
    removed from the file is deleted, so the collection matches the file. A profile is skipped
    when a real worker report exists for that business.
    """
    reports_ref = client.collection(REPORTS_COLLECTION)
    entities_ref = client.collection(ENTITIES_COLLECTION)
    keep = {r.id for r in seed.reports}
    stale = [
        doc.id
        for doc in reports_ref.where(filter=FieldFilter("source", "==", "seed")).stream()
        if doc.id not in keep
    ]

    batch = client.batch()
    for report in seed.reports:
        batch.set(reports_ref.document(report.id), report_document(report, now))
    for doc_id in stale:
        batch.delete(reports_ref.document(doc_id))
    written = 0
    for slug, entity in entity_documents(seed, now).items():
        if _has_real_reports(client, slug):
            log.warning("Skipped profile %s: it has real worker reports", slug)
            continue
        batch.set(entities_ref.document(slug), entity)
        written += 1
    batch.commit()
    return len(seed.reports), written, len(stale)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load demo radar reports into Firestore.")
    parser.add_argument("--input", type=Path, default=RADAR_SEED_FILE, help="Seed reports JSON")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firestore"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        seed = load(args.input)
    except ValidationError as exc:
        log.error("%s: %d problem(s)", args.input.name, exc.error_count())
        for err in exc.errors()[:10]:
            log.error("    %s: %s", ".".join(str(p) for p in err["loc"]), err["msg"])
        log.error("Nothing was written: fix the file and run again.")
        return 1
    except (ValueError, OSError) as exc:
        log.error("%s: %s", args.input.name, exc)
        return 1

    now = datetime.now(UTC)
    entities = entity_documents(seed, now)
    log.info("Validated %d reports for %d businesses", len(seed.reports), len(entities))
    if args.dry_run:
        for slug, entity in entities.items():
            log.info(
                "[dry-run] %s: %d report(s), %d incident(s), %s",
                slug,
                entity["report_count"],
                entity["incident_count"],
                entity["risk_level"],
            )
        return 0

    reports, written, removed = load_seed(get_firestore_client(), seed, now)
    log.info("Wrote %d reports and %d profiles, removed %d stale", reports, written, removed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
