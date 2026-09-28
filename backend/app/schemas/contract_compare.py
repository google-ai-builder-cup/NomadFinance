from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.contract import (
    MAX_CONTRACT_TEXT_CHARS,
    ContractBlock,
    DocumentKind,
    HostCountryCode,
    JobTypeId,
)

# The 15 curated categories (docs/data-model/collections/labor_laws.md) plus `other`.
ClauseCategory = Literal[
    "minimum_wage",
    "working_hours",
    "overtime_pay",
    "rest_days_and_holidays",
    "annual_leave",
    "sick_leave",
    "salary_payment",
    "salary_deductions",
    "termination_notice",
    "early_termination",
    "recruitment_fees",
    "passport_retention",
    "accommodation",
    "insurance_and_injury",
    "social_security",
    "other",
]
ClauseRisk = Literal["safe", "caution", "danger"]

# A contract with more blocks than this is not a contract a worker was handed.
MAX_BLOCKS = 1000


class TermAssessment(BaseModel):
    """One term as judged by Gemini (prompt contract/compare.v1). Descriptions go to Gemini."""

    block_ids: list[int] = Field(description="Ids of the term's blocks, in order.")
    category: ClauseCategory = Field(description="Rule the term falls under, or other.")
    risk: ClauseRisk
    explanation: str = Field(description="One or two plain English sentences, with numbers.")
    recommendation: str | None = Field(description="One short sentence; null for a safe term.")


class ComparisonAnswer(BaseModel):
    """Gemini response schema for the clause comparison."""

    terms: list[TermAssessment] = Field(description="Every term of the contract, in order.")
    summary: str = Field(description="Two or three plain English sentences, worst problem first.")


class ContractCompareRequest(BaseModel):
    """Body of `POST /api/v1/contracts/compare`: outputs of the extract and detect steps."""

    blocks: list[ContractBlock] = Field(
        min_length=1, max_length=MAX_BLOCKS, description="`blocks` from /contracts/extract."
    )
    host_country: HostCountryCode = Field(description="From /contracts/detect (or the worker).")
    job_type: JobTypeId = Field(description="From /contracts/detect (or the worker's profile).")
    document_kind: DocumentKind = Field(
        default="employment_contract", description="From /contracts/detect."
    )

    @field_validator("blocks")
    @classmethod
    def _bounded_text(cls, blocks: list[ContractBlock]) -> list[ContractBlock]:
        if sum(len(block.text) for block in blocks) > MAX_CONTRACT_TEXT_CHARS:
            raise ValueError(f"the blocks hold more than {MAX_CONTRACT_TEXT_CHARS} characters")
        return blocks


class ClauseCounts(BaseModel):
    safe: int = 0
    caution: int = 0
    danger: int = 0


class ComparedClause(BaseModel):
    """One assessed term of the report (the clause map in collections/contracts.md, plus the
    number, page and block ids that tie it back to the document)."""

    index: int = Field(description="1, 2, 3, ... in reading order.")
    number: str | None = Field(description="Printed number of the term's first block.")
    page: int = Field(description="Page of the term's first block.")
    text: str = Field(description="The term's exact words, in the contract's language.")
    category: ClauseCategory
    risk: ClauseRisk
    law_reference: str | None = Field(
        description="Law and section of the curated rule, added by code; null without a rule."
    )
    explanation: str
    recommendation: str | None
    block_ids: list[int] = Field(description="Ids (1-based positions) of the request's blocks.")


class ContractComparison(BaseModel):
    """Response of `POST /api/v1/contracts/compare` (NF-P2-004)."""

    country: HostCountryCode
    job_type: JobTypeId
    law_version: int = Field(description="Labor-law version used; part of the report cache key.")
    health_score: int = Field(description="0 to 100, 100 safest; bands follow risk_level.")
    risk_level: ClauseRisk = Field(description="The worst risk of any term.")
    clause_counts: ClauseCounts
    summary: str = Field(description="Plain English, worst problem first.")
    clauses: list[ComparedClause]
    unassessed_block_ids: list[int] = Field(
        description="Clause, list item or table blocks the model did not assess (should be empty)."
    )
