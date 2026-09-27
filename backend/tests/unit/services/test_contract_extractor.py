from __future__ import annotations

from typing import Any, cast

import pytest

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ContractBlock, ExtractedContract
from app.services.contract.extractor import (
    EXTRACT_PROMPT,
    NotADocumentError,
    contract_text,
    extract_contract,
)

pytestmark = pytest.mark.anyio


def _block(
    text: str, kind: str = "clause", number: str | None = None, page: int = 1
) -> ContractBlock:
    return ContractBlock.model_validate(
        {"page": page, "kind": kind, "number": number, "text": text}
    )


def _contract(*blocks: ContractBlock, is_document: bool = True) -> ExtractedContract:
    return ExtractedContract(
        is_document=is_document,
        page_count=max((b.page for b in blocks), default=1),
        title=None,
        legibility="good",
        blocks=list(blocks),
    )


class FakeGemini:
    def __init__(self, result: ExtractedContract) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ExtractedContract:
        self.calls.append(kwargs)
        return self.result


async def test_sends_file_to_extraction_tier_with_versioned_prompt() -> None:
    fake = FakeGemini(_contract(_block("Salary: SGD 650", number="2")))

    contract, text = await extract_contract(
        b"%PDF-1.4 fake", "application/pdf", cast(GeminiClient, fake)
    )

    assert text == "2 Salary: SGD 650"
    assert contract.blocks[0].number == "2"
    call = fake.calls[0]
    prompt = load_prompt("contract", "extract", 2)
    assert call["tier"] is ModelTier.EXTRACTION
    assert call["operation"] == "contract.extract"
    assert call["response_model"] is ExtractedContract
    assert call["system_instruction"] == prompt.system
    # Long PDFs take about 2.6 s a page; the default 30 s would cut them off.
    assert call["timeout_seconds"] == 90.0
    file_part, instruction = call["contents"]
    assert file_part.inline_data.mime_type == "application/pdf"
    assert file_part.inline_data.data == b"%PDF-1.4 fake"
    assert instruction == prompt.user


def test_pipeline_records_version_2() -> None:
    assert (EXTRACT_PROMPT.key, EXTRACT_PROMPT.version) == ("contract.extract", 2)


def test_text_keeps_reading_order_numbers_and_tables() -> None:
    contract = _contract(
        _block("EMPLOYMENT CONTRACT", kind="heading"),
        _block("The Employer shall pay:", number="3."),
        _block("a basic salary of SGD 650 a month;", kind="list_item", number="(a)"),
        _block("Item | Amount\nPlacement fee | SGD 2,400", kind="table", page=2),
        _block("   ", kind="other", page=2),
        _block("Signed: [illegible]", kind="signature", page=2),
    )

    assert contract_text(contract) == (
        "EMPLOYMENT CONTRACT\n\n"
        "3. The Employer shall pay:\n\n"
        "(a) a basic salary of SGD 650 a month;\n\n"
        "Item | Amount\nPlacement fee | SGD 2,400\n\n"
        "Signed: [illegible]"
    )


async def test_photos_keep_the_default_timeout() -> None:
    fake = FakeGemini(_contract(_block("Gaji bulanan: RM 1.500")))

    await extract_contract(b"\xff\xd8\xff", "image/jpeg", cast(GeminiClient, fake))

    # One page: a hung attempt should be retried after 30 s, not 90 s.
    assert fake.calls[0]["timeout_seconds"] is None


async def test_poor_legibility_is_returned_not_raised() -> None:
    blurry = _contract(_block("Salary [illegible]")).model_copy(update={"legibility": "poor"})

    contract, _text = await extract_contract(
        b"\xff\xd8\xff", "image/jpeg", cast(GeminiClient, FakeGemini(blurry))
    )

    assert contract.legibility == "poor"


@pytest.mark.parametrize(
    "result",
    [
        _contract(is_document=False),
        _contract(_block("   \n"), _block("", kind="heading")),
        _contract(_block("Looks like text"), is_document=False),
    ],
)
async def test_rejects_files_without_readable_text(result: ExtractedContract) -> None:
    with pytest.raises(NotADocumentError):
        await extract_contract(
            b"\xff\xd8\xff", "image/jpeg", cast(GeminiClient, FakeGemini(result))
        )
