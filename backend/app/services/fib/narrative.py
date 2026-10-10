"""Financial Identity narrative (NF-P3-013): the report text of `financial_profile/current`."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, NamedTuple

from app.config import get_settings
from app.integrations.gemini import GeminiClient, GeminiResponseError, ModelTier, model_for
from app.prompts.loader import load_prompt
from app.schemas.fib_profile import NarrativeAnswer
from app.utils.i18n import language_name

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# profile records NARRATIVE_PROMPT.key / .version in its `prompt_versions`.
NARRATIVE_PROMPT = load_prompt("fib", "synthesize_narrative", 2)


class Narrative(NamedTuple):
    text: str
    # What the worker shared, in a paragraph of its own so that turning the sharing off removes
    # it from a report without rewriting the rest (NF-HR-001). Empty when nothing is shared.
    activity_text: str
    model: str


_NUMBER = re.compile(r"\d+")


def _numbers_in(value: Any) -> set[int]:
    """The whole numbers written in `value`. `int()` reads "03" as 3 and any script's digits, so
    "3 October" matches the date 2026-10-03 and a Hindi digit matches its Latin one."""
    return {int(found) for found in _NUMBER.findall(json.dumps(value, ensure_ascii=False))}


def _grounded_activity(text: str, shared: dict[str, Any] | None) -> str:
    """The activity paragraph, or "" when it should not be printed.

    It is printed only when the worker shares something and every number in it is one of the
    numbers or dates of what they shared; a lender must not read a count the data does not hold.
    The structured section of the PDF still shows the figures.
    """
    if not shared or not text:
        return ""
    invented = _numbers_in(text) - _numbers_in(shared)
    if invented:
        # The numbers only, never the paragraph: it is about a worker's own activity.
        logger.warning("fib_activity_text_dropped numbers_not_shared=%s", sorted(invented))
        return ""
    return text


def _clean(text: str) -> str:
    # D-50: structured output sometimes returns a paragraph break as the two characters
    # backslash and n instead of a line break.
    return text.replace("\\r\\n", "\n").replace("\\n", "\n").strip()


async def write_narrative(
    profile: dict[str, Any], language: str, gemini: GeminiClient
) -> Narrative:
    """Write the report text for a computed profile.

    Args:
        profile: What the prompt may see: period, the four metrics, entry counts, reporting
            currency, `income_verified_by_contract` and, only when the worker shares it,
            `shared_activity`. No overall score and no names.
        language: One of the six app language codes.
        gemini: Client for the reasoning-tier call.

    Returns:
        The text, the paragraph about shared activity ("" unless `profile` has
        `shared_activity` and the paragraph states only numbers from it), and the model.

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
    activity = _grounded_activity(_clean(answer.activity_text), profile.get("shared_activity"))
    return Narrative(text, activity, model_for(ModelTier.REASONING, settings))
