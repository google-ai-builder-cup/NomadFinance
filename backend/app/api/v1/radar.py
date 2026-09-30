from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status

from app.config import Settings, get_settings
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user
from app.integrations.cloud_storage import RadarEvidenceStore, get_radar_evidence_store
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.radar_repo import RadarRepository, get_radar_repository
from app.schemas.radar_report import (
    RadarEvidenceResponse,
    RadarReportRequest,
    RadarReportResponse,
    RadarReportSummary,
)
from app.schemas.user import AuthenticatedUser
from app.services.radar.entity_reports import list_entity_reports
from app.services.radar.evidence import (
    MAX_EVIDENCE_FILES,
    NotTheReporterError,
    ReportNotFoundError,
    TooMuchEvidenceError,
    add_evidence,
)
from app.services.radar.intake import (
    AbusiveContentError,
    EntityUnknownError,
    LocationUnknownError,
    PersonalDataError,
    SpamDetectedError,
    submit_report,
)
from app.utils.validators import sniff_document_mime_type

router = APIRouter(prefix="/radar", tags=["radar"])

# Firestore's auto ids: 20 letters and digits. Anything else cannot be a report of ours.
ReportId = Annotated[str, Path(pattern=r"^[A-Za-z0-9]{20}$", description="The report's id.")]
# python-slugify's own output shape: lowercase words joined by single hyphens.
EntitySlug = Annotated[
    str, Path(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", description="The entity's slug.")
]

_REPORT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "Failed screening, or no entity/location in the form or the report"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy, unavailable or out of quota; see Retry-After"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/report",
    status_code=status.HTTP_201_CREATED,
    response_model=RadarReportResponse,
    responses=_REPORT_ERROR_RESPONSES,
    summary="Report a money transfer operator, recruitment agency or employer",
    dependencies=[Depends(limit_ai_calls)],
)
async def report(
    body: RadarReportRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
) -> RadarReportResponse:
    """Steps 2 to 7 of the radar pipeline: extract, screen, classify, embed, cluster, store.

    `entity_type`, `entity_name`, `corridor_id` and `host_country` are optional: send
    whatever the submission form collected, and Gemini fills in the rest from
    `description`. `violation_type` is not accepted here — it is always classified fresh
    from the report text (step 4), never a worker's own pick. A report that fails screening
    (spam, abusive content, or personal data) is refused with 422 and never stored; App
    Check / reCAPTCHA enforcement is wired separately (NF-P3-025).
    """
    try:
        return await submit_report(user.uid, body, gemini, radar, settings, datetime.now(UTC))
    except EntityUnknownError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Could not tell who this report is about. Add a business name.",
        ) from exc
    except LocationUnknownError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Could not tell where this happened. Add a corridor or the country you work in.",
        ) from exc
    except SpamDetectedError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This doesn't look like a real report. Please describe what happened.",
        ) from exc
    except AbusiveContentError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "This report cannot be published as written. Remove any threats or abusive language.",
        ) from exc
    except PersonalDataError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Please remove personal details (names, phone numbers, addresses) and try again.",
        ) from exc


@router.get(
    "/entities/{slug}/reports",
    response_model=list[RadarReportSummary],
    responses={401: {"description": "Missing or invalid Firebase ID token"}},
    summary="Every report about one business, newest first",
)
async def entity_reports(
    slug: EntitySlug,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
) -> list[RadarReportSummary]:
    """The individual reports behind one `radar_entities/{slug}` profile.

    The profile itself (name, `report_count`, `community_rating`, `risk_level`, `flagged`)
    is client-readable straight from Firestore (`firestore.rules`) and holds no personal
    data; `radar_reports` isn't, so this is how the entity profile page gets its report
    list. `reporter_hash` and the classification internals are never included. An unknown
    slug and an entity with no reports both answer an empty list — the two look the same
    from here.
    """
    return await list_entity_reports(slug, radar)


async def _read_evidence_upload(file: UploadFile, settings: Settings) -> tuple[bytes, str]:
    """The uploaded bytes and their real type, or the HTTP error for a file we cannot take."""
    # Read one byte past the limit so an oversized file is detected without loading all of it.
    data = await file.read(settings.upload_max_bytes + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if len(data) > settings.upload_max_bytes:
        limit_mb = settings.upload_max_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"The file is larger than {limit_mb} MB."
        )
    mime_type = sniff_document_mime_type(data)
    if mime_type is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).",
        )
    return data, mime_type


_EVIDENCE_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    403: {"description": "This report wasn't filed by you"},
    404: {"description": "No such report, or it has no reporter to check ownership against"},
    413: {"description": "File larger than the upload limit (default 10 MB)"},
    415: {"description": "Not a PDF, PNG, JPEG, WebP or HEIC/HEIF file"},
    422: {"description": f"Already has the maximum of {MAX_EVIDENCE_FILES} attachments"},
    429: {"description": "Too many requests. Please wait a minute and try again."},
}


@router.post(
    "/report/{report_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    response_model=RadarEvidenceResponse,
    responses=_EVIDENCE_RESPONSES,
    summary="Attach a photo or screenshot to a report you filed",
)
async def report_evidence(
    report_id: ReportId,
    file: Annotated[UploadFile, File(description="Evidence as PDF, PNG, JPEG, WebP or HEIC")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    radar: Annotated[RadarRepository, Depends(get_radar_repository)],
    store: Annotated[RadarEvidenceStore, Depends(get_radar_evidence_store)],
) -> RadarEvidenceResponse:
    """Add one attachment to a report you filed yourself (`POST /radar/report`).

    A separate call, not a field on the report itself: it needs the report's own id first,
    and lets you attach evidence after the fact. Only the worker who filed the report can
    add to it — checked by re-hashing your uid, never by storing who filed what. At most 5
    attachments per report. A `contract_signal` or `seed` report (no `reporter_hash`) always
    answers 404: there is no worker to check ownership against.
    """
    data, content_type = await _read_evidence_upload(file, settings)
    try:
        return await add_evidence(
            user.uid,
            report_id,
            content_type,
            data,
            radar,
            store,
            settings.radar_reporter_hash_secret.get_secret_value(),
        )
    except ReportNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such report.") from exc
    except NotTheReporterError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This report wasn't filed by you.") from exc
    except TooMuchEvidenceError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Already has the maximum of {MAX_EVIDENCE_FILES} attachments.",
        ) from exc
