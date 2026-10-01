from __future__ import annotations

from google.genai import types

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ExtractedContract

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records EXTRACT_PROMPT.key / .version in the report's `prompt_versions`.
EXTRACT_PROMPT = load_prompt("contract", "extract", 2)


class NotADocumentError(Exception):
    """The upload has no readable document text (e.g. a selfie or a blank page)."""


def contract_text(contract: ExtractedContract) -> str:
    """The whole document as plain text, built from its blocks in reading order.

    Built here rather than asked from Gemini as well: a second copy would double the output
    tokens and the time of the call. A block's printed number leads its text ("3.1 The
    employer ..."), and blocks are separated by a blank line.
    """
    parts: list[str] = []
    for block in contract.blocks:
        text = block.text.strip()
        if not text:
            continue
        parts.append(f"{block.number.strip()} {text}" if block.number else text)
    return "\n\n".join(parts)


def _timeout_for(mime_type: str) -> float | None:
    """Longer per-attempt timeout for PDFs only.

    Output grows with the page count (about 2.6 s a page), so a long PDF needs up to 90 s. A
    photo is one page, and Gemini sometimes hangs an attempt: keeping the default 30 s there
    means a hang costs 30 s before the retry, not 90 s.
    """
    if mime_type == "application/pdf":
        return get_settings().gemini_extraction_timeout_seconds
    return None


async def extract_contract(
    data: bytes, mime_type: str, gemini: GeminiClient
) -> tuple[ExtractedContract, str]:
    """Transcribe a contract file into ordered blocks in its original language.

    Args:
        data: File content (PDF or image), already size- and type-checked.
        mime_type: Type detected from the content, e.g. "application/pdf".
        gemini: Client for the extraction tier call.

    Returns:
        The structured extraction and its plain text (`contract_text`). A `legibility` of
        "poor" is returned, not raised: the caller decides whether to ask for a new photo.

    Raises:
        NotADocumentError: Gemini found no readable document in the file.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    # Annotated: with Pillow installed (weasyprint pulls it in) mypy would infer list[object].
    contents: list[types.PartUnion] = [
        types.Part.from_bytes(data=data, mime_type=mime_type),
        EXTRACT_PROMPT.user,
    ]
    extracted = await gemini.generate_structured(
        operation=EXTRACT_PROMPT.key,
        tier=ModelTier.EXTRACTION,
        contents=contents,
        response_model=ExtractedContract,
        system_instruction=EXTRACT_PROMPT.system,
        timeout_seconds=_timeout_for(mime_type),
    )
    text = contract_text(extracted)
    if not extracted.is_document or not text:
        raise NotADocumentError("No readable document text found in the file")
    return extracted, text
