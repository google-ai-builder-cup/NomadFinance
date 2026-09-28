from __future__ import annotations

import math
import re

from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import DetectedContract

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records DETECT_PROMPT.key / .version in the report's `prompt_versions`.
DETECT_PROMPT = load_prompt("contract", "detect", 2)

_LANGUAGE_CODE = re.compile(r"^[a-z]{2}$")
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")
# Names and evidence are short in any real document; the cap keeps a confused answer from
# reaching Firestore or the UI as a paragraph.
_MAX_TEXT_FIELD_CHARS = 200


def _language_code(raw: str | None) -> str | None:
    """ISO 639-1 code from a model answer such as "EN", "en-US" or "zh_CN"; None if unusable."""
    if not raw:
        return None
    code = re.split(r"[-_]", raw.strip().lower())[0]
    return code if _LANGUAGE_CODE.match(code) else None


def _short_text(raw: str | None) -> str | None:
    text = (raw or "").strip()[:_MAX_TEXT_FIELD_CHARS].strip()
    return text or None


def _clean(detected: DetectedContract) -> DetectedContract:
    """Normalise what the model returned, so later steps can trust the shapes.

    Values that are unusable become None rather than errors: a step that cannot tell the
    language or the currency must not fail the whole analysis.
    """
    amount = detected.salary_amount
    if amount is not None and not (math.isfinite(amount) and amount > 0):
        amount = None
    currency = (detected.salary_currency or "").strip().upper()
    return detected.model_copy(
        update={
            "language": _language_code(detected.language),
            "host_country_evidence": (
                (_short_text(detected.host_country_evidence) or "") if detected.host_country else ""
            ),
            "employer_name": _short_text(detected.employer_name),
            "agency_name": _short_text(detected.agency_name),
            "salary_amount": amount,
            "salary_currency": (
                currency if amount is not None and _CURRENCY_CODE.match(currency) else None
            ),
            "salary_period": detected.salary_period if amount is not None else None,
        }
    )


def _fenced(text: str) -> str:
    # The prompt tells the model that everything inside <contract_text> is content to read.
    # A document containing the closing tag could otherwise end that section early.
    return text.replace("</contract_text", "< /contract_text")


async def detect_contract(text: str, gemini: GeminiClient) -> DetectedContract:
    """Detect the language, host country, kind and job type of a contract, and read its parties.

    Args:
        text: The contract text from the extraction step (`contract_text`), in its original
            language. The caller has checked it is not empty.
        gemini: Client for the extraction tier call.

    Returns:
        The facts found. `host_country` is None when the contract is for a country outside
        SG, KR, MY, JP, HK, AU or does not show one: the caller then falls back to the
        worker's profile or asks. Other values are None when the document does not say.

    Raises:
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    detected = await gemini.generate_structured(
        operation=DETECT_PROMPT.key,
        tier=ModelTier.EXTRACTION,
        contents=DETECT_PROMPT.render_user(contract_text=_fenced(text)),
        response_model=DetectedContract,
        system_instruction=DETECT_PROMPT.system,
        # A classification: the same contract should always give the same answer.
        temperature=0.0,
    )
    return _clean(detected)
