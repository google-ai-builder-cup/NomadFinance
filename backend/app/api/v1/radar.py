from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.core.rate_limit import limit_ai_calls
from app.dependencies import get_current_user
from app.integrations.gemini import GeminiClient, get_gemini_client
from app.repositories.radar_repo import RadarRepository, get_radar_repository
from app.schemas.radar_report import RadarReportRequest, RadarReportResponse
from app.schemas.user import AuthenticatedUser
from app.services.radar.intake import (
    AbusiveContentError,
    EntityUnknownError,
    LocationUnknownError,
    PersonalDataError,
    SpamDetectedError,
    submit_report,
)

router = APIRouter(prefix="/radar", tags=["radar"])

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
    """Steps 2 to 4 and 7 of the radar pipeline: extract, screen, classify, store.

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
