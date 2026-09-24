from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractedText(BaseModel):
    """Gemini response schema for contract text extraction.

    Field descriptions are sent to Gemini as part of the schema.
    """

    is_document: bool = Field(
        description="False when the file has no readable document text (selfie, blank page)."
    )
    page_count: int = Field(description="Pages in the PDF; 1 for a photo.")
    text: str = Field(
        description="Full transcription in the original language; empty if not a document."
    )


class ContractExtractResponse(BaseModel):
    """Response of `POST /api/v1/contracts/extract`."""

    filename: str | None = Field(description="Name of the uploaded file, as sent by the client.")
    mime_type: str = Field(description="Type detected from the file bytes, not the client header.")
    size_bytes: int
    page_count: int
    text: str = Field(description="Extracted text in the document's original language.")
