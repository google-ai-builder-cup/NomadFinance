"""Request and response models of the Scam Analyzer API (NF-SA-002).

These are the contract in `docs/api/v2-scam.md`: the endpoints (NF-SA-007, -008, -012, -013)
import them, and `tests/unit/test_scam_mocks.py` checks that every mock in `docs/mocks/scam/`
parses as one of them. A field added to a response is not a breaking change; a field removed,
renamed or retyped is (`docs/api/v2-conventions.md`, section 6). Where the data lives and how
long it is kept: `docs/data-model/collections/scam.md`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

Language = Literal["en", "hi", "tl", "id", "ne", "bn"]
MessageLanguage = Literal["en", "hi", "tl", "id", "ne", "bn", "other"]
CorridorId = Literal["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"]
RiskLevel = Literal["low", "medium", "high"]
InputType = Literal["text", "screenshot"]
IndicatorKind = Literal["url", "phone", "email", "handle", "sender"]
IndicatorFlag = Literal["shortener", "punycode", "lookalike", "premium_rate", "unexpected_country"]
ContactChannel = Literal["sms", "whatsapp", "call", "email", "other"]
SimilarSource = Literal["scam_pattern", "radar_report"]
ExplainerStatus = Literal["ready", "unavailable"]

# An id from the scam taxonomy (`scam_taxonomy/{id}`): the screens translate it by key.
TaxonomyId = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{1,40}$")]
# First 8 hex characters of an indicator's SHA-256 key (data model, "The key of an indicator").
IndicatorId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{8}$")]

MAX_TEXT_CHARS = 4000
MAX_REPORT_DESCRIPTION_CHARS = 1000
MAX_REPORT_INDICATORS = 10


class ScamAnalyzeTextRequest(BaseModel):
    """Body of `POST /api/v2/scam/analyze` for a pasted message (`application/json`).

    A screenshot goes as `multipart/form-data` with an `image` file and the same `language` and
    `corridor_id` fields; it has no model here because a file is not JSON.
    """

    text: str = Field(
        description="The message exactly as received. Not cut: over the limit is a 422."
    )
    language: Language = Field(description="The worker's language: the explainer is written in it.")
    corridor_id: CorridorId | None = Field(
        default=None, description="The worker's route; defaults to the one in their profile."
    )

    @field_validator("text")
    @classmethod
    def _text_has_content_and_fits(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("The message is empty.")
        if len(stripped) > MAX_TEXT_CHARS:
            raise ValueError(f"String should have at most {MAX_TEXT_CHARS} characters")
        return stripped


class ScamVerdict(BaseModel):
    """What the classifier decided. Also the structured-output schema of that call (NF-SA-007)."""

    is_scam: bool
    scam_type: TaxonomyId | None = Field(description="Taxonomy type id; `null` when not a scam.")
    tactics: list[TaxonomyId] = Field(max_length=6, description="Taxonomy tactic ids.")
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    trigger_phrases: list[Annotated[str, StringConstraints(min_length=1, max_length=80)]] = Field(
        max_length=5, description="Parts of `redacted_text` that gave it away."
    )

    @model_validator(mode="after")
    def _a_message_that_is_not_a_scam_has_no_type_tactics_or_risk(self) -> ScamVerdict:
        if not self.is_scam and (self.scam_type or self.tactics or self.risk_level != "low"):
            raise ValueError("A message that is not a scam has no type or tactics and low risk.")
        if self.is_scam and self.scam_type is None:
            raise ValueError("A scam has a type (`other_scam` when none of the others fits).")
        return self


class ScamAmount(BaseModel):
    amount: float = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217.")


class ScamDetails(BaseModel):
    """What the message asks for, when it says. Every field is optional: absent is unknown."""

    claimed_identity: str | None = Field(default=None, max_length=120)
    contact_channel: ContactChannel | None = None
    payment_requested: str | None = Field(default=None, max_length=120)
    amount_requested: ScamAmount | None = None
    deadline_stated: bool | None = None


class SeenCount(BaseModel):
    """How often workers reported this indicator (`scam_indicators`), read when a check is shown."""

    reports: int = Field(ge=1)
    incidents: int = Field(ge=1)
    last_reported_at: datetime
    flagged: bool = Field(description="At least 2 incidents: a pattern, not one unverified report.")


class ScamIndicator(BaseModel):
    id: IndicatorId
    kind: IndicatorKind
    value: str = Field(max_length=254, description="A URL is its host only.")
    flags: list[IndicatorFlag]
    imitates: str | None = Field(default=None, description="The real domain a lookalike copies.")
    seen: SeenCount | None = Field(
        default=None, description="`null` when never reported, or hidden by an operator."
    )

    @model_validator(mode="after")
    def _imitates_belongs_to_a_lookalike(self) -> ScamIndicator:
        if self.imitates is not None and "lookalike" not in self.flags:
            raise ValueError("`imitates` is only set for a lookalike.")
        return self


class TacticExplanation(BaseModel):
    tactic: TaxonomyId
    text: str = Field(min_length=1)


class ScamExplainer(BaseModel):
    """For a scam: why it works, what the scammer wants and three safe next steps (grade 6)."""

    kind: Literal["scam"]
    language: Language
    why_it_works: list[TacticExplanation] = Field(min_length=1)
    scammer_wants: str = Field(min_length=1)
    next_steps: list[str] = Field(min_length=3, max_length=3)


class BenignExplainer(BaseModel):
    """For a message that is not a scam: a short reassurance and one general tip."""

    kind: Literal["benign"]
    language: Language
    reassurance: str = Field(min_length=1)
    tip: str = Field(min_length=1)


Explainer = Annotated[ScamExplainer | BenignExplainer, Field(discriminator="kind")]


class SimilarScam(BaseModel):
    source: SimilarSource
    scam_type: TaxonomyId | None
    score: float = Field(ge=0, le=1)


class ScamCheckDetail(BaseModel):
    """One analysed message, as the owner sees it (`GET /scam/checks/{id}`)."""

    id: str
    input_type: InputType
    language: Language
    message_language: MessageLanguage | None = None
    redacted_text: str = Field(description="Phone numbers, emails, IDs, accounts and URLs masked.")
    corridor_id: CorridorId | None = None
    verdict: ScamVerdict
    details: ScamDetails
    indicators: list[ScamIndicator] = Field(max_length=10)
    explainer: Explainer | None
    explainer_status: ExplainerStatus
    similar: list[SimilarScam] = Field(max_length=3)
    corridor_report_count: int | None = Field(default=None, ge=0)
    reported: bool
    report_id: str | None
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def _the_parts_agree(self) -> ScamCheckDetail:
        if (self.explainer is None) != (self.explainer_status == "unavailable"):
            raise ValueError("`explainer` is null exactly when `explainer_status` is unavailable.")
        if self.explainer is not None and (self.explainer.kind == "scam") != self.verdict.is_scam:
            raise ValueError("The explainer kind must match the verdict.")
        if self.reported != (self.report_id is not None):
            raise ValueError("`report_id` is set exactly when `reported` is true.")
        return self


class ScamAnalyzeResponse(ScamCheckDetail):
    """Answer of `POST /scam/analyze`: the check, and whether it came from the cache."""

    cached: bool = Field(description="True when this exact message was checked before.")


class ScamCheckSummary(BaseModel):
    """One row of the history list."""

    id: str
    created_at: datetime
    input_type: InputType
    language: Language
    is_scam: bool
    scam_type: TaxonomyId | None
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    excerpt: str = Field(max_length=140, description="Start of `redacted_text`.")
    reported: bool


class ScamCheckListResponse(BaseModel):
    items: list[ScamCheckSummary]
    next_cursor: str | None


class ScamReportRequest(BaseModel):
    """Body of `POST /scam/checks/{id}/report`: exactly what the confirmation sheet shows."""

    indicator_ids: list[IndicatorId] = Field(
        max_length=MAX_REPORT_INDICATORS,
        description="The indicators the worker left ticked. May be empty.",
    )
    description: str | None = Field(
        default=None,
        description="The message text, as the worker edited it; defaults to `redacted_text`. "
        "Redacted again by the server.",
    )

    @field_validator("indicator_ids")
    @classmethod
    def _no_repeats(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Each indicator may be named once.")
        return value

    @field_validator("description")
    @classmethod
    def _description_fits(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("The description is empty.")
        if len(stripped) > MAX_REPORT_DESCRIPTION_CHARS:
            raise ValueError(
                f"String should have at most {MAX_REPORT_DESCRIPTION_CHARS} characters"
            )
        return stripped


class ScamReportResponse(BaseModel):
    report_id: str
    already_reported: bool = Field(description="True when this check had been reported before.")
    entity_slug: str = Field(description="The Radar profile: `/radar/entity/{entity_slug}`.")
    entity_name: str = Field(description="The scam type's English label.")
    created_at: datetime
