from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.config import get_settings
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ContractBlock, DocumentKind, LaborLawContext, LaborLawRule
from app.schemas.contract_compare import (
    ClauseRisk,
    ComparedClause,
    ComparisonAnswer,
    ContractComparison,
    TermAssessment,
)
from app.services.contract.risk_scorer import score_contract

logger = logging.getLogger(__name__)

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records COMPARE_PROMPT.key / .version in the report's `prompt_versions`.
COMPARE_PROMPT = load_prompt("contract", "compare", 1)

COUNTRY_NAMES: dict[str, str] = {
    "SG": "Singapore",
    "KR": "South Korea",
    "MY": "Malaysia",
    "JP": "Japan",
    "HK": "Hong Kong",
    "AU": "Australia",
}
# A loan agreement is not work: labor law has nothing to say about its terms.
_COMPARABLE_KINDS = frozenset({"employment_contract", "recruitment_agreement"})
# Blocks that always hold a term; a paragraph may be an introduction and can be skipped.
_TERM_KINDS = frozenset({"clause", "list_item", "table"})
# Only a rule that actually regulates the matter can make a term illegal.
_REGULATED = frozenset({"regulated", "partly_regulated"})
# Words that name no particular law, so they cannot tell two references apart.
_COMMON_LAW_WORDS = frozenset(
    {"act", "and", "the", "for", "with", "part", "section", "schedule", "revised", "edition"}
)
_WORD = re.compile(r"[A-Za-z]{4,}|\d{4}")


class NotComparableError(Exception):
    """Only employment contracts and recruitment agreements are checked against labor law."""


class NoTermsError(Exception):
    """The model found no terms to assess in the blocks."""


def _block_text(block: ContractBlock) -> str:
    text = block.text.strip()
    return f"{block.number.strip()} {text}" if block.number else text


def render_blocks(blocks: list[ContractBlock]) -> str:
    """One line per block, "[id] (kind number, page) text"; a table's rows follow indented.

    Ids are 1-based positions in `blocks`, the handle the model answers with.
    """
    lines: list[str] = []
    for block_id, block in enumerate(blocks, start=1):
        label = f"{block.kind} {block.number.strip()}" if block.number else block.kind
        first, *rest = block.text.strip().splitlines() or [""]
        lines.append(f"[{block_id}] ({label}, p{block.page}) {first}")
        lines.extend(f"    {line}" for line in rest)
    # The prompt says everything inside <contract_blocks> is content. A document containing
    # the closing tag could otherwise end that section early.
    return "\n".join(lines).replace("</contract_blocks", "< /contract_blocks")


def _rules_json(law: LaborLawContext) -> str:
    """The rules as the model needs them: the job type's variant only, no references (code
    attaches those), no curation metadata. About a third smaller than the stored rules."""
    rules: list[dict[str, Any]] = []
    for rule in law.rules:
        variant = rule.applicable_variant
        entry: dict[str, Any] = {
            "category": rule.category,
            "coverage": rule.coverage,
            "title": rule.title,
            "summary": rule.summary,
            "requirements": variant.requirements,
        }
        if variant.limits:
            entry["limits"] = {
                name: limit.model_dump(exclude_none=True) for name, limit in variant.limits.items()
            }
        if rule.notes:
            entry["notes"] = rule.notes
        rules.append(entry)
    return json.dumps(rules, ensure_ascii=False)


def _words(text: str) -> set[str]:
    return {word.lower() for word in _WORD.findall(text)} - _COMMON_LAW_WORDS


def _law_reference(rule: LaborLawRule | None) -> str | None:
    """The rule's reference for the variant that was applied, as "law, section".

    A rule lists the laws of all its variants (SG rest days: the Employment Act for most
    workers, the Work Passes Regulations for domestic workers). The requirements name their
    own law in brackets, so the reference whose law shares the most words with them wins;
    the first reference is the fallback.
    """
    if rule is None or rule.coverage not in _REGULATED or not rule.references:
        return None
    requirement_words = _words(" ".join(rule.applicable_variant.requirements))

    def overlap(law: str) -> float:
        law_words = _words(law)
        return len(law_words & requirement_words) / len(law_words) if law_words else 0.0

    best = max(rule.references, key=lambda reference: overlap(reference.law))
    reference = best if overlap(best.law) > 0 else rule.references[0]
    return f"{reference.law}, {reference.section}"


def _clause(
    index: int,
    ids: list[int],
    term: TermAssessment,
    risk: ClauseRisk,
    rule: LaborLawRule | None,
    blocks: list[ContractBlock],
) -> ComparedClause:
    first = blocks[ids[0] - 1]
    recommendation = (term.recommendation or "").strip() or None
    return ComparedClause(
        index=index,
        number=first.number,
        page=first.page,
        text="\n".join(_block_text(blocks[i - 1]) for i in ids),
        category=term.category,
        risk=risk,
        law_reference=_law_reference(rule),
        explanation=term.explanation.strip(),
        recommendation=None if risk == "safe" else recommendation,
        block_ids=ids,
    )


def build_clauses(
    answer: ComparisonAnswer, blocks: list[ContractBlock], law: LaborLawContext
) -> tuple[list[ComparedClause], list[int]]:
    """Turn the model's answer into report clauses, trusting none of it blindly.

    - Block ids outside the contract, or already used by an earlier term, are dropped.
    - A "danger" without a rule that regulates the matter becomes "caution": only a curated
      rule can make a term illegal.
    - Law references come from the curated rule of the category, never from the model.

    Returns:
        The clauses in reading order, and the ids of term blocks no clause covers.
    """
    rules = {rule.category: rule for rule in law.rules}
    used: set[int] = set()
    kept: list[tuple[list[int], TermAssessment, ClauseRisk, LaborLawRule | None]] = []
    for term in answer.terms:
        ids = sorted({i for i in term.block_ids if 1 <= i <= len(blocks) and i not in used})
        if not ids:
            continue
        used.update(ids)
        rule = rules.get(term.category)
        risk = term.risk
        if risk == "danger" and (rule is None or rule.coverage not in _REGULATED):
            logger.info("compare_danger_downgraded category=%s", term.category)
            risk = "caution"
        kept.append((ids, term, risk, rule))

    kept.sort(key=lambda item: item[0][0])
    clauses = [
        _clause(index, ids, term, risk, rule, blocks)
        for index, (ids, term, risk, rule) in enumerate(kept, start=1)
    ]
    unassessed = [
        block_id
        for block_id, block in enumerate(blocks, start=1)
        if block.kind in _TERM_KINDS and block_id not in used
    ]
    if unassessed:
        # Ids only: block text can hold personal data and never goes to the logs.
        logger.warning("compare_unassessed_blocks count=%d ids=%s", len(unassessed), unassessed)
    return clauses, unassessed


async def compare_contract(
    blocks: list[ContractBlock],
    law: LaborLawContext,
    gemini: GeminiClient,
    document_kind: DocumentKind = "employment_contract",
) -> ContractComparison:
    """Check every term of a contract against the host country's labor law.

    Args:
        blocks: The contract's blocks from the extraction step, in reading order.
        law: The host country's rules for the worker's job type (step 3).
        gemini: Client for the reasoning tier call.
        document_kind: From the detection step; loan agreements and other documents are not
            checked against labor law.

    Returns:
        The assessed terms with law references, the health score, risk level and counts.

    Raises:
        NotComparableError: `document_kind` is not a contract labor law applies to.
        NoTermsError: No term of the contract could be assessed.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    if document_kind not in _COMPARABLE_KINDS:
        raise NotComparableError(f"labor law is not checked for {document_kind!r}")

    answer = await gemini.generate_structured(
        operation=COMPARE_PROMPT.key,
        tier=ModelTier.REASONING,
        contents=COMPARE_PROMPT.render_user(
            job_type=law.job_type.replace("_", " "),
            host_country_name=COUNTRY_NAMES[law.country],
            law_rules_json=_rules_json(law),
            contract_blocks=render_blocks(blocks),
        ),
        response_model=ComparisonAnswer,
        system_instruction=COMPARE_PROMPT.system,
        timeout_seconds=get_settings().gemini_compare_timeout_seconds,
    )
    clauses, unassessed = build_clauses(answer, blocks, law)
    if not clauses:
        raise NoTermsError("no contract term could be assessed")

    health_score, risk_level, counts = score_contract(clause.risk for clause in clauses)
    return ContractComparison(
        country=law.country,
        job_type=law.job_type,
        law_version=law.law_version,
        health_score=health_score,
        risk_level=risk_level,
        clause_counts=counts,
        summary=answer.summary.strip(),
        clauses=clauses,
        unassessed_block_ids=unassessed,
    )
