"""The Gemini step that translates a plan's narrative (NF-FC-014, Flash-Lite).

Only sentences go to the model (`narrative_of`). The answer is checked in code
(`plan_translation_check`) and asked for once more with the reasons; a second failure is a
`GeminiResponseError` (502 `ai_bad_response`) and nothing is saved. Figures never leave the
stored plan, so a translation cannot change one.
"""

from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.integrations.gemini.errors import GeminiResponseError
from app.integrations.gemini.model_tiers import model_for
from app.prompts.loader import load_prompt
from app.schemas.coach_plan import CoachPlan
from app.schemas.coach_plan_text import PlanTranslation
from app.schemas.contract import ReportLanguage
from app.services.coach.plan_translation_check import (
    apply_narrative,
    check_translation,
    narrative_of,
    same_figures,
)

logger = logging.getLogger(__name__)

TRANSLATE_PROMPT = load_prompt("coach", "translate_plan", 1)
ATTEMPTS = 2
LANGUAGE_NAMES: dict[str, str] = {
    "hi": "Hindi",
    "tl": "Tagalog (Filipino)",
    "id": "Indonesian",
    "ne": "Nepali",
    "bn": "Bengali",
}


class CoachPlanTranslator:
    def __init__(self, gemini: GeminiClient) -> None:
        self._gemini = gemini
        self._settings = get_settings()

    @property
    def model(self) -> str:
        return model_for(ModelTier(self._settings.gemini_coach_translate_tier), self._settings)

    async def translate(self, plan: CoachPlan, language: ReportLanguage) -> CoachPlan:
        """The plan in `language`: its sentences translated, every other field as it was.

        Raises:
            GeminiError: The call failed (a `GeminiResponseError` when the answer was unusable
                twice).
            ValueError: `language` is English (nothing to translate).
        """
        if language not in LANGUAGE_NAMES:
            raise ValueError(f"No translation into {language}")
        source = narrative_of(plan)
        plan_json = json.dumps(source.model_dump(), ensure_ascii=False)
        fix_these = "none"
        for attempt in range(1, ATTEMPTS + 1):
            target = await self._gemini.generate_structured(
                operation=TRANSLATE_PROMPT.key,
                tier=ModelTier(self._settings.gemini_coach_translate_tier),
                contents=TRANSLATE_PROMPT.render_user(
                    target_language=LANGUAGE_NAMES[language],
                    plan_json=plan_json,
                    fix_these=fix_these,
                ),
                response_model=PlanTranslation,
                system_instruction=TRANSLATE_PROMPT.system,
                temperature=0.0,
                thinking_budget=self._settings.gemini_coach_translate_thinking_budget,
                timeout_seconds=60,
            )
            problems = check_translation(source, target)
            if not problems:
                translated = apply_narrative(plan, target)
                if not same_figures(plan, translated):
                    raise GeminiResponseError("The translation changed a figure.")
                return translated
            # Only the number of reasons is logged, never the text.
            logger.warning(
                "coach_translation_rejected language=%s attempt=%d problems=%d",
                language,
                attempt,
                len(problems),
            )
            fix_these = "\n".join(problems)
        raise GeminiResponseError("The translation changed numbers or the structure.")
