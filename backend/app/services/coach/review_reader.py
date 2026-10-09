"""Reading the worker's reply at the review step (NF-FC-020).

One structured call (`coach/review.v1`, classification tier) names what the worker meant: a yes, a
change (and which answer), or neither. Code decides what moves. A confirm needs high confidence
and the quoted words in the message; a change moves only to an answer the worker really gave. The
message is masked before it is sent and nothing of it is logged.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from app.config import get_settings
from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.coach_profile import SlotName
from app.schemas.coach_review import ReviewReading
from app.services.coach.extraction_cues import normal

logger = logging.getLogger(__name__)

REVIEW_PROMPT = load_prompt("coach", "review", 1)
# A yes moves the interview to the plan, so it must be sure; a worker who is not understood is
# simply shown the review again and can press the button.
CONFIRM_AT = 0.85
CHANGE_AT = 0.6


@dataclass(frozen=True)
class ReviewMove:
    """What the worker's reply does at the review: confirm every answer, or change one (`slot`;
    none when the worker did not say which, and the coach asks)."""

    kind: str  # "confirm" or "change"
    slot: SlotName | None = None


def decide(reading: ReviewReading, message: str, answered: set[str]) -> ReviewMove | None:
    """The move a reading allows, or None (nothing moves; the coach shows the review again)."""
    evidence = normal(reading.evidence)
    if reading.action == "other" or not evidence or evidence not in normal(message):
        return None
    if reading.action == "confirm":
        return ReviewMove("confirm") if reading.confidence >= CONFIRM_AT else None
    if reading.confidence < CHANGE_AT:
        return None
    # A change names an answer the worker gave; "I want to change something" names none, and the
    # coach then asks which.
    slot = reading.slot if reading.slot in answered else None
    return ReviewMove("change", slot)


class ReviewReader(Protocol):
    async def read(self, document: dict[str, Any], text: str) -> ReviewMove | None: ...


class CoachReviewReader:
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini
        self._settings = get_settings()

    async def read(self, document: dict[str, Any], text: str) -> ReviewMove | None:
        """The move the worker's `text` makes at the review of `document`.

        Raises:
            GeminiError: The call failed; the turn ends as any Gemini failure of a turn does.
        """
        slots: dict[str, dict[str, Any]] = document["slots"]
        answers = {name: record["value"] for name, record in slots.items()}
        message = redact_text(text)
        reading = await self._gemini.generate_structured(
            operation=REVIEW_PROMPT.key,
            tier=ModelTier(self._settings.gemini_coach_extract_tier),
            contents=REVIEW_PROMPT.render_user(
                answers_json=json.dumps(answers, ensure_ascii=False, sort_keys=True),
                message=message.replace("</worker_message", "< /worker_message"),
            ),
            response_model=ReviewReading,
            system_instruction=REVIEW_PROMPT.system,
            temperature=0.0,
            thinking_budget=self._settings.gemini_coach_extract_thinking_budget,
        )
        move = decide(reading, message, set(answers))
        logger.info("coach_review action=%s move=%s", reading.action, move.kind if move else None)
        return move
