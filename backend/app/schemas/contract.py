from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BlockKind = Literal["heading", "clause", "paragraph", "list_item", "table", "signature", "other"]
Legibility = Literal["good", "partial", "poor"]


class ContractBlock(BaseModel):
    """One piece of the document in reading order (NF-P2-001).

    Field descriptions are sent to Gemini as part of the schema.
    """

    page: int = Field(description="Page the block starts on, from 1; 1 for a photo.")
    kind: BlockKind = Field(
        description=(
            "heading: a title or section heading. clause: a numbered or clearly separate term. "
            "paragraph: running text that is not a term. list_item: an item of a list inside "
            "a clause. table: a whole table. signature: signature, date and name lines. "
            "other: anything else with text (stamps, footers)."
        )
    )
    number: str | None = Field(
        description='Clause or item number as printed ("3", "3.1", "(a)", "IV"); null if none.'
    )
    text: str = Field(
        description=(
            "Exact text in the original language, without the number. For a table: one row per "
            "line, cells separated by ' | ', header row first."
        )
    )


class ExtractedContract(BaseModel):
    """Gemini response schema for contract extraction (prompt contract/extract.v2)."""

    is_document: bool = Field(
        description="False when the file has no readable document text (selfie, blank page)."
    )
    page_count: int = Field(description="Pages in the PDF; 1 for a photo.")
    title: str | None = Field(description="Document title as written; null if there is none.")
    legibility: Legibility = Field(
        description=(
            "good: all text readable. partial: some words or lines unreadable. poor: much of "
            "the text unreadable (blur, glare, cropped)."
        )
    )
    blocks: list[ContractBlock] = Field(
        description="The whole document in reading order; empty if not a document."
    )


class ContractExtractResponse(BaseModel):
    """Response of `POST /api/v1/contracts/extract`."""

    filename: str | None = Field(description="Name of the uploaded file, as sent by the client.")
    mime_type: str = Field(description="Type detected from the file bytes, not the client header.")
    size_bytes: int
    page_count: int
    title: str | None = Field(description="Document title as written, if any.")
    legibility: Legibility = Field(
        description="`poor` means the transcription is unreliable: ask for a clearer photo."
    )
    text: str = Field(
        description="Whole document in its original language, built from `blocks` in order."
    )
    blocks: list[ContractBlock] = Field(description="The document in reading order.")
