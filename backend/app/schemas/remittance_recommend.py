from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.contract import ReportLanguage
from app.schemas.remittance_compare import CorridorId, RemittanceComparison
from app.schemas.remittance_trends import RemittanceTrends

# A real corridor has at most 44 surveyed services (JP-PH); bounds the request the same way
# MAX_CLAUSES and MAX_BLOCKS do for contracts.
MAX_PROVIDERS = 60


class RemittanceRecommendRequest(BaseModel):
    """Body of `POST /api/v1/remittance/recommend`: the comparison, and the worker's language."""

    comparison: RemittanceComparison = Field(
        description="The unmodified response of `/remittance/compare`."
    )
    trend: RemittanceTrends | None = Field(
        default=None, description="The response of `/remittance/trends`, for the timing tip."
    )
    target_language: ReportLanguage = Field(description="Language to write the recommendation in.")

    @field_validator("comparison")
    @classmethod
    def _bounded_and_has_a_best(cls, comparison: RemittanceComparison) -> RemittanceComparison:
        if len(comparison.providers) > MAX_PROVIDERS:
            raise ValueError(f"comparison.providers holds more than {MAX_PROVIDERS} entries")
        if not any(p.rank == 1 for p in comparison.providers):
            raise ValueError("comparison has no ranked provider to recommend")
        return comparison


class RecommendationAnswer(BaseModel):
    """Gemini response schema for the recommendation (prompt remittance/recommend.v2).

    `best_provider` is checked against the comparison, never taken as the final answer: see
    `RemittanceRecommendation.recommended_firm`.
    """

    best_provider: str = Field(description="Recommended provider's name, copied from the data.")
    headline: str = Field(description="One short sentence with the key number.")
    explanation: str = Field(description="Two to four short sentences.")
    timing_tip: str | None = Field(description="One sentence from the trend data, or null.")


class RemittanceRecommendation(BaseModel):
    """Response of `POST /api/v1/remittance/recommend` (NF-P2-016): step 9 of the pipeline.

    `recommended_rpw_id` and `recommended_firm` are the best-ranked comparable provider that
    workers have not flagged (`recommender.recommended_provider`), set by code: nothing here is
    a fact Gemini is trusted to decide. `timing_tip` is `null` whenever `trend` had nothing to
    say, whatever Gemini wrote.
    """

    corridor_id: CorridorId
    target_language: ReportLanguage
    recommended_rpw_id: int
    recommended_firm: str
    headline: str
    explanation: str
    timing_tip: str | None
