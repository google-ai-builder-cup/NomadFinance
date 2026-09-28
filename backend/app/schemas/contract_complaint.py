from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.contract import (
    MAX_CONTRACT_TEXT_CHARS,
    HostCountryCode,
    ReportLanguage,
    SalaryPeriod,
)
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_translate import MAX_CLAUSES

# The language each host authority works in (data-scripts/.../complaint_template.py). A test
# compares the two lists, so a new letter language must be added in both places.
LetterLanguage = Literal["en", "ko", "ms", "ja"]


class ComplaintChannel(BaseModel):
    """One way to reach the authority (`complaint_templates/.../types/{type}`, contracts.md)."""

    kind: Literal["web", "email", "phone", "post"]
    value: str
    note: str | None = None


class ComplaintTemplate(BaseModel):
    """A curated letter frame as stored in `complaint_templates/{country}/types/{type}`."""

    country: HostCountryCode
    type: str
    authority_name: str
    authority_url: str | None = None
    channels: list[ComplaintChannel]
    letter_language: LetterLanguage
    template_text: str
    placeholders: list[str]
    reviewed_on: str


class ContractFacts(BaseModel):
    """What step 2 read from the contract (the `extracted` map); every field may be null."""

    employer_name: str | None = None
    agency_name: str | None = None
    salary_amount: float | None = None
    salary_currency: str | None = None
    salary_period: SalaryPeriod | None = None


class ContractComplaintRequest(BaseModel):
    """Body of `POST /api/v1/contracts/complaint`: the comparison, plus who is complaining."""

    host_country: HostCountryCode = Field(description="From /contracts/detect (or the worker).")
    clauses: list[ComparedClause] = Field(
        min_length=1, max_length=MAX_CLAUSES, description="`clauses` from /contracts/compare."
    )
    contract_facts: ContractFacts = Field(
        default_factory=ContractFacts, description="Employer, agency and salary from /detect."
    )
    worker_language: ReportLanguage = Field(description="Language of the worker's own copy.")

    @field_validator("clauses")
    @classmethod
    def _bounded_text(cls, clauses: list[ComparedClause]) -> list[ComparedClause]:
        total = sum(len(c.text) + len(c.explanation) for c in clauses)
        if total > MAX_CONTRACT_TEXT_CHARS:
            raise ValueError(f"the clauses hold more than {MAX_CONTRACT_TEXT_CHARS} characters")
        return clauses


class ComplaintAnswer(BaseModel):
    """Gemini response schema for the complaint letter (prompt contract/complaint.v2).

    Only the two texts come from Gemini; the authority, channels and template type are read
    from the curated template by code. Field descriptions are sent to Gemini.
    """

    letter_text: Annotated[str, StringConstraints(strip_whitespace=True)] = Field(
        description="The finished letter for the authority, in the template's letter language."
    )
    worker_copy: Annotated[str, StringConstraints(strip_whitespace=True)] | None = Field(
        description=(
            "The same letter in the worker's language; null when that is the letter language."
        )
    )


class ContractComplaint(BaseModel):
    """Response of `POST /api/v1/contracts/complaint` (NF-P2-006).

    `template_type`, `authority_name` and `letter_text` are the `complaint` map of
    `reports/{lang}` (contracts.md); the rest lets the report say where to send the letter.
    """

    template_type: str = Field(description="The template used: `general` for every violation.")
    authority_name: str
    authority_url: str | None
    channels: list[ComplaintChannel] = Field(description="Ways to reach the authority.")
    letter_language: LetterLanguage
    letter_text: str = Field(description="The letter to send, in `letter_language`.")
    worker_language: ReportLanguage
    worker_copy: str | None = Field(
        description="The same letter in `worker_language`, to read; null when it is the same."
    )
    violation_count: int = Field(description="How many danger clauses the letter covers.")
