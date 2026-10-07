"""What the explainer models return (NF-SA-009), before it becomes the contract's `Explainer`.

Looser than `ScamExplainer` and `BenignExplainer`: a fourth next step or a long sentence must
not fail the whole call with a 502. The service (`app/services/scam/explainer.py`) trims and
checks it, and when it cannot be used the answer carries `explainer: null` instead.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExplainedTactic(BaseModel):
    tactic: str = Field(description="One of the tactic ids that were asked for, copied exactly.")
    text: str = Field(description="One or two short sentences in the worker's language.")


class ScamExplanation(BaseModel):
    """The structured-output schema of the `scam.explain` call."""

    why_it_works: list[ExplainedTactic]
    scammer_wants: str
    next_steps: list[str] = Field(description="Exactly 3 steps, the most important first.")


class BenignReassurance(BaseModel):
    """The structured-output schema of the `scam.reassure` call."""

    reassurance: str
    tip: str
