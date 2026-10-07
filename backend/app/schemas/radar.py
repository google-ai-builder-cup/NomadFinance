from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.radar_scam import RadarScamReport

# Same values on radar_entities and every radar_reports document (docs/data-model/
# collections/radar.md). Contract Shield (NF-P2-021) only ever produces "employer" or
# "recruitment_agency"; "money_transfer_operator" comes from a worker's own report (NF-P3-001).
#
# "scam_type" (an entity that is a kind of scam, not a business), "scam_message" and
# "scam_check" belong to reports made from a Scam Analyzer check (NF-SA-013). A worker's own
# report form and the models that read it must never produce them, so those keep the narrower
# `User...` types: a model that answered "scam_message" would file a report as a scam type.
UserEntityType = Literal["money_transfer_operator", "recruitment_agency", "employer"]
RadarEntityType = UserEntityType | Literal["scam_type"]

UserViolationType = Literal[
    "hidden_fees",
    "exchange_rate_markup",
    "illegal_recruitment_fee",
    "wage_theft",
    "illegal_deduction",
    "contract_substitution",
    "passport_retention",
    "unlicensed_operator",
    "other",
]
RadarViolationType = UserViolationType | Literal["scam_message"]

RadarReportSource = Literal["user", "contract_signal", "seed", "scam_check"]

RadarRiskLevel = Literal["low", "medium", "high"]


class RadarValidation(BaseModel):
    """Classification-tier output for a worker's own report (NF-P3-001).

    A `contract_signal` report has no free text to check, so this is filled with fixed
    values that say so (`services/cross_pillar/contract_to_radar.py`), not a model's guess.
    """

    spam_score: float = Field(ge=0, le=1)
    category_confidence: float = Field(ge=0, le=1)
    model: str


class RadarReport(BaseModel):
    """`radar_reports/{id}` (docs/data-model/collections/radar.md). Backend-only; no client
    ever reads or writes this directly."""

    entity_type: RadarEntityType
    entity_name: str
    entity_slug: str
    violation_type: RadarViolationType
    corridor_id: str | None = None
    host_country: str | None = None
    description: str
    language: str
    cluster_id: str
    source: RadarReportSource
    reporter_hash: str | None = None
    evidence_paths: list[str] = Field(default_factory=list)
    summary: str | None = Field(
        default=None,
        description="One neutral English sentence from step 4's classification (NF-P3-001). "
        "None for contract_signal/seed reports, which have no free text to summarize.",
    )
    validation: RadarValidation
    scam: RadarScamReport | None = Field(
        default=None,
        description="The details of a scam report (`source` is `scam_check`); absent otherwise.",
    )
    created_at: datetime
    schema_version: int = 1


class RadarEntity(BaseModel):
    """`radar_entities/{slug}` (docs/data-model/collections/radar.md): the running profile of
    one operator, agency or employer. Recomputed on every new report (NF-P3-003).

    Read by signed-in users (`firestore.rules`); written only by the backend.
    """

    name: str
    slug: str
    entity_type: RadarEntityType
    aliases: list[str] = Field(default_factory=list)
    corridors: list[str] = Field(default_factory=list)
    host_countries: list[str] = Field(default_factory=list)
    report_count: int = Field(ge=0)
    incident_count: int = Field(ge=0, description="Distinct clusters: unique incidents.")
    violation_counts: dict[RadarViolationType, int] = Field(default_factory=dict)
    first_reported_at: datetime
    last_reported_at: datetime
    community_rating: float | None = Field(
        default=None, ge=0, le=5, description="Null until incident_count reaches the minimum."
    )
    risk_level: RadarRiskLevel
    flagged: bool = Field(
        description="Drives the 'Community flagged' badges (NF-P3-022, NF-P3-023)."
    )
    updated_at: datetime
    schema_version: int = 1
