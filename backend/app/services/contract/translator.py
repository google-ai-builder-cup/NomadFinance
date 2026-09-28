from __future__ import annotations

import json

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ReportLanguage
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_translate import (
    ContractReportTranslation,
    TranslatedClause,
    TranslatedClauseAnswer,
    TranslationAnswer,
)

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records TRANSLATE_PROMPT.key / .version in the report's `prompt_versions`.
TRANSLATE_PROMPT = load_prompt("contract", "translate", 1)

# Full names for the six UI languages (frontend/src/i18n/*.json), for the prompt to read.
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "tl": "Tagalog",
    "id": "Indonesian",
    "ne": "Nepali",
    "bn": "Bengali",
}


class TranslationIncompleteError(Exception):
    """Gemini's answer left out a clause that was sent to be translated."""


def _report_json(full_text: str, summary: str, clauses: list[ComparedClause]) -> str:
    """The report as the model needs it: only the fields it may translate.

    `law_reference`, `number`, `page` and `block_ids` never go to the model; they are
    reattached from the source clauses in `_merge` instead.
    """
    payload = {
        "full_text": full_text,
        "summary": summary,
        "clauses": [
            {
                "index": clause.index,
                "category": clause.category,
                "risk": clause.risk,
                "text": clause.text,
                "explanation": clause.explanation,
                "recommendation": clause.recommendation,
            }
            for clause in clauses
        ],
    }
    raw = json.dumps(payload, ensure_ascii=False)
    # The prompt says everything inside <report> is content to translate. A clause copied
    # verbatim from the contract could otherwise contain the closing tag.
    return raw.replace("</report", "< /report")


def _merge(
    clauses: list[ComparedClause], answer: list[TranslatedClauseAnswer]
) -> list[TranslatedClause]:
    """Reattach what was never sent to the model, and never trust it for the rest either.

    `category` and `risk` come back from the merged result from the source clause, not the
    answer: they are the codes the UI keys its risk flags on, so a mistranslated word must
    never be able to change one.
    """
    translated = {item.index: item for item in answer}
    missing = [clause.index for clause in clauses if clause.index not in translated]
    if missing:
        raise TranslationIncompleteError(f"missing clauses in the translated answer: {missing}")

    merged = []
    for source in clauses:
        item = translated[source.index]
        recommendation = (item.recommendation or "").strip() or None
        merged.append(
            TranslatedClause(
                index=source.index,
                number=source.number,
                page=source.page,
                text=item.text.strip(),
                category=source.category,
                risk=source.risk,
                law_reference=source.law_reference,
                explanation=item.explanation.strip(),
                recommendation=None if source.risk == "safe" else recommendation,
                block_ids=source.block_ids,
            )
        )
    return merged


async def translate_report(
    full_text: str,
    summary: str,
    clauses: list[ComparedClause],
    target_language: ReportLanguage,
    gemini: GeminiClient,
) -> ContractReportTranslation:
    """Translate a finished Contract Shield report into a worker's language.

    Args:
        full_text: The contract's whole text from step 1, in its original language.
        summary: The comparison's `summary` from step 4, in English.
        clauses: The comparison's `clauses` from step 4, in English.
        target_language: One of the six supported UI languages.
        gemini: Client for the classification tier call.

    Returns:
        The same report with `full_text`, `summary` and each clause's `text`, `explanation`
        and `recommendation` translated. `category`, `risk`, `law_reference`, `number`,
        `page` and `block_ids` are carried over from `clauses` unchanged, never from Gemini.

    Raises:
        TranslationIncompleteError: The answer left out a clause that was sent.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    answer = await gemini.generate_structured(
        operation=TRANSLATE_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=TRANSLATE_PROMPT.render_user(
            target_language=LANGUAGE_NAMES[target_language],
            report_json=_report_json(full_text, summary, clauses),
        ),
        response_model=TranslationAnswer,
        system_instruction=TRANSLATE_PROMPT.system,
        timeout_seconds=get_settings().gemini_translate_timeout_seconds,
    )
    return ContractReportTranslation(
        language=target_language,
        full_text=answer.full_text.strip(),
        summary=answer.summary.strip(),
        clauses=_merge(clauses, answer.clauses),
    )
