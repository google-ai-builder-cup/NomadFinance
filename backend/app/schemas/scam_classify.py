"""What the classifier model returns for a message (NF-SA-007), before it becomes a `ScamVerdict`.

Deliberately looser than the contract's `ScamVerdict`: a model that writes an 85-character
trigger phrase or an unknown tactic id must not fail the whole check with a 502. The service
(`app/services/scam/classifier.py`) trims it into the strict contract types instead.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.scam import RiskLevel


class ClassifiedDetails(BaseModel):
    """`ScamDetails` flattened: the amount and its currency are two plain fields."""

    claimed_identity: str | None = None
    contact_channel: str | None = None
    payment_requested: str | None = None
    amount: float | None = None
    currency: str | None = None
    deadline_stated: bool | None = None


class ScamClassification(BaseModel):
    """The structured-output schema of the `scam.classify` call."""

    is_scam: bool
    scam_type: str | None = Field(description="A taxonomy type id, or null when not a scam.")
    tactics: list[str] = Field(description="Taxonomy tactic ids.")
    risk_level: RiskLevel
    confidence: float
    trigger_phrases: list[str]
    message_language: str | None = Field(description="en, hi, tl, id, ne, bn or other.")
    details: ClassifiedDetails
