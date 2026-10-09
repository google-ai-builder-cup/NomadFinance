"""What the Coach guard's classifier returns for one worker message (NF-FC-013).

This is the model's raw label, sent to Gemini as the response schema. Nothing in it is stored or
shown: `app/services/coach/guard.py` turns it into a decision, and a label the model is unsure of
lets the turn through (the reply prompt and the reply check still stand behind it).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ScopeLabel = Literal["on_topic", "off_topic", "product_request", "injection", "distress"]


class ScopeVerdict(BaseModel):
    label: ScopeLabel
    confidence: float = Field(description="0 to 1: how sure the label is.")
