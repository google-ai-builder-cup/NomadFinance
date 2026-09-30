from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.repositories.fib_repo import FibRepository, get_fib_repository
from app.schemas.fib import (
    BillLogRequest,
    BillLogResponse,
    IncomeLogRequest,
    IncomeLogResponse,
    SavingsLogRequest,
    SavingsLogResponse,
)
from app.schemas.user import AuthenticatedUser
from app.services.fib.logger import log_bill, log_income, log_savings

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
    """Store one entry under `users/{uid}/bills`. Manual entry only — a bill photo read by
    Gemini Vision is NF-P3-011's own endpoint, writing into the same collection."""
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
