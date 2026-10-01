from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest
from google.api_core.exceptions import Forbidden

from app.integrations.cloud_storage import BillImageStore
from app.integrations.gemini import GeminiClient, GeminiResponseError, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.fib_repo import EntryKind, FibRepository
from app.schemas.fib import ExtractedBill
from app.services.fib.ocr import BillUnreadableError, NotABillError, scan_bill

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


def _bill(**overrides: Any) -> ExtractedBill:
    fields: dict[str, Any] = {
        "is_bill": True,
        "amount": 38.5,
        "currency": "SGD",
        "vendor": "Example Telecom",
        "bill_date": "2026-09-20",
        "paid": True,
        "category": "phone_internet",
        "confidence": 0.94,
    }
    return ExtractedBill.model_validate(fields | overrides)


class FakeGemini:
    def __init__(self, outcome: ExtractedBill | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ExtractedBill:
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeFib:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def new_id(self, uid: str, kind: EntryKind) -> str:
        return "b_1"

    def save_entry(self, uid: str, kind: EntryKind, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = data


class FakeStore:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.uploads: list[tuple[str, str, str, bytes, str]] = []

    def upload(
        self, uid: str, entry_id: str, extension: str, data: bytes, content_type: str
    ) -> str:
        if self.fail:
            raise Forbidden("no access")
        self.uploads.append((uid, entry_id, extension, data, content_type))
        return f"bills/{uid}/{entry_id}/bill.{extension}"


async def _scan(
    outcome: ExtractedBill | Exception,
    fib: FakeFib | None = None,
    store: FakeStore | None = None,
    mime_type: str = "image/jpeg",
    gemini: FakeGemini | None = None,
) -> Any:
    return await scan_bill(
        "u1",
        JPEG,
        mime_type,
        cast(GeminiClient, gemini or FakeGemini(outcome)),
        cast(FibRepository, fib or FakeFib()),
        cast(BillImageStore, store or FakeStore()),
        NOW,
    )


async def test_sends_the_photo_to_the_extraction_tier_with_the_versioned_prompt() -> None:
    gemini = FakeGemini(_bill())

    await _scan(_bill(), gemini=gemini)

    call = gemini.calls[0]
    prompt = load_prompt("fib", "extract_bill", 1)
    assert call["tier"] is ModelTier.EXTRACTION
    assert call["operation"] == "fib.extract_bill"
    assert call["response_model"] is ExtractedBill
    assert call["system_instruction"] == prompt.system
    assert call["timeout_seconds"] is None
    photo, instruction = call["contents"]
    assert photo.inline_data.data == JPEG
    assert photo.inline_data.mime_type == "image/jpeg"
    assert instruction == prompt.user


async def test_a_pdf_gets_the_longer_extraction_timeout() -> None:
    gemini = FakeGemini(_bill())

    await _scan(_bill(), mime_type="application/pdf", gemini=gemini)

    assert gemini.calls[0]["timeout_seconds"] == 90.0


async def test_a_paid_bill_is_stored_with_its_extraction_and_photo() -> None:
    fib, store = FakeFib(), FakeStore()

    response = await _scan(_bill(), fib, store)

    stored = fib.docs["u1/bills/b_1"]
    assert stored == {
        "entry_date": "2026-09-20",
        "amount": 38.5,
        "currency": "SGD",
        "paid": True,
        "source": "bill_ocr",
        "vendor": "Example Telecom",
        "bill_date": "2026-09-20",
        "image_path": "bills/u1/b_1/bill.jpg",
        "category": "phone_internet",
        "category_source": "model",
        "extraction": {
            "confidence": 0.94,
            "model": "gemini-3.5-flash-lite",
            "prompt_version": 1,
        },
    }
    assert "category_confidence" not in stored
    assert store.uploads == [("u1", "b_1", "jpg", JPEG, "image/jpeg")]
    assert response.entry_id == "b_1"
    assert response.category_source == "model"
    assert response.image_path == "bills/u1/b_1/bill.jpg"
    assert response.paid_assumed is False


async def test_an_unpaid_bill_is_dated_the_day_it_was_logged() -> None:
    fib = FakeFib()

    response = await _scan(_bill(paid=False), fib)

    assert fib.docs["u1/bills/b_1"]["entry_date"] == "2026-10-01"
    assert fib.docs["u1/bills/b_1"]["bill_date"] == "2026-09-20"
    assert response.paid is False
    assert response.paid_assumed is False


async def test_unknown_paid_is_stored_as_unpaid_and_flagged() -> None:
    fib = FakeFib()

    response = await _scan(_bill(paid=None), fib)

    assert fib.docs["u1/bills/b_1"]["paid"] is False
    assert response.paid_assumed is True


async def test_missing_optional_fields_are_left_out_of_the_entry() -> None:
    fib = FakeFib()

    response = await _scan(_bill(vendor="  ", bill_date=None, category=None), fib)

    stored = fib.docs["u1/bills/b_1"]
    for field in ("vendor", "bill_date", "category", "category_source"):
        assert field not in stored
    assert response.vendor is None
    assert response.category_source is None


async def test_an_unreadable_date_is_dropped_not_stored() -> None:
    fib = FakeFib()

    response = await _scan(_bill(bill_date="20/09/2026"), fib)

    assert "bill_date" not in fib.docs["u1/bills/b_1"]
    assert fib.docs["u1/bills/b_1"]["entry_date"] == "2026-10-01"
    assert response.bill_date is None


async def test_currency_is_normalised_and_a_long_vendor_cut() -> None:
    fib = FakeFib()

    await _scan(_bill(currency=" php ", vendor="V" * 300), fib)

    assert fib.docs["u1/bills/b_1"]["currency"] == "PHP"
    assert len(fib.docs["u1/bills/b_1"]["vendor"]) == 200


async def test_a_pdf_is_stored_with_its_own_extension() -> None:
    store = FakeStore()

    await _scan(_bill(), store=store, mime_type="application/pdf")

    assert store.uploads[0][2:] == ("pdf", JPEG, "application/pdf")


async def test_a_failed_photo_upload_still_stores_the_entry() -> None:
    fib = FakeFib()

    response = await _scan(_bill(), fib, FakeStore(fail=True))

    assert "image_path" not in fib.docs["u1/bills/b_1"]
    assert response.image_path is None
    assert response.amount == 38.5


async def test_a_non_bill_is_refused_and_nothing_stored() -> None:
    fib, store = FakeFib(), FakeStore()

    with pytest.raises(NotABillError):
        await _scan(ExtractedBill(is_bill=False, confidence=0), fib, store)

    assert fib.docs == {}
    assert store.uploads == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": None},
        {"amount": 0},
        {"amount": -5},
        {"currency": None},
        {"currency": "S$"},
        {"currency": ""},
    ],
)
async def test_a_bill_without_a_readable_amount_or_currency_is_refused(
    overrides: dict[str, Any],
) -> None:
    fib, store = FakeFib(), FakeStore()

    with pytest.raises(BillUnreadableError):
        await _scan(_bill(**overrides), fib, store)

    assert fib.docs == {}
    assert store.uploads == []


async def test_gemini_errors_pass_through_and_nothing_is_stored() -> None:
    fib = FakeFib()

    with pytest.raises(GeminiResponseError):
        await _scan(GeminiResponseError("bad output"), fib)

    assert fib.docs == {}
