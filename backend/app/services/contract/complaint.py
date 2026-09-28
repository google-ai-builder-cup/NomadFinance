from __future__ import annotations

import json

from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.repositories.complaint_template_repo import ComplaintTemplateRepository
from app.schemas.contract import HostCountryCode, ReportLanguage
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_complaint import (
    ComplaintAnswer,
    ComplaintTemplate,
    ContractComplaint,
    ContractFacts,
    LetterLanguage,
)
from app.utils.i18n import language_name

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records COMPLAINT_PROMPT.key / .version in the report's `prompt_versions`.
COMPLAINT_PROMPT = load_prompt("contract", "complaint", 2)

# Every violation uses the `general` template: category-specific letters are not curated
# (NF-P2-006), and the clause categories are already spelled out inside the letter.
TEMPLATE_TYPE = "general"

LETTER_LANGUAGE_NAMES: dict[LetterLanguage, str] = {
    "en": "English",
    "ko": "Korean",
    "ms": "Malay (Bahasa Melayu)",
    "ja": "Japanese",
}


class NoViolationsError(Exception):
    """No clause has the risk `danger`, so there is nothing to complain about."""


class ComplaintTemplateNotFoundError(Exception):
    """No curated complaint template is loaded for this country (`data-scripts` loader)."""


class ComplaintIncompleteError(Exception):
    """Gemini's answer is unusable: an empty letter, a missing copy or unfilled markers."""


def _untag(raw: str, *tags: str) -> str:
    """Stop text a worker supplied from closing one of the prompt's data blocks early.

    The prompt says everything inside a block is data; a clause copied from a contract could
    otherwise contain the closing tag.
    """
    for tag in tags:
        raw = raw.replace(f"</{tag}", f"< /{tag}")
    return raw


def _violations_json(clauses: list[ComparedClause]) -> str:
    payload = [
        {
            "index": clause.index,
            "category": clause.category,
            "law_reference": clause.law_reference,
            "text": clause.text,
            "explanation": clause.explanation,
        }
        for clause in clauses
    ]
    return _untag(json.dumps(payload, ensure_ascii=False), "violations")


def _facts_json(facts: ContractFacts) -> str:
    return _untag(facts.model_dump_json(), "contract_facts")


def _template_json(template: ComplaintTemplate) -> str:
    # `channels` and `reviewed_on` stay out: the letter never quotes them, and code attaches
    # the channels to the result from the template itself.
    return json.dumps(
        {
            "authority_name": template.authority_name,
            "letter_language": template.letter_language,
            "letter_language_name": LETTER_LANGUAGE_NAMES[template.letter_language],
            "template_text": template.template_text,
            "placeholders": template.placeholders,
        },
        ensure_ascii=False,
    )


def _check_answer(
    answer: ComplaintAnswer, template: ComplaintTemplate, same_language: bool
) -> str | None:
    """Return the worker's copy (None when it is the letter itself), or raise if unusable."""
    if not answer.letter_text:
        raise ComplaintIncompleteError("the answer has no letter text")
    if not same_language and not answer.worker_copy:
        raise ComplaintIncompleteError("the answer has no copy in the worker's language")
    worker_copy = None if same_language else answer.worker_copy
    for text in (answer.letter_text, worker_copy or ""):
        unfilled = [name for name in template.placeholders if "{{" + name + "}}" in text]
        if unfilled:
            raise ComplaintIncompleteError(f"placeholders left unfilled: {unfilled}")
    return worker_copy


async def generate_complaint(
    host_country: HostCountryCode,
    clauses: list[ComparedClause],
    facts: ContractFacts,
    worker_language: ReportLanguage,
    repo: ComplaintTemplateRepository,
    gemini: GeminiClient,
) -> ContractComplaint:
    """Write the complaint letter for the danger clauses of a contract comparison.

    Args:
        host_country: The contract's host country; picks the authority and letter language.
        clauses: The comparison's `clauses` from step 4. Only those with risk `danger` are
            the violations; the rest are ignored.
        facts: Employer, agency and salary from step 2.
        worker_language: The worker's language, for their readable copy of the letter.
        repo: Repository for the `complaint_templates` collection.
        gemini: Client for the reasoning tier call.

    Returns:
        The letter in the authority's language and, unless that is also the worker's
        language, the same letter in `worker_language`. The authority name, channels and
        template type come from the curated template, never from Gemini. The worker's own
        details are left as [bracketed blanks].

    Raises:
        NoViolationsError: No clause has the risk `danger`.
        ComplaintTemplateNotFoundError: No template is loaded for `host_country`.
        ComplaintIncompleteError: The answer has no letter, no worker copy, or unfilled markers.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    violations = sorted((c for c in clauses if c.risk == "danger"), key=lambda c: c.index)
    if not violations:
        raise NoViolationsError("no clause has the risk 'danger'")

    payload = await run_in_threadpool(repo.get_template, host_country, TEMPLATE_TYPE)
    if payload is None:
        raise ComplaintTemplateNotFoundError(f"no complaint template loaded for {host_country!r}")
    template = ComplaintTemplate.model_validate(payload)

    answer = await gemini.generate_structured(
        operation=COMPLAINT_PROMPT.key,
        tier=ModelTier.REASONING,
        contents=COMPLAINT_PROMPT.render_user(
            worker_language=language_name(worker_language),
            template_json=_template_json(template),
            violations_json=_violations_json(violations),
            contract_facts_json=_facts_json(facts),
        ),
        response_model=ComplaintAnswer,
        system_instruction=COMPLAINT_PROMPT.system,
        timeout_seconds=get_settings().gemini_complaint_timeout_seconds,
    )
    worker_copy = _check_answer(answer, template, template.letter_language == worker_language)
    return ContractComplaint(
        template_type=TEMPLATE_TYPE,
        authority_name=template.authority_name,
        authority_url=template.authority_url,
        channels=template.channels,
        letter_language=template.letter_language,
        letter_text=answer.letter_text,
        worker_language=worker_language,
        worker_copy=worker_copy,
        violation_count=len(violations),
    )
