from __future__ import annotations

from enum import StrEnum

from app.config import Settings


class ModelTier(StrEnum):
    """Workload class a Gemini call belongs to; each tier maps to one configured model."""

    REASONING = "reasoning"
    """Legal analysis, complaint letters, financial narratives."""

    EXTRACTION = "extraction"
    """Vision and document extraction (contracts, bills, receipts)."""

    CLASSIFICATION = "classification"
    """High-volume, low-cost calls: classification, validation, translation."""


def model_for(tier: ModelTier, settings: Settings) -> str:
    """Return the model ID configured for a tier."""
    models = {
        ModelTier.REASONING: settings.gemini_model_reasoning,
        ModelTier.EXTRACTION: settings.gemini_model_extraction,
        ModelTier.CLASSIFICATION: settings.gemini_model_classification,
    }
    return models[tier]
