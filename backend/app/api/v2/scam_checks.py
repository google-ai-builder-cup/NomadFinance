from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from fastapi.exceptions import RequestValidationError

from app.core.errors import ApiError
from app.core.rate_limit import limit_ai_calls
from app.dependencies import (
    get_current_user,
    get_scam_check_store,
    get_scam_reporter,
    require_flag,
)
from app.schemas.scam import (
    ScamCheckDetail,
    ScamCheckListResponse,
    ScamReportRequest,
    ScamReportResponse,
)
from app.schemas.user import AuthenticatedUser
from app.services.scam.check_store import CheckStore
from app.services.scam.history import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    CheckNotFoundError,
    InvalidCursorError,
    get_check,
    list_checks,
)
from app.services.scam.report import IndicatorsNotInCheckError, NotAScamError, ScamReporter

# The same guard as the analyze route: a missing token is a 401 first, and a caller without the
# `scam` flag gets the 404 an unknown path gets (docs/api/v2-scam.md).
router = APIRouter(prefix="/scam", tags=["scam"], dependencies=[Depends(require_flag("scam"))])

_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, expired or revoked token"},
    404: {"description": "The `scam` flag is off for the caller"},
    429: {"description": "More than 60 calls a minute; see Retry-After"},
}


@router.get(
    "/checks",
    response_model=ScamCheckListResponse,
    responses={
        **_RESPONSES,
        400: {"description": "The cursor is not one this worker was given (`invalid_cursor`)"},
        422: {"description": "`limit` outside 1 to 100"},
    },
    summary="The worker's scam-check history, newest first",
)
async def list_scam_checks(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    store: Annotated[CheckStore, Depends(get_scam_check_store)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> ScamCheckListResponse:
    """The checks this worker made, newest first, a page at a time.

    Each row is what a history screen needs: the verdict's headline, the first 140 characters of
    the masked text and whether the worker already warned others. Pass the `next_cursor` of a
    page as `cursor` for the next one; `null` means the end. A check past its expiry is not
    listed.
    """
    try:
        return await list_checks(store, user.uid, limit=limit, cursor=cursor, now=datetime.now(UTC))
    except InvalidCursorError as exc:
        raise ApiError(
            400, "invalid_cursor", "The cursor is not valid. Start from the top."
        ) from exc


@router.get(
    "/checks/{check_id}",
    response_model=ScamCheckDetail,
    responses={**_RESPONSES, 404: {"description": "Flag off, or no such check of the caller's"}},
    summary="One stored scam check",
)
async def get_scam_check(
    check_id: str,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    store: Annotated[CheckStore, Depends(get_scam_check_store)],
) -> ScamCheckDetail:
    """One of the worker's checks, as the analyze answer gave it (without `cached`).

    `indicators[].seen` is read when the check is shown, so a number reported since the check
    was made shows its current count. A check that does not exist, has expired or belongs to
    someone else is the same `404`, so a stranger cannot learn which ids exist.
    """
    try:
        return await get_check(store, user.uid, check_id, datetime.now(UTC))
    except CheckNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc


@router.post(
    "/checks/{check_id}/report",
    response_model=ScamReportResponse,
    status_code=201,
    responses={
        **_RESPONSES,
        200: {"model": ScamReportResponse, "description": "The check had been reported already"},
        404: {"description": "Flag off, or no such check of the caller's"},
        409: {"description": "The check's verdict is not a scam (`not_a_scam`)"},
        422: {
            "description": "An indicator not in the check, a repeat, more than 10, or a bad text"
        },
        429: {"description": "Too many AI calls (default 10 a minute per user); see Retry-After"},
    },
    dependencies=[Depends(limit_ai_calls)],
    summary="Warn other workers: report a scam check to Exploitation Radar",
)
async def report_scam_check(
    check_id: str,
    body: ScamReportRequest,
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    reporter: Annotated[ScamReporter, Depends(get_scam_reporter)],
) -> ScamReportResponse:
    """Report the scam in one of the worker's checks, exactly as the confirmation sheet showed.

    Only the `indicator_ids` the worker left ticked and the text they confirmed (masked again
    here) are sent to Radar; no uid, reporter hash, check id or raw message is stored with the
    report. A check is reported once: a repeat returns the first report with `200` and
    `already_reported: true`, and counts nothing a second time. The Radar profile of the scam
    type is `/radar/entity/{entity_slug}`.
    """
    try:
        outcome = await reporter.report(user.uid, check_id, body)
    except CheckNotFoundError as exc:
        raise ApiError(404, "not_found", "Not Found") from exc
    except NotAScamError as exc:
        raise ApiError(
            409, "not_a_scam", "Only a message that was judged a scam can be reported."
        ) from exc
    except IndicatorsNotInCheckError as exc:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("body", "indicator_ids"),
                    "msg": f"Unknown indicator: {exc}",
                }
            ]
        ) from exc
    response.status_code = 201 if outcome.created else 200
    return outcome.response
