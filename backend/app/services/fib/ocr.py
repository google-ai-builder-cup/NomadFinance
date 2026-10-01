"""Financial Identity Builder: bill photo reading (NF-P3-011), step 2a of the FIB pipeline.

One Gemini Vision call (extraction tier) turns a photo or PDF of a bill into an entry in
`users/{uid}/bills`, `source: "bill_ocr"`. Nothing is stored unless the file is a bill with a
readable amount and currency: both are required fields of an entry.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPIError
from google.genai import types

from app.config import get_settings
from app.integrations.cloud_storage import BillImageStore
from app.integrations.gemini import GeminiClient, ModelTier, model_for
from app.prompts.loader import load_prompt
from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.fib import (
    CURRENCY_PATTERN,
    MAX_VENDOR_CHARS,
    BillScanResponse,
    ExtractedBill,
)

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup.
EXTRACT_BILL_PROMPT = load_prompt("fib", "extract_bill", 1)

SOURCE = "bill_ocr"

# sniff_document_mime_type only ever returns one of these.
_EXTENSION: dict[str, str] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}


class NotABillError(Exception):
    """Gemini found no bill, invoice or receipt in the file (a selfie, a screenshot, ...)."""


class BillUnreadableError(Exception):
    """It is a bill, but the amount or the currency could not be read from it."""


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _valid_amount_and_currency(extracted: ExtractedBill) -> tuple[float, str]:
    currency = (extracted.currency or "").strip().upper()
    if (
        extracted.amount is None
        or extracted.amount <= 0
        or not re.match(CURRENCY_PATTERN, currency)
    ):
        raise BillUnreadableError("The amount or currency of the bill could not be read")
    return extracted.amount, currency


async def read_bill(data: bytes, mime_type: str, gemini: GeminiClient) -> ExtractedBill:
    """Read one bill file with Gemini Vision.

    Raises:
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    # A photo is one page and keeps the default timeout, so a hung attempt is retried after
    # 30 s, not 90 s; only a PDF's output grows with its page count.
    timeout = (
        get_settings().gemini_extraction_timeout_seconds if mime_type == "application/pdf" else None
    )
    return await gemini.generate_structured(
        operation=EXTRACT_BILL_PROMPT.key,
        tier=ModelTier.EXTRACTION,
        contents=[
            types.Part.from_bytes(data=data, mime_type=mime_type),
            EXTRACT_BILL_PROMPT.render_user(),
        ],
        response_model=ExtractedBill,
        system_instruction=EXTRACT_BILL_PROMPT.system,
        timeout_seconds=timeout,
    )


async def scan_bill(
    uid: str,
    data: bytes,
    mime_type: str,
    gemini: GeminiClient,
    fib: FibRepository,
    store: BillImageStore,
    now: datetime,
) -> BillScanResponse:
    """Read a bill photo and store it as a bill entry.

    The category Gemini suggests is stored as `category_source: "model"` without a
    `category_confidence`: the one confidence it returns is for amount and currency, not the
    category. Flash-Lite (NF-P3-012) sets that number when it categorizes.

    Raises:
        NotABillError: The file is not a bill.
        BillUnreadableError: No readable amount or currency; nothing is stored.
        GeminiError: Any Gemini failure.
    """
    extracted = await read_bill(data, mime_type, gemini)
    if not extracted.is_bill:
        raise NotABillError("No bill found in the file")
    amount, currency = _valid_amount_and_currency(extracted)

    bill_date = _parse_date(extracted.bill_date)
    paid_assumed = extracted.paid is None
    paid = bool(extracted.paid)
    # entry_date is the day it was paid, or the day it was logged if unpaid.
    entry_date = bill_date if paid and bill_date is not None else now.date()
    vendor = (extracted.vendor or "").strip()[:MAX_VENDOR_CHARS] or None

    kind: EntryKind = "bills"
    entry_id = await run_in_threadpool(fib.new_id, uid, kind)
    image_path: str | None = None
    try:
        image_path = await run_in_threadpool(
            store.upload, uid, entry_id, _EXTENSION[mime_type], data, mime_type
        )
    except GoogleAPIError:
        # The photo is a convenience copy: losing it must not lose the amount just read.
        logger.warning("fib_bill_image_upload_failed", exc_info=True)

    extraction: dict[str, object] = {
        "confidence": extracted.confidence,
        "model": model_for(ModelTier.EXTRACTION, get_settings()),
        "prompt_version": EXTRACT_BILL_PROMPT.version,
    }
    entry: dict[str, object] = {
        "entry_date": entry_date.isoformat(),
        "amount": amount,
        "currency": currency,
        "paid": paid,
        "source": SOURCE,
        "extraction": extraction,
    }
    if vendor:
        entry["vendor"] = vendor
    if bill_date is not None:
        entry["bill_date"] = bill_date.isoformat()
    if image_path is not None:
        entry["image_path"] = image_path
    if extracted.category is not None:
        entry["category"] = extracted.category
        entry["category_source"] = "model"

    await run_in_threadpool(fib.save_entry, uid, kind, entry_id, entry)
    logger.info(
        "fib_bill_scanned entry_date=%s paid=%s confidence=%.2f",
        entry_date,
        paid,
        extracted.confidence,
    )
    return BillScanResponse(
        entry_id=entry_id,
        entry_date=entry_date,
        amount=amount,
        currency=currency,
        vendor=vendor,
        bill_date=bill_date,
        paid=paid,
        category=extracted.category,
        category_source="model" if extracted.category is not None else None,
        notes=None,
        created_at=now,
        image_path=image_path,
        confidence=extracted.confidence,
        paid_assumed=paid_assumed,
    )
