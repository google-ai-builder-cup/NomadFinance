from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.contract import HostCountryCode, ReportLanguage
from app.schemas.radar import RadarEntityType, RadarReportSource, RadarViolationType
from app.schemas.remittance_compare import CorridorId

# A worker's own account of an incident is often longer than a system-generated one
# (contract_to_radar.py's MAX_DESCRIPTION_CHARS is 1000); short reports ("scam", "bad")
# give Gemini nothing to extract or classify from.
MIN_DESCRIPTION_CHARS = 10
MAX_DESCRIPTION_CHARS = 2000
MAX_ENTITY_NAME_CHARS = 200

RadarPersonalDataKind = Literal[
    "phone_number",
    "email",
    "id_number",
    "bank_account",
    "home_address",
    "private_person_name",
]


class RadarReportRequest(BaseModel):
    """Body of `POST /api/v1/radar/report` (NF-P3-001).

    Only `description` and `language` are required. The rest are the values a worker chose
    in the submission form (NF-P3-006), sent when the form asks for them; step 2
    (`extract_entity.v1.yaml`) fills in whatever is left blank, and a form value present here
    is preferred over what extraction finds on its own.
    """

    entity_type: RadarEntityType | None = None
    entity_name: str | None = Field(default=None, max_length=MAX_ENTITY_NAME_CHARS)
    corridor_id: CorridorId | None = None
    host_country: HostCountryCode | None = None
    description: str = Field(min_length=MIN_DESCRIPTION_CHARS, max_length=MAX_DESCRIPTION_CHARS)
    language: ReportLanguage

    @field_validator("entity_name")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @field_validator("description")
    @classmethod
    def _stripped(cls, value: str) -> str:
        return value.strip()


class RadarReportResponse(BaseModel):
    """Response of `POST /api/v1/radar/report`: the stored report, for the worker's own
    confirmation screen."""

    report_id: str = Field(description="Id of `radar_reports/{report_id}`.")
    entity_type: RadarEntityType
    entity_name: str
    violation_type: RadarViolationType
    corridor_id: CorridorId | None
    host_country: HostCountryCode | None
    description: str
    summary: str = Field(
        description="One neutral English sentence from step 4, for the confirmation screen. "
        "Also stored on the report itself (NF-P3-004). The alert cron generates its own, "
        "separate, alert-level summary from facts aggregated across multiple reports — it "
        "does not reuse this one."
    )
    created_at: datetime


class RadarReportSummary(BaseModel):
    """One report on an entity's profile (NF-P3-008): `GET /radar/entities/{slug}/reports`.

    `radar_reports` has no client access (`firestore.rules`); this is the backend's own
    view of it, with `reporter_hash` and the classification internals (`spam_score`,
    `category_confidence`, `model`) left out — never a client's business.
    """

    report_id: str
    violation_type: RadarViolationType
    description: str
    summary: str | None
    language: str
    corridor_id: CorridorId | None
    host_country: HostCountryCode | None
    source: RadarReportSource
    created_at: datetime


class RadarEvidenceResponse(BaseModel):
    """Response of `POST /api/v1/radar/report/{report_id}/evidence` (NF-P3-004)."""

    report_id: str
    evidence_paths: list[str] = Field(description="Every attachment on the report so far.")


class ExtractedEntity(BaseModel):
    """Step 2 (`extract_entity.v1.yaml`) response: who and where a report is about."""

    entity_name: str | None
    entity_name_normalized: str | None = Field(
        description="Lower case, legal suffixes and punctuation stripped; used for the "
        "slug so spelling variants of one business group together."
    )
    entity_type: RadarEntityType
    corridor_id: CorridorId | None
    host_country: HostCountryCode | None
    amount: float | None = Field(
        description="Not stored on `radar_reports` (no field for it yet); kept only because "
        "it is genuinely part of the model's answer."
    )
    currency: str | None


class ReportScreen(BaseModel):
    """Step 3 (`validate.v1.yaml`) response: spam, abuse and personal-data screening."""

    spam_score: float = Field(ge=0, le=1)
    reason: str
    is_abusive: bool
    personal_data: list[RadarPersonalDataKind]


class ViolationClassification(BaseModel):
    """Step 4 (`categorize.v1.yaml`) response: the violation type actually stored."""

    violation_type: RadarViolationType
    category_confidence: float = Field(ge=0, le=1)
    summary: str
