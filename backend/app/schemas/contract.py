from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

BlockKind = Literal["heading", "clause", "paragraph", "list_item", "table", "signature", "other"]
Legibility = Literal["good", "partial", "poor"]

# Same values as the onboarding profile (frontend/src/types/enums.ts) and the labor-law data.
HostCountryCode = Literal["SG", "KR", "MY", "JP", "HK", "AU"]
JobTypeId = Literal[
    "domestic_worker",
    "manufacturing_worker",
    "care_worker",
    "plantation_worker",
    "construction_worker",
    "working_holiday",
    "other",
]
DocumentKind = Literal["employment_contract", "recruitment_agreement", "loan_agreement", "other"]
SalaryPeriod = Literal["month", "week", "day", "hour"]

# About 50k tokens: far above a 15-page contract (about 60k characters), well below what the
# model accepts. Bounds the cost of one call.
MAX_CONTRACT_TEXT_CHARS = 200_000


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


class DetectedContract(BaseModel):
    """Gemini response schema for contract detection (prompt contract/detect.v1, NF-P2-002).

    `language`, `host_country`, `document_kind` and `job_type` are stored as the contract's
    `detected` map; the employer, agency and salary fields as its `extracted` map
    (docs/data-model/collections/contracts.md). Field descriptions are sent to Gemini.
    """

    language: str | None = Field(
        description='ISO 639-1 code of the main language of the document, e.g. "en", "ms", "ko".'
    )
    host_country: HostCountryCode | None = Field(
        description=(
            "Country where the work is done, if it is one of SG, KR, MY, JP, HK, AU. "
            "null for any other country or when it cannot be told."
        )
    )
    host_country_evidence: str = Field(
        description="A few words saying what showed the country. Empty if host_country is null."
    )
    document_kind: DocumentKind = Field(
        description=(
            "employment_contract; recruitment_agreement (with an agency, about fees or "
            "placement); loan_agreement (money lent to the worker); or other."
        )
    )
    job_type: JobTypeId = Field(description="The worker's job type, judged by the duties.")
    employer_name: str | None = Field(description="Employer exactly as written; null if none.")
    agency_name: str | None = Field(description="Recruitment agency as written; null if none.")
    salary_amount: float | None = Field(
        description="Basic salary as a plain number; null if no amount is stated."
    )
    salary_currency: str | None = Field(description='ISO 4217 code of the salary, e.g. "SGD".')
    salary_period: SalaryPeriod | None = Field(
        description="month, week, day or hour; null if not stated or any other period."
    )


class ContractDetectRequest(BaseModel):
    """Body of `POST /api/v1/contracts/detect`: the `text` returned by the extract step."""

    text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_CONTRACT_TEXT_CHARS),
    ] = Field(description="Whole contract text, in its original language.")
