from __future__ import annotations

from pydantic import BaseModel


class FeatureFlagsResponse(BaseModel):
    """Which Future Scope modules are on for the caller. One key per module."""

    coach: bool
    scam: bool
