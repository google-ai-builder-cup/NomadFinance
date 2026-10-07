"""Models of the screenshot path of `POST /api/v2/scam/analyze` (NF-SA-008).

`ScreenshotReading` is the structured-output schema of the Vision call, loose on purpose: a
model that returns an odd value must not fail the check with a 502. `ScamAnalyzeFormFields` is
the text part of the multipart body; the file itself has no model because a file is not JSON.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.scam import CorridorId, Language


class ScreenshotReading(BaseModel):
    """What the Vision step found in a screenshot."""

    is_message: bool
    message_text: str | None = None
    sender: str | None = None


class ScamAnalyzeFormFields(BaseModel):
    """`language` and `corridor_id` of a screenshot request, same rules as the JSON body."""

    language: Language
    corridor_id: CorridorId | None = None
