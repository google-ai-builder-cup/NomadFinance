"""Upload the demo sample contracts to Cloud Storage (NF-P3-020).

Run from data-scripts/:  python -m src.loaders.sample_contracts
Writes `demo-samples/contracts/{file}.pdf` in the project's default bucket, one object per
contract in data/seed/contracts/manifest.json. The folder is not one of the per-user folders in
frontend/storage.rules, so browsers cannot read it: the team downloads the files through the
Firebase console or `gcloud storage cp`, then uploads them in the app like a worker would.

Running again is safe: an object whose content and metadata already match is left alone, a
changed file is replaced, and an object no longer in the manifest is deleted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import Any

from firebase_admin import storage  # type: ignore[import-untyped]
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError
from pydantic import ValidationError

from src.config import SEED_CONTRACTS_DIR
from src.firestore_client import get_firebase_app
from src.validators.sample_contract import Manifest, SampleContract, load

log = logging.getLogger(__name__)

PREFIX = "demo-samples/contracts/"
DEFAULT_BUCKET = "nomadfinance-prod.firebasestorage.app"


def object_metadata(contract: SampleContract) -> dict[str, str]:
    """Custom metadata shown in the console, so a file's purpose is visible without the manifest."""
    meta = {
        "country": contract.country,
        "job_type": contract.job_type,
        "worker_language": contract.worker_language,
        "overall": contract.overall,
        "synthetic": "true",
    }
    if contract.radar_entity_slug:
        meta["radar_entity_slug"] = contract.radar_entity_slug
    return meta


def _md5(data: bytes) -> str:
    return base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode()


def upload_all(bucket: Any, manifest: Manifest, directory: Path) -> tuple[int, int, int]:
    """Sync the bucket folder to the manifest; returns (uploaded, unchanged, deleted)."""
    uploaded = unchanged = 0
    wanted = set()
    for contract in manifest.contracts:
        name = PREFIX + contract.file
        wanted.add(name)
        data = (directory / contract.file).read_bytes()
        meta = object_metadata(contract)
        blob = bucket.get_blob(name)
        if blob is not None and blob.md5_hash == _md5(data) and (blob.metadata or {}) == meta:
            unchanged += 1
            continue
        blob = bucket.blob(name)
        blob.metadata = meta
        blob.upload_from_string(data, content_type="application/pdf")
        uploaded += 1
        log.info("uploaded %s (%d bytes)", name, len(data))
    # List first: deleting while paging through the listing can skip objects.
    stale = [b for b in list(bucket.list_blobs(prefix=PREFIX)) if b.name not in wanted]
    for blob in stale:
        blob.delete()
        log.info("deleted %s (not in the manifest)", blob.name)
    return uploaded, unchanged, len(stale)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload the demo sample contracts.")
    parser.add_argument("--input-dir", type=Path, default=SEED_CONTRACTS_DIR)
    parser.add_argument(
        "--bucket",
        default=os.environ.get("FIREBASE_STORAGE_BUCKET", DEFAULT_BUCKET),
        help="Target bucket (default: FIREBASE_STORAGE_BUCKET or the project's default bucket)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only; no network access")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        manifest = load(args.input_dir)
    except ValidationError as exc:
        for err in exc.errors():
            log.error("%s: %s", ".".join(str(p) for p in err["loc"]), err["msg"])
        return 1
    except (ValueError, OSError) as exc:
        log.error("%s", exc)
        return 1
    log.info("%d contracts checked", len(manifest.contracts))
    if args.dry_run:
        for c in manifest.contracts:
            log.info("would upload gs://%s/%s%s", args.bucket, PREFIX, c.file)
        return 0

    try:
        bucket = storage.bucket(args.bucket, app=get_firebase_app())
        uploaded, unchanged, deleted = upload_all(bucket, manifest, args.input_dir)
    except DefaultCredentialsError:
        log.error("No Google credentials: run `gcloud auth application-default login` first")
        return 1
    except GoogleAPIError as exc:
        log.error("Cloud Storage refused the request: %s", exc)
        return 1
    log.info("done: %d uploaded, %d unchanged, %d deleted", uploaded, unchanged, deleted)
    return 0


if __name__ == "__main__":
    sys.exit(main())
