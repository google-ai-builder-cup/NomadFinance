from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from app.api.v1.contract_analysis import read_contract_upload
from app.config import Settings, get_settings
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user, get_feature_flag_service
from app.integrations.cloud_storage import (
    BillImageStore,
    ExportStore,
    get_bill_image_store,
    get_export_store,
)
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.coach_session_repo import CoachPlanRepository, get_coach_plan_repository
from app.repositories.fib_repo import FibRepository, get_fib_repository
from app.repositories.rate_repo import RateRepository, get_rate_repository
from app.repositories.scam_check_repo import ScamCheckRepository, get_scam_check_repository
from app.repositories.user_repo import UserRepository, get_user_repository
from app.schemas.fib import (
    BillLogRequest,
    BillLogResponse,
    BillScanResponse,
    FibCategorizeResponse,
    IncomeLogRequest,
    IncomeLogResponse,
    SavingsLogRequest,
    SavingsLogResponse,
)
from app.schemas.fib_activity import ActivityFeedResponse
from app.schemas.fib_export import ExportReportRequest, ExportReportResponse
from app.schemas.fib_profile import RefreshProfileResponse
from app.schemas.user import AuthenticatedUser
from app.services.coach.plan_goals import newest_plan_goals
from app.services.feature_flag_service import FeatureFlagService
from app.services.fib.activity_feed import build_feed
from app.services.fib.categorizer import categorize_pending
from app.services.fib.exporter import (
    NoExportError,
    NoProfileError,
    export_report,
    latest_report_link,
)
from app.services.fib.logger import log_bill, log_income, log_savings
from app.services.fib.ocr import BillUnreadableError, NotABillError, scan_bill
from app.services.fib.profile_builder import refresh_profile
from app.services.fib.signals import SignalReader, sharing_of

router = APIRouter(prefix="/fib", tags=["fib"])

_LOG_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    422: {"description": "Invalid body"},
    429: {"description": "Too many requests. Please wait a minute and try again."},
}


@router.post(
    "/income",
    status_code=status.HTTP_201_CREATED,
    response_model=IncomeLogResponse,
    responses=_LOG_ERROR_RESPONSES,
    summary="Log a manual income entry",
)
async def log_income_entry(
    body: IncomeLogRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
) -> IncomeLogResponse:
    """Store one entry under `users/{uid}/income`. No Gemini call, so only the API-wide rate
    limit applies. `category` is required and always `category_source: "user"` here."""
    return await log_income(user.uid, body, fib, datetime.now(UTC))


@router.post(
    "/bill",
    status_code=status.HTTP_201_CREATED,
    response_model=BillLogResponse,
    responses=_LOG_ERROR_RESPONSES,
    summary="Log a manual bill entry",
)
async def log_bill_entry(
    body: BillLogRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
) -> BillLogResponse:
    """Store one entry under `users/{uid}/bills`. Manual entry only — a bill photo is
    read by `POST /fib/bill/scan`, writing into the same collection."""
    return await log_bill(user.uid, body, fib, datetime.now(UTC))


@router.post(
    "/savings",
    status_code=status.HTTP_201_CREATED,
    response_model=SavingsLogResponse,
    responses=_LOG_ERROR_RESPONSES,
    summary="Log a manual savings entry",
)
async def log_savings_entry(
    body: SavingsLogRequest,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
) -> SavingsLogResponse:
    """Store one entry under `users/{uid}/savings`. No Gemini call, so only the API-wide
    rate limit applies."""
    return await log_savings(user.uid, body, fib, datetime.now(UTC))


_SCAN_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Empty file"},
    401: {"description": "Missing or invalid Firebase ID token"},
    413: {"description": "File larger than the upload limit (default 10 MB)"},
    415: {"description": "Not a PDF, PNG, JPEG, WebP or HEIC/HEIF file"},
    422: {"description": "No bill in the file, or no readable amount or currency"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/bill/scan",
    status_code=status.HTTP_201_CREATED,
    response_model=BillScanResponse,
    responses=_SCAN_ERROR_RESPONSES,
    summary="Read a bill photo and log it",
    dependencies=[Depends(limit_ai_calls)],
)
async def scan_bill_photo(
    file: Annotated[UploadFile, File(description="Bill as PDF, PNG, JPEG, WebP or HEIC")],
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    store: Annotated[BillImageStore, Depends(get_bill_image_store)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BillScanResponse:
    """Read a photo or PDF of a bill and store it under `users/{uid}/bills`.

    Gemini Vision reads the amount, currency, vendor, bill date, whether it was paid and a
    suggested category. Nothing is stored unless the file is a bill with a readable amount
    and currency (422). `paid_assumed` is true when the bill did not say and `paid` is false
    by default. The photo is kept in Cloud Storage; `image_path` is null if that failed.
    """
    data, mime_type = await read_contract_upload(file, settings)
    try:
        return await scan_bill(user.uid, data, mime_type, gemini, fib, store, datetime.now(UTC))
    except NotABillError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No bill found. Upload a clear photo or PDF of the bill or receipt.",
        ) from exc
    except BillUnreadableError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "The amount or currency could not be read. Take a clearer photo with the whole "
            "bill in view, or enter it by hand.",
        ) from exc


_CATEGORIZE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    502: {"description": "Gemini returned an unusable answer"},
    503: {"description": "Gemini busy or unavailable; retry after the Retry-After header"},
    504: {"description": "Gemini timed out"},
}


@router.post(
    "/categorize",
    response_model=FibCategorizeResponse,
    responses=_CATEGORIZE_ERROR_RESPONSES,
    summary="Categorize your uncategorized entries",
    dependencies=[Depends(limit_ai_calls)],
)
async def categorize_entries(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
) -> FibCategorizeResponse:
    """Give a category and a confidence to your income and bill entries that have none.

    Pending means no category yet, or a category from a bill photo that has no confidence.
    A category you chose yourself is never changed. At most 100 entries are handled per call,
    oldest first; `remaining` says how many are left, and calling again continues. Calling when
    nothing is pending makes no Gemini call.
    """
    return await categorize_pending(user.uid, gemini, fib)


_EXPORT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing or invalid Firebase ID token"},
    404: {"description": "No profile to export yet, or nothing exported yet"},
    422: {"description": "Invalid body"},
    429: {"description": "Too many requests. Please wait a minute and try again."},
}


@router.post(
    "/report/export",
    status_code=status.HTTP_201_CREATED,
    response_model=ExportReportResponse,
    responses=_EXPORT_ERROR_RESPONSES,
    summary="Export your Financial Identity report as a PDF",
)
async def export_financial_report(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    store: Annotated[ExportStore, Depends(get_export_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    body: ExportReportRequest | None = None,
) -> ExportReportResponse:
    """Make a PDF of your current Financial Identity profile and return a signed download link.

    The PDF is the profile as last computed (weekly); it shows that date. It is written in the
    language of the profile's report text. `holder_name` is optional, printed on the PDF only
    and never stored. A new export replaces the previous PDF. The link works for
    `EXPORT_URL_EXPIRY_MINUTES` (default 24 hours) and gives the PDF to anyone who has it.

    The Coach check-ins and scam checks appear only while `signal_sharing` says so at the
    moment of the export (NF-HR-001), whatever the stored profile still holds.
    """
    try:
        return await export_report(
            user.uid,
            body.holder_name if body else None,
            fib,
            store,
            datetime.now(UTC),
            timedelta(minutes=settings.export_url_expiry_minutes),
            sharing_of(await run_in_threadpool(users.get_profile, user.uid)),
        )
    except NoProfileError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No Financial Identity profile yet. It is computed weekly from your logged activity.",
        ) from exc


@router.get(
    "/report/export",
    response_model=ExportReportResponse,
    responses=_EXPORT_ERROR_RESPONSES,
    summary="Get a new download link for your latest exported report",
)
async def latest_financial_report(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    store: Annotated[ExportStore, Depends(get_export_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> ExportReportResponse:
    """A fresh signed link to the PDF you exported last, without making it again.

    A PDF that holds Coach or scam-check activity you have since stopped sharing is not linked:
    export again to get one without it (404 until then).
    """
    try:
        return await latest_report_link(
            user.uid,
            fib,
            store,
            datetime.now(UTC),
            timedelta(minutes=settings.export_url_expiry_minutes),
            sharing_of(await run_in_threadpool(users.get_profile, user.uid)),
        )
    except NoExportError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report has been exported yet.") from exc


@router.get(
    "/activity",
    response_model=ActivityFeedResponse,
    responses={
        401: {"description": "Missing or invalid Firebase ID token"},
        422: {"description": "`days` or `limit` out of range"},
    },
    summary="Your activity in one list: money log, Coach plan and check-ins, scam checks",
)
async def activity_feed(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
    scam_checks: Annotated[ScamCheckRepository, Depends(get_scam_check_repository)],
    flags: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
    days: Annotated[int, Query(ge=1, le=365)] = 90,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ActivityFeedResponse:
    """Your income, transfers, bills and savings entries, your Coach plans and check-in
    answers, and your scam checks, newest first.

    Coach events appear while the `coach` flag is on for you, scam checks while `scam` is. Each
    item is a kind, a day and fixed fields; no note, message or typed answer is in it. This is
    your own view and does not depend on `signal_sharing`, which is only about reports.
    """
    return await build_feed(
        user.uid,
        days=days,
        limit=limit,
        now=datetime.now(UTC),
        fib=fib,
        plans=plans,
        scam_checks=scam_checks,
        flags=flags,
    )


@router.post(
    "/profile/refresh",
    response_model=RefreshProfileResponse,
    dependencies=[Depends(limit_ai_calls)],
    responses={
        **_LOG_ERROR_RESPONSES,
        502: {"description": "Gemini returned an unusable answer"},
        503: {"description": "Gemini busy, unavailable or out of quota"},
        504: {"description": "Gemini timed out"},
    },
    summary="Work out your Financial Identity score now",
)
async def refresh_financial_profile(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    fib: Annotated[FibRepository, Depends(get_fib_repository)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    rates: Annotated[RateRepository, Depends(get_rate_repository)],
    gemini: Annotated[GeminiClient, Depends(get_gemini_client)],
    plans: Annotated[CoachPlanRepository, Depends(get_coach_plan_repository)],
    scam_checks: Annotated[ScamCheckRepository, Depends(get_scam_check_repository)],
    flags: Annotated[FeatureFlagService, Depends(get_feature_flag_service)],
) -> RefreshProfileResponse:
    """Compute your profile now instead of waiting for the weekly run.

    The weekly job stays the way every profile is kept up to date; this is for the first one,
    so a new worker does not wait up to a week to see a score. One call writes the metrics and
    the report text (a reasoning-tier call, usually 20 to 40 seconds). A profile computed in the
    last hour is returned as it is, so pressing the button again costs nothing.
    """
    now = datetime.now(UTC)
    return await refresh_profile(
        user.uid,
        gemini,
        fib,
        users,
        rates,
        now,
        newest_plan_goals(plans),
        SignalReader(plans, scam_checks, flags),
    )
