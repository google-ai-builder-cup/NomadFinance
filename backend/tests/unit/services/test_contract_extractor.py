from __future__ import annotations

from typing import Any, cast

import pytest

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ExtractedText
from app.services.contract.extractor import NotADocumentError, extract_text

pytestmark = pytest.mark.anyio


class FakeGemini:
    def __init__(self, result: ExtractedText) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> ExtractedText:
        self.calls.append(kwargs)
        return self.result


async def test_sends_file_to_extraction_tier_with_versioned_prompt() -> None:
    fake = FakeGemini(ExtractedText(is_document=True, page_count=2, text="Salary: SGD 650"))

    result = await extract_text(b"%PDF-1.4 fake", "application/pdf", cast(GeminiClient, fake))

    assert result.text == "Salary: SGD 650"
    call = fake.calls[0]
    prompt = load_prompt("contract", "extract", 1)
    assert call["tier"] is ModelTier.EXTRACTION
    assert call["operation"] == "contract.extract"
    assert call["response_model"] is ExtractedText
    assert call["system_instruction"] == prompt.system
    file_part, instruction = call["contents"]
    assert file_part.inline_data.mime_type == "application/pdf"
    assert file_part.inline_data.data == b"%PDF-1.4 fake"
    assert instruction == prompt.user


@pytest.mark.parametrize(
    "result",
    [
        ExtractedText(is_document=False, page_count=1, text=""),
        ExtractedText(is_document=True, page_count=1, text="   \n"),
    ],
)
async def test_rejects_files_without_readable_text(result: ExtractedText) -> None:
    with pytest.raises(NotADocumentError):
        await extract_text(b"\xff\xd8\xff", "image/jpeg", cast(GeminiClient, FakeGemini(result)))
