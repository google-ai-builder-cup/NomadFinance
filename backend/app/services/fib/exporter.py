"""Financial Identity PDF export (NF-P3-014): the portable report a worker can hand to a lender.

Renders the stored `financial_profile/current` (it does not recompute it), keeps the PDF in
Cloud Storage under `exports/{uid}/`, records it as `latest_export`, and hands back a signed
link. Links are made on request and never stored (fib.md).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.integrations.cloud_storage import ExportStore
from app.repositories.fib_repo import FibRepository
from app.schemas.fib_export import ExportReportResponse
from app.services.fib.report_html import build_report_html
from app.services.fib.report_labels import LABELS

logger = logging.getLogger(__name__)

DOWNLOAD_NAME = "financial-identity-report.pdf"


class NoProfileError(Exception):
    """The worker has no `financial_profile/current` yet (the weekly recompute has not run)."""


class NoExportError(Exception):
    """The worker has not exported a report yet."""


def render_pdf(html: str) -> bytes:
    """Render the report HTML to PDF bytes. Blocking and CPU-bound: call it in a thread."""
    # Imported here, not at module level: weasyprint loads Pango when imported, and a missing
    # system library must fail the export, not stop the whole API from starting.
    from weasyprint import HTML  # type: ignore[import-untyped]

    def refuse(url: str, *args: Any, **kwargs: Any) -> Any:
        raise ValueError(f"The report may not load {url}")

    return bytes(HTML(string=html, url_fetcher=refuse).write_pdf())


def _language(profile: dict[str, Any]) -> str:
    language = profile.get("narrative", {}).get("language")
    return str(language) if language in LABELS else "en"


async def _link(
    uid: str,
    profile: dict[str, Any],
    path: str,
    created_at: datetime,
    now: datetime,
    expires_in: timedelta,
    store: ExportStore,
) -> ExportReportResponse:
    url = await run_in_threadpool(store.signed_url, uid, path, expires_in, DOWNLOAD_NAME)
    return ExportReportResponse(
        download_url=url,
        expires_at=now + expires_in,
        created_at=created_at,
        language=_language(profile),
        filename=DOWNLOAD_NAME,
    )


async def export_report(
    uid: str,
    holder_name: str | None,
    fib: FibRepository,
    store: ExportStore,
    now: datetime,
    expires_in: timedelta,
) -> ExportReportResponse:
    """Render, store and link a new report. The previous export is deleted afterwards, so a
    worker has at most one PDF.

    Raises:
        NoProfileError: There is no profile to print.
    """
    profile = await run_in_threadpool(fib.get_profile, uid)
    if profile is None:
        raise NoProfileError("No financial profile yet")

    html = build_report_html(profile, holder_name, now)
    pdf = await run_in_threadpool(render_pdf, html)
    path = await run_in_threadpool(
        store.upload, uid, f"financial-identity-{now:%Y%m%dT%H%M%SZ}.pdf", pdf
    )
    try:
        await run_in_threadpool(
            fib.set_latest_export, uid, {"storage_path": path, "created_at": now}
        )
    except GoogleAPICallError:
        # Never leave a file the profile does not point to.
        await run_in_threadpool(store.delete, uid, path)
        raise

    previous = (profile.get("latest_export") or {}).get("storage_path")
    if previous and previous != path:
        try:
            await run_in_threadpool(store.delete, uid, previous)
        except (GoogleAPICallError, ValueError):
            logger.warning("fib_export_previous_not_deleted", exc_info=True)

    logger.info("fib_report_exported language=%s size_bytes=%d", _language(profile), len(pdf))
    return await _link(uid, profile, path, now, now, expires_in, store)


async def latest_report_link(
    uid: str, fib: FibRepository, store: ExportStore, now: datetime, expires_in: timedelta
) -> ExportReportResponse:
    """A fresh link to the worker's latest export, without rendering it again.

    Raises:
        NoExportError: Nothing has been exported yet.
    """
    profile = await run_in_threadpool(fib.get_profile, uid)
    export = (profile or {}).get("latest_export")
    if profile is None or not export:
        raise NoExportError("No report exported yet")
    return await _link(
        uid, profile, export["storage_path"], export["created_at"], now, expires_in, store
    )
