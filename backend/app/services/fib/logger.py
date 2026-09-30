"""Financial Identity Builder: manual activity logging (NF-P3-010).

Three entry types, one pattern each, mirroring `services/remittance/logger.py`'s own
`log_transfer` (the first writer into this same repository, for `transfers`). No Gemini
call: a category here is always `category_source: "user"`, whatever the worker chose (or
none at all) — Flash-Lite categorization (NF-P3-012) and bill-photo OCR (NF-P3-011) are
their own, later endpoints, writing into the same collections through the same repository.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.fib import (
    BillLogRequest,
    BillLogResponse,
    IncomeLogRequest,
    IncomeLogResponse,
    SavingsLogRequest,
    SavingsLogResponse,
)

logger = logging.getLogger(__name__)

SOURCE = "manual"


async def log_income(
    uid: str, body: IncomeLogRequest, fib: FibRepository, now: datetime
) -> IncomeLogResponse:
    """Store one income entry. Always `category_source: "user"`, `verified: false` — a
    contract-verified income line is NF-P3-024's own write, not this endpoint's."""
    kind: EntryKind = "income"
    entry_date = body.entry_date or now.date()
    entry_id = await run_in_threadpool(fib.new_id, uid, kind)

    data: dict[str, object] = {
        "entry_date": entry_date.isoformat(),
        "amount": body.amount,
        "currency": body.currency,
        "category": body.category,
        "category_source": "user",
        "verified": False,
        "source": SOURCE,
    }
    if body.employer_name:
        data["employer_name"] = body.employer_name
    if body.notes:
        data["notes"] = body.notes

    await run_in_threadpool(fib.save_entry, uid, kind, entry_id, data)
    logger.info("fib_income_logged entry_date=%s category=%s", entry_date, body.category)
    return IncomeLogResponse(
        entry_id=entry_id,
        entry_date=entry_date,
        amount=body.amount,
        currency=body.currency,
        category=body.category,
        category_source="user",
        employer_name=body.employer_name,
        verified=False,
        notes=body.notes,
        created_at=now,
    )


async def log_bill(
    uid: str, body: BillLogRequest, fib: FibRepository, now: datetime
) -> BillLogResponse:
    """Store one bill entry. A category is optional here; uncategorized entries wait for
    Flash-Lite (NF-P3-012), the same as any other source."""
    kind: EntryKind = "bills"
    entry_date = body.entry_date or now.date()
    entry_id = await run_in_threadpool(fib.new_id, uid, kind)

    data: dict[str, object] = {
        "entry_date": entry_date.isoformat(),
        "amount": body.amount,
        "currency": body.currency,
        "paid": body.paid,
        "source": SOURCE,
    }
    if body.vendor:
        data["vendor"] = body.vendor
    if body.bill_date is not None:
        data["bill_date"] = body.bill_date.isoformat()
    if body.category is not None:
        data["category"] = body.category
        data["category_source"] = "user"
    if body.notes:
        data["notes"] = body.notes

    await run_in_threadpool(fib.save_entry, uid, kind, entry_id, data)
    logger.info("fib_bill_logged entry_date=%s paid=%s", entry_date, body.paid)
    return BillLogResponse(
        entry_id=entry_id,
        entry_date=entry_date,
        amount=body.amount,
        currency=body.currency,
        vendor=body.vendor,
        bill_date=body.bill_date,
        paid=body.paid,
        category=body.category,
        category_source="user" if body.category is not None else None,
        notes=body.notes,
        created_at=now,
    )


async def log_savings(
    uid: str, body: SavingsLogRequest, fib: FibRepository, now: datetime
) -> SavingsLogResponse:
    """Store one savings entry (a deposit or a withdrawal, always a positive amount)."""
    kind: EntryKind = "savings"
    entry_date = body.entry_date or now.date()
    entry_id = await run_in_threadpool(fib.new_id, uid, kind)

    data: dict[str, object] = {
        "entry_date": entry_date.isoformat(),
        "amount": body.amount,
        "currency": body.currency,
        "direction": body.direction,
        "source": SOURCE,
    }
    if body.account_type is not None:
        data["account_type"] = body.account_type
    if body.notes:
        data["notes"] = body.notes

    await run_in_threadpool(fib.save_entry, uid, kind, entry_id, data)
    logger.info("fib_savings_logged entry_date=%s direction=%s", entry_date, body.direction)
    return SavingsLogResponse(
        entry_id=entry_id,
        entry_date=entry_date,
        amount=body.amount,
        currency=body.currency,
        direction=body.direction,
        account_type=body.account_type,
        notes=body.notes,
        created_at=now,
    )
