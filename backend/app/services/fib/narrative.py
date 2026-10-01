"""Financial Identity narrative (NF-P3-013): the report text of `financial_profile/current`."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.integrations.gemini import GeminiClient, GeminiResponseError, ModelTier, model_for
from app.prompts.loader import load_prompt
from app.schemas.fib_profile import NarrativeAnswer
from app.utils.i18n import language_name

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# profile records NARRATIVE_PROMPT.key / .version in its `prompt_versions`.
NARRATIVE_PROMPT = load_prompt("fib", "synthesize_narrative", 1)


def _clean(text: str) -> str:
    # D-50: structured output sometimes returns a paragraph break as the two characters
    # backslash and n instead of a line break.
    return text.replace("\\r\\n", "\n").replace("\\n", "\n").strip()


async def write_narrative(
    profile: dict[str, Any], language: str, gemini: GeminiClient
) -> tuple[str, str]:
    """Write the report text for a computed profile.

    Args:
        profile: What the prompt may see: period, the four metrics, entry counts, reporting
            currency and `income_verified_by_contract`. No overall score and no names.
        language: One of the six app language codes.
        gemini: Client for the reasoning-tier call.

    Returns:
        The text and the model that wrote it.

    Raises:
        GeminiError: Any Gemini failure, including an empty text (`GeminiResponseError`).
    """
    settings = get_settings()
    answer = await gemini.generate_structured(
        operation=NARRATIVE_PROMPT.key,
        tier=ModelTier.REASONING,
        contents=NARRATIVE_PROMPT.render_user(
            report_language=language_name(language),
            profile_json=json.dumps(profile, ensure_ascii=False),
        ),
        response_model=NarrativeAnswer,
        system_instruction=NARRATIVE_PROMPT.system,
        timeout_seconds=settings.gemini_narrative_timeout_seconds,
    )
    text = _clean(answer.text)
    if not text:
        raise GeminiResponseError("The narrative came back empty")
    return text, model_for(ModelTier.REASONING, settings)
