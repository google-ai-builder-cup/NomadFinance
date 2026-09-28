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
LawCoverage = Literal["regulated", "partly_regulated", "not_regulated", "unclear"]
LawConfidence = Literal["high", "medium", "low"]
LawLimitPeriod = Literal["hour", "day", "week", "month", "year", "once"]

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


class LawLimit(BaseModel):
    """A number a contract clause can be compared with (labor_laws.md, `rules.variants.limits`)."""

    value: float
    unit: str
    period: LawLimitPeriod | None = None
    note: str | None = None


class LawReference(BaseModel):
    """Where a rule comes from (labor_laws.md, `rules.references`)."""

    law: str
    section: str
    url: str
    year: int | None = None
    in_force_since: str | None = None
    natlex_isn: str | None = None


class LaborLawVariant(BaseModel):
    """The rule for one group of workers (labor_laws.md, `rules.variants`).

    `applies_to` is `["all"]` or one or more job type ids; a job-type variant overrides the
    `all` variant for that job type (enforced at curation time by `LaborLawFile`).
    """

    applies_to: list[str]
    requirements: list[str]
    limits: dict[str, LawLimit] = Field(default_factory=dict)
    penalty: str | None = None
    enforced_by: str | None = None


class LaborLawRule(BaseModel):
    """One curated category, with the variant that applies to the requested job type.

    `applicable_variant` is what the clause comparison (NF-P2-004) should check a contract
    against; the full `variants` are kept for any category that needs another job type.
    """

    category: str = Field(description="One of the 15 category ids in labor_laws.md.")
    coverage: LawCoverage
    title: str
    summary: str
    applicable_variant: LaborLawVariant
    variants: list[LaborLawVariant]
    references: list[LawReference]
    confidence: LawConfidence
    notes: str | None = Field(
        default=None, description="Curator exceptions and caveats, e.g. a job type left out."
    )


class LaborLawContext(BaseModel):
    """Response of `GET /api/v1/contracts/labor-law/{host_country}` (NF-P2-003).

    `law_version` is `labor_laws/{country}/_meta/current.version`: record it on the eventual
    contract report so the response cache (NF-P2-007) can tell when the law has changed
    (`docs/data-model/versioning.md`).
    """

    country: HostCountryCode
    job_type: JobTypeId
    law_version: int
    rules: list[LaborLawRule]
