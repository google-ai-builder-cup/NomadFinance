"""The `scam` map of a Radar report made from a Scam Analyzer check (NF-SA-013).

`docs/data-model/collections/radar.md`, "Scam reports". Public to every signed-in worker through
the entity page, so it holds only what the worker confirmed on the sheet: no uid, no reporter
hash, no check id and no raw message. An absent key means unknown, as everywhere in the scam
contract.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.scam import (
    IndicatorFlag,
    IndicatorKind,
    InputType,
    MessageLanguage,
    RiskLevel,
    ScamDetails,
    TaxonomyId,
)


class ReportedIndicator(BaseModel):
    """An indicator the worker left ticked: the check's own, without its `id` and `seen`."""

    kind: IndicatorKind
    value: str = Field(max_length=254)
    flags: list[IndicatorFlag]
    imitates: str | None = None


class RadarScamReport(BaseModel):
    scam_type: TaxonomyId
    tactics: list[TaxonomyId]
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    trigger_phrases: list[str]
    details: ScamDetails
    indicators: list[ReportedIndicator]
    message_language: MessageLanguage | None = None
    input_type: InputType
