from __future__ import annotations

import asyncio
import json
import logging
import re
import unicodedata

from app.integrations.gemini import (
    GeminiClient,
    GeminiError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUnavailableError,
    ModelTier,
)
from app.prompts.loader import load_prompt
from app.repositories.scam_taxonomy_repo import ScamTaxonomy
from app.schemas.scam import (
    BenignExplainer,
    CorridorId,
    Explainer,
    Language,
    ScamDetails,
    ScamExplainer,
    ScamVerdict,
    TacticExplanation,
)
from app.schemas.scam_explain import BenignReassurance, ScamExplanation
from app.utils.corridors import CORRIDOR_HOST_HOME
from app.utils.i18n import language_name

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup. The check
# records EXPLAIN_PROMPT.key / .version (or REASSURE_PROMPT's) in `prompt_versions`.
EXPLAIN_PROMPT = load_prompt("scam", "explain", 1)
REASSURE_PROMPT = load_prompt("scam", "reassure", 1)

# A scam is explained on the reasoning tier, which on 2026-10-06 took 18 s to its first piece
# with default thinking (D-115). Writing six lines of plain language needs little thinking, so
# the budget is small; and the whole step is time-boxed so the worker keeps the verdict instead
# of waiting past the client's 60 s (contract: "Time"). The numbers are first guesses to be
# tuned from live timings (D-138).
#
# Measured live on the free tier on 2026-10-07: of 10 scam explainers on the reasoning tier, 2
# finished (9 s and 18 s); the other 8 were refused with 429 or 503, or ran out the box. So the
# reasoning tier gets only PRIMARY_TIMEOUT_SECONDS, and when it is busy, rate limited or slow the
# same prompt is tried once on the classification tier in what is left of the box.
THINKING_BUDGET = 256
PRIMARY_TIMEOUT_SECONDS = 20.0
STEP_TIMEOUT_SECONDS = 40.0
# The failures of capacity, not of the answer: another tier may well be free.
_CAPACITY_ERRORS = (GeminiRateLimitError, GeminiUnavailableError, GeminiTimeoutError)
_TEMPERATURE = 0.3
_MAX_TEXT_CHARS = 400  # a runaway answer is not a grade-6 explanation
_NEEDED_STEPS = 3
_FALLBACK_TACTICS = 2

# The host countries of the six corridors; the explainer names one so a helpline fits the worker.
_HOST_NAMES = {"SG": "Singapore", "AU": "Australia", "MY": "Malaysia", "JP": "Japan"}

_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_TOKEN = re.compile(r"\[[A-Z_]{2,12}\]")  # [PHONE], [URL]: the redactor's own tokens
_NUMBER = re.compile(r"\d(?:[\d \-().]{5,}\d)")
_DEVANAGARI = (0x0900, 0x097F)
_BENGALI = (0x0980, 0x09FF)
_SCRIPT = {"hi": _DEVANAGARI, "ne": _DEVANAGARI, "bn": _BENGALI}


class ExplainerRejectedError(ValueError):
    """The model answered, but the answer cannot be shown to a worker."""


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)


def _letters_in(text: str, span: tuple[int, int]) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    return sum(span[0] <= ord(ch) <= span[1] for ch in letters) / len(letters) if letters else 0.0


def _in_language(text: str, language: Language) -> bool:
    """Right script for the worker's language. Latin-script languages are not told apart: the
    check catches an answer in Devanagari for an English reader, not Tagalog for Indonesian."""
    span = _SCRIPT.get(language)
    if span is not None:
        return _letters_in(text, span) >= 0.5
    letters = [ch for ch in text if ch.isalpha()]
    return not letters or sum(ord(ch) < 0x250 for ch in letters) / len(letters) >= 0.9


def _checked(text: str, allowed_digits: str) -> str:
    """One sentence group that is safe to show: no link, address, token or number of its own.

    A scam message can try to plant its own contact point in the "next steps"; the prompt forbids
    it and this refuses it. A helpline number is allowed only if the curated notes gave it.
    """
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > _MAX_TEXT_CHARS:
        raise ExplainerRejectedError("empty or too long")
    if _URL.search(cleaned) or _EMAIL.search(cleaned) or _TOKEN.search(cleaned):
        raise ExplainerRejectedError("contains a link, address or token")
    for run in _NUMBER.findall(_ascii_digits(cleaned)):
        if re.sub(r"\D", "", run) not in allowed_digits:
            raise ExplainerRejectedError("contains a number the notes did not give")
    return cleaned


def _explained_tactics(verdict: ScamVerdict, taxonomy: ScamTaxonomy) -> list[str]:
    """The tactics to explain: the detected ones, or, when none was, the type's usual ones, so
    `why_it_works` is never empty."""
    detected = [t for t in verdict.tactics if t in taxonomy.tactics]
    if detected:
        return detected
    related = taxonomy.types.get(verdict.scam_type or "", {}).get("related_tactics", [])
    usual = [t for t in related if t in taxonomy.tactics][:_FALLBACK_TACTICS]
    return usual or list(taxonomy.tactics)[:1]


def _notes(taxonomy: ScamTaxonomy, verdict: ScamVerdict, tactics: list[str]) -> tuple[str, str]:
    """What the curated taxonomy says about the tactics and about staying safe, as grounding."""
    tactic_notes = [
        {
            "id": t,
            "label": taxonomy.tactics[t].get("label"),
            "how_it_works": taxonomy.tactics[t].get("how_it_works"),
        }
        for t in tactics
    ]
    safe = []
    type_advice = taxonomy.types.get(verdict.scam_type or "", {}).get("safe_response")
    if type_advice:
        safe.append({"for": f"scam type {verdict.scam_type}", "advice": type_advice})
    safe += [
        {"for": f"tactic {t}", "advice": taxonomy.tactics[t]["safe_response"]}
        for t in tactics
        if taxonomy.tactics[t].get("safe_response")
    ]
    return json.dumps(tactic_notes, ensure_ascii=False), json.dumps(safe, ensure_ascii=False)


def _clean_scam(
    raw: ScamExplanation, tactics: list[str], language: Language, allowed_digits: str
) -> ScamExplainer:
    by_tactic: dict[str, str] = {}
    for item in raw.why_it_works:
        tactic = item.tactic.strip()
        if tactic in tactics and tactic not in by_tactic:
            by_tactic[tactic] = _checked(item.text, allowed_digits)
    missing = [t for t in tactics if t not in by_tactic]
    if missing:
        raise ExplainerRejectedError(f"no explanation for {missing}")
    steps = [step for step in raw.next_steps if step.strip()]
    if len(steps) < _NEEDED_STEPS:
        raise ExplainerRejectedError(f"{len(steps)} next steps, needs {_NEEDED_STEPS}")
    explainer = ScamExplainer(
        kind="scam",
        language=language,
        why_it_works=[TacticExplanation(tactic=t, text=by_tactic[t]) for t in tactics],
        scammer_wants=_checked(raw.scammer_wants, allowed_digits),
        next_steps=[_checked(s, allowed_digits) for s in steps[:_NEEDED_STEPS]],
    )
    written = [e.text for e in explainer.why_it_works] + explainer.next_steps
    _require_language(" ".join([explainer.scammer_wants, *written]), language)
    return explainer


def _clean_benign(raw: BenignReassurance, language: Language) -> BenignExplainer:
    explainer = BenignExplainer(
        kind="benign",
        language=language,
        reassurance=_checked(raw.reassurance, ""),
        tip=_checked(raw.tip, ""),
    )
    _require_language(explainer.reassurance + " " + explainer.tip, language)
    return explainer


def _require_language(text: str, language: Language) -> None:
    if not _in_language(text, language):
        raise ExplainerRejectedError(f"not written in {language}")


def _host_country(corridor_id: CorridorId | None) -> str:
    pair = CORRIDOR_HOST_HOME.get(corridor_id or "")
    return _HOST_NAMES[pair[0]] if pair else "unknown"


async def _explain_scam(
    redacted_text: str,
    verdict: ScamVerdict,
    details: ScamDetails,
    language: Language,
    corridor_id: CorridorId | None,
    taxonomy: ScamTaxonomy,
    gemini: GeminiClient,
    tier: ModelTier,
) -> ScamExplainer:
    tactics = _explained_tactics(verdict, taxonomy)
    tactic_notes, safe_notes = _notes(taxonomy, verdict, tactics)
    raw = await gemini.generate_structured(
        operation=EXPLAIN_PROMPT.key,
        tier=tier,
        contents=EXPLAIN_PROMPT.render_user(
            language=language_name(language),
            host_country=_host_country(corridor_id),
            verdict_json=verdict.model_dump_json(include={"scam_type", "risk_level"}),
            details_json=details.model_dump_json(exclude_none=True),
            tactics_json=json.dumps(tactics),
            tactic_notes_json=tactic_notes,
            safe_response_json=safe_notes,
            message=_fenced(redacted_text),
        ),
        response_model=ScamExplanation,
        system_instruction=EXPLAIN_PROMPT.system,
        temperature=_TEMPERATURE,
        # Only the reasoning tier thinks much; the fallback tier is asked for no thinking.
        thinking_budget=THINKING_BUDGET if tier is ModelTier.REASONING else None,
    )
    # Digits only, so a helpline the notes write as "1300 292 371" matches a step that writes it
    # as "1300-292-371".
    allowed_digits = re.sub(r"\D", "", _ascii_digits(safe_notes))
    return _clean_scam(raw, tactics, language, allowed_digits)


async def _explain_benign(
    redacted_text: str, details: ScamDetails, language: Language, gemini: GeminiClient
) -> BenignExplainer:
    # The classification tier: a reassurance needs no reasoning, and the reasoning tier's
    # quota is for scams (design 5.2).
    raw = await gemini.generate_structured(
        operation=REASSURE_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=REASSURE_PROMPT.render_user(
            language=language_name(language),
            details_json=details.model_dump_json(exclude_none=True),
            message=_fenced(redacted_text),
        ),
        response_model=BenignReassurance,
        system_instruction=REASSURE_PROMPT.system,
        temperature=_TEMPERATURE,
    )
    return _clean_benign(raw, language)


async def _explain_scam_with_fallback(
    redacted_text: str,
    verdict: ScamVerdict,
    details: ScamDetails,
    language: Language,
    corridor_id: CorridorId | None,
    taxonomy: ScamTaxonomy,
    gemini: GeminiClient,
) -> ScamExplainer:
    """The reasoning tier first, for at most PRIMARY_TIMEOUT_SECONDS, then the classification tier.

    An answer that fails the checks is not retried on the other tier: the model answered, and
    asking another one the same thing is not what a busy server needs.
    """
    args = (redacted_text, verdict, details, language, corridor_id, taxonomy, gemini)
    try:
        async with asyncio.timeout(PRIMARY_TIMEOUT_SECONDS):
            return await _explain_scam(*args, ModelTier.REASONING)
    except (TimeoutError, *_CAPACITY_ERRORS) as exc:
        reason = "primary_timeout" if isinstance(exc, TimeoutError) else type(exc).__name__
        logger.warning("scam_explainer_fallback reason=%s tier=classification", reason)
    return await _explain_scam(*args, ModelTier.CLASSIFICATION)


def _fenced(text: str) -> str:
    # The prompts tell the model that everything inside <message> is data. A message that
    # contains the closing tag could otherwise end that section early.
    return text.replace("</message", "< /message")


async def explain_message(
    redacted_text: str,
    verdict: ScamVerdict,
    details: ScamDetails,
    *,
    language: Language,
    corridor_id: CorridorId | None,
    taxonomy: ScamTaxonomy,
    gemini: GeminiClient,
) -> Explainer | None:
    """Write the explainer for a classified message, or None when it cannot be made.

    A failure here never fails the check: the worker keeps the verdict and the contract's
    `explainer_status: "unavailable"` says the explanation is missing (and a stored check with
    no explainer is not served from the cache, so the next try makes one).

    Args:
        redacted_text: The message after `redact_text`, never the raw text.
        verdict: What the classifier decided; its tactics are what gets explained.
        details: What the message asks for, to make "what the scammer wants" concrete.
        language: The worker's language (not the message's): the explainer is written in it.
        corridor_id: The worker's route, for the host country's helpline; may be None.
        taxonomy: The curated notes the explanation is grounded in.
        gemini: Client for the explainer call.
    """
    kind = "scam" if verdict.is_scam else "benign"
    try:
        async with asyncio.timeout(STEP_TIMEOUT_SECONDS):
            if verdict.is_scam:
                return await _explain_scam_with_fallback(
                    redacted_text, verdict, details, language, corridor_id, taxonomy, gemini
                )
            return await _explain_benign(redacted_text, details, language, gemini)
    except TimeoutError:
        logger.warning("scam_explainer_unavailable kind=%s reason=step_timeout", kind)
    except GeminiError as exc:
        logger.warning("scam_explainer_unavailable kind=%s reason=%s", kind, type(exc).__name__)
    except ExplainerRejectedError as exc:
        # The reason names a rule, never the model's words: they may echo the message.
        logger.warning("scam_explainer_unavailable kind=%s reason=rejected (%s)", kind, exc)
    return None


__all__ = ["EXPLAIN_PROMPT", "REASSURE_PROMPT", "explain_message"]
