from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.schemas.contract import MAX_CONTRACT_TEXT_CHARS, ReportLanguage
from app.schemas.contract_compare import ClauseCategory, ClauseRisk, ComparedClause

# A contract with more assessed terms than this was not handed to a worker (compare.v1 caps
# out around 25 to 30 for a real contract); bounds the request the same way MAX_BLOCKS does.
MAX_CLAUSES = 200


class ContractTranslateRequest(BaseModel):
    """Body of `POST /api/v1/contracts/translate`: a finished report and its target language."""

    full_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_CONTRACT_TEXT_CHARS),
    ] = Field(description="Whole contract text from /contracts/extract, in its original language.")
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        description="`summary` from /contracts/compare."
    )
    clauses: list[ComparedClause] = Field(
        min_length=1, max_length=MAX_CLAUSES, description="`clauses` from /contracts/compare."
    )
    target_language: ReportLanguage = Field(description="Language to translate the report into.")

    @field_validator("clauses")
    @classmethod
    def _bounded_text(cls, clauses: list[ComparedClause]) -> list[ComparedClause]:
        total = sum(len(c.text) + len(c.explanation) + len(c.recommendation or "") for c in clauses)
        if total > MAX_CONTRACT_TEXT_CHARS:
            raise ValueError(f"the clauses hold more than {MAX_CONTRACT_TEXT_CHARS} characters")
        return clauses


class TranslatedClauseAnswer(BaseModel):
    """One clause as Gemini returns it (prompt contract/translate.v1); descriptions go to it.

    `category` and `risk` are round-tripped so the model keeps its place in the report, but
    the service never trusts them: the merged result always takes both from the source clause.
    """

    index: int = Field(description="Same index as the source clause; never renumbered.")
    category: ClauseCategory = Field(description="Unchanged from the source; a code, not text.")
    risk: ClauseRisk = Field(description="Unchanged from the source; a code, not text.")
    text: str = Field(description="The clause's exact words, translated.")
    explanation: str = Field(description="Translated explanation.")
    recommendation: str | None = Field(description="Translated recommendation; null stays null.")


class TranslationAnswer(BaseModel):
    """Gemini response schema for the report translation."""

    full_text: str = Field(description="Whole contract text, translated.")
    summary: str = Field(description="Report summary, translated.")
    clauses: list[TranslatedClauseAnswer] = Field(description="Every clause that was sent.")


class TranslatedClause(BaseModel):
    """One clause of the translated report (the clause map of `reports/{lang}`, contracts.md)."""

    index: int
    number: str | None = Field(description="Carried over from the source clause, unchanged.")
    page: int = Field(description="Carried over from the source clause, unchanged.")
    text: str = Field(description="Translated.")
    category: ClauseCategory = Field(description="Carried over from the source clause, unchanged.")
    risk: ClauseRisk = Field(description="Carried over from the source clause, unchanged.")
    law_reference: str | None = Field(description="Carried over from the source clause, unchanged.")
    explanation: str = Field(description="Translated.")
    recommendation: str | None = Field(description="Translated; null for a safe clause.")
    block_ids: list[int] = Field(description="Carried over from the source clause, unchanged.")


class ContractReportTranslation(BaseModel):
    """Response of `POST /api/v1/contracts/translate` (NF-P2-005): the report, translated."""

    language: ReportLanguage
    full_text: str
    summary: str
    clauses: list[TranslatedClause]
