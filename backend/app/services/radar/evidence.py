"""Exploitation Radar evidence attachments (NF-P3-004 follow-on): a worker attaches a photo
or screenshot to a report they already filed.

A separate call from `POST /radar/report`, not a field on it: `radar-evidence/{report_id}/`
needs a real report id first, and a worker may want to attach evidence after the fact (a
follow-up screenshot) without resubmitting the whole report. Ownership is checked by
re-hashing the caller's uid and comparing it to the report's own `reporter_hash` — the same
HMAC that exists for anonymity in the first place, never a stored uid-to-report mapping.
"""

from __future__ import annotations

import uuid

from fastapi.concurrency import run_in_threadpool

from app.integrations.cloud_storage import RadarEvidenceStore
from app.repositories.radar_repo import RadarRepository
from app.schemas.radar_report import RadarEvidenceResponse
from app.utils.hashing import hash_reporter

# No calibration behind this; a round number to stop one report from becoming an unbounded
# photo dump. Easy to raise later.
MAX_EVIDENCE_FILES = 5

# sniff_document_mime_type only ever returns one of these; the extension is for a human
# looking at the bucket, Content-Type on the blob is what actually matters for serving it.
_EXTENSION: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


class ReportNotFoundError(Exception):
    """No such report, or it wasn't filed by a worker (no `reporter_hash` to check
    ownership against: a `contract_signal` or `seed` report)."""


class NotTheReporterError(Exception):
    """The caller's uid does not hash to this report's stored `reporter_hash`."""


class TooMuchEvidenceError(Exception):
    """The report already has `MAX_EVIDENCE_FILES` attachments."""


async def add_evidence(
    uid: str,
    report_id: str,
    content_type: str,
    data: bytes,
    radar: RadarRepository,
    store: RadarEvidenceStore,
    reporter_hash_secret: str,
) -> RadarEvidenceResponse:
    """Verify ownership, upload the file, and record its path on the report.

    Raises:
        ReportNotFoundError: No such report, or no `reporter_hash` to check against.
        NotTheReporterError: The caller isn't who filed this report.
        TooMuchEvidenceError: Already at the cap.
    """
    report = await run_in_threadpool(radar.get, report_id)
    if report is None or not report.get("reporter_hash"):
        raise ReportNotFoundError(report_id)
    if report["reporter_hash"] != hash_reporter(uid, reporter_hash_secret):
        raise NotTheReporterError(report_id)
    existing: list[str] = report.get("evidence_paths") or []
    if len(existing) >= MAX_EVIDENCE_FILES:
        raise TooMuchEvidenceError(report_id)

    filename = f"{uuid.uuid4().hex}.{_EXTENSION[content_type]}"
    path = await run_in_threadpool(store.upload, report_id, filename, data, content_type)
    await run_in_threadpool(radar.add_evidence_path, report_id, path)
    return RadarEvidenceResponse(report_id=report_id, evidence_paths=[*existing, path])
