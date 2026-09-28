from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.contract import HostCountryCode, JobTypeId, Legibility, ReportLanguage
from app.schemas.contract_compare import ClauseCounts, ClauseRisk
from app.schemas.contract_complaint import ContractComplaint
from app.schemas.contract_translate import TranslatedClause

ContractStatus = Literal["uploaded", "processing", "completed", "failed"]
# The step a contract is on while `processing`, and the step that failed. Step 1 (extract)
# runs during the upload, so a stored contract starts at detect.
PipelineStep = Literal["extract", "detect", "law", "compare", "translate", "complaint"]
PipelineErrorCode = Literal[
    "poor_legibility",
    "country_unknown",
    "not_employment_contract",
    "no_law_data",
    "no_terms",
    "gemini_busy",
    "gemini_unavailable",
    "gemini_timeout",
    "gemini_bad_answer",
    "internal",
]


class ContractUploadResponse(BaseModel):
    """Response of `POST /api/v1/contracts` (NF-P2-007): the stored contract after step 1."""

    contract_id: str = Field(description="Id of `users/{uid}/contracts/{contract_id}`.")
    status: ContractStatus
    reused: bool = Field(description="True when this user already uploaded the same file.")
    page_count: int
    title: str | None
    legibility: Legibility = Field(
        description="`poor`: ask for a clearer photo; analysing it would be refused."
    )


class AnalyzeRequest(BaseModel):
    """Optional body of `POST /api/v1/contracts/{id}/analyze`: the upload form's choices.

    Each field wins over what the contract shows and over the worker's profile.
    """

    host_country: HostCountryCode | None = Field(
        default=None, description="Country where the worker works, if they chose one."
    )
    job_type: JobTypeId | None = Field(default=None, description="The worker's job, if chosen.")
    report_language: ReportLanguage | None = Field(
        default=None, description="Language of the worker's report; default: profile language."
    )


class ContractAnalysis(BaseModel):
    """Response of `POST /api/v1/contracts/{id}/analyze`: where to find the finished report.

    The reports themselves are `users/{uid}/contracts/{id}/reports/{language}` documents, read
    by the app straight from Firestore, or through `POST .../reports/{language}`.
    """

    contract_id: str
    status: ContractStatus
    cached: bool = Field(description="True when the stored analysis was still current.")
    host_country: HostCountryCode
    job_type: JobTypeId
    health_score: int
    risk_level: ClauseRisk
    clause_counts: ClauseCounts
    report_language: ReportLanguage = Field(description="The worker's report language.")
    report_languages: list[ReportLanguage] = Field(description="Languages with a stored report.")
    complaint_pending: bool = Field(
        default=False,
        description="The letter failed for a passing reason; analyze again to write only it.",
    )


class ContractReport(BaseModel):
    """A stored `reports/{language}` document (contracts.md), without its timestamps.

    `en` is the report the comparison wrote (`is_source`); every other language is a
    translation of it.
    """

    language: ReportLanguage
    is_source: bool
    full_text: str = Field(description="The contract's whole text, in its original language.")
    summary: str
    clauses: list[TranslatedClause]
    complaint: ContractComplaint | None = Field(
        description="The complaint letter when a term is `danger` and a template exists."
    )
    content_hash: str
    law_version: int
    prompt_versions: dict[str, int]
    models: dict[str, str]
    schema_version: int = 1
