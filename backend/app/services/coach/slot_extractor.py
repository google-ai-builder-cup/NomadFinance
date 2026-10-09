"""Slot extraction: what a worker's message answers (NF-FC-010).

`CoachSlotExtractor` is the `SlotExtractor` the turn endpoint (NF-FC-009) takes. One structured
call reads the message (`coach/extract.v1`, classification tier); `extraction_checks.interpret`
then decides, with no model, what is kept, what is asked again and what is dropped. The message
is masked before it is sent, and nothing of it is logged.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from app.config import get_settings
from app.core.redact import redact_text
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.coach_extraction import SlotExtraction
from app.schemas.contract import ReportLanguage
from app.services.coach.extraction_checks import EARLIER_MESSAGES, ReadingContext, interpret
from app.services.coach.question_bank import load_question_bank
from app.services.coach.session_machine import QUESTION_STAGES, next_slot
from app.services.coach.turn_types import Understanding

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = load_prompt("coach", "extract", 1)
# The last turns the model may see, so "yes" or "450 dollars every week" is read in context.
RECENT_MESSAGES = 4


def _today() -> date:
    return datetime.now(UTC).date()


class CoachSlotExtractor:
    def __init__(self, gemini: GeminiClient, *, today: Callable[[], date] = _today) -> None:
        self._gemini = gemini
        self._today = today
        self._bank = load_question_bank()
        self._settings = get_settings()

    async def extract(
        self, document: dict[str, Any], text: str, language: ReportLanguage
    ) -> Understanding:
        """Read the worker's `text` against the stored `document` of the session.

        Raises:
            GeminiError: The call failed; the turn ends as any Gemini failure of a turn does.
        """
        stage = document["stage"]
        if stage not in QUESTION_STAGES:
            # In `review` and `plan` an answer does not move the stage: confirming and
            # correcting are explicit moves (NF-FC-008).
            return Understanding()
        slots: dict[str, dict[str, Any]] = document["slots"]
        declined = document.get("declined_slots", [])
        asking = next_slot(self._bank, stage, slots, declined)
        message = redact_text(text)
        messages = [
            {"role": m["role"], "text": m["text"]} for m in document["messages"][-RECENT_MESSAGES:]
        ]
        earlier = [m["text"] for m in reversed(document["messages"]) if m["role"] == "user"]
        today = self._today()
        extraction = await self._gemini.generate_structured(
            operation=EXTRACT_PROMPT.key,
            tier=ModelTier(self._settings.gemini_coach_extract_tier),
            contents=EXTRACT_PROMPT.render_user(
                worker_language=language,
                today=today.isoformat(),
                asking=asking or "none",
                unconfirmed_json=_json(
                    {n: r["value"] for n, r in slots.items() if not r["confirmed"]}
                ),
                confirmed_json=_json({n: r["value"] for n, r in slots.items() if r["confirmed"]}),
                recent_talk=_json(messages),
                message=_fenced(message),
            ),
            response_model=SlotExtraction,
            system_instruction=EXTRACT_PROMPT.system,
            temperature=0.0,
            thinking_budget=self._settings.gemini_coach_extract_thinking_budget,
        )
        understanding = interpret(
            extraction,
            ReadingContext(
                bank=self._bank,
                slots=slots,
                declined=declined,
                asking=asking,
                message=message,
                earlier=earlier[:EARLIER_MESSAGES],
                today=today,
            ),
        )
        logger.info(
            "coach_extract kind=%s candidates=%d updates=%d declined=%d follow_up=%s",
            extraction.message_kind,
            len(extraction.candidates),
            len(understanding.updates),
            len(understanding.declined),
            understanding.clarify.trigger if understanding.clarify else None,
        )
        return understanding


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _fenced(text: str) -> str:
    # The prompt says everything inside <worker_message> is data; a closing tag in the text
    # could end that section early.
    return text.replace("</worker_message", "< /worker_message")
