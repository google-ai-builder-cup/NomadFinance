from __future__ import annotations

from google.genai import types

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ExtractedText

# Loaded at import so a missing or malformed prompt file stops the app at startup.
_PROMPT = load_prompt("contract", "extract", 1)


class NotADocumentError(Exception):
    """The upload has no readable document text (e.g. a selfie or a blank page)."""


async def extract_text(data: bytes, mime_type: str, gemini: GeminiClient) -> ExtractedText:
    """Transcribe a contract file into text in its original language.

    Args:
        data: File content (PDF or image), already size- and type-checked.
        mime_type: Type detected from the content, e.g. "application/pdf".
        gemini: Client for the extraction tier call.

    Returns:
        The extraction with `is_document` true and non-empty text.

    Raises:
        NotADocumentError: Gemini found no readable document in the file.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    extracted = await gemini.generate_structured(
        operation="contract.extract",
        tier=ModelTier.EXTRACTION,
        contents=[types.Part.from_bytes(data=data, mime_type=mime_type), _PROMPT.user],
        response_model=ExtractedText,
        system_instruction=_PROMPT.system,
    )
    if not extracted.is_document or not extracted.text.strip():
        raise NotADocumentError("No readable document text found in the file")
    return extracted
