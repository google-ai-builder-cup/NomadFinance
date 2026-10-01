"""The complaint letter inside the pipeline (NF-P2-007, step 6 of NF-P2-006).

A report is worth having without its letter, so a failed letter never throws the analysis
away. But a failure that may not repeat must not be cached as "no letter": the contract is
marked `complaint_pending` and the next analyze writes only the letter. That covers Gemini
(overloaded, timeout, bad answer) and a missing template: all six host countries have a
curated one, so a missing template means it was not loaded into that Firestore yet, as
happened in production. A contract analysed before that rule (no letter, nothing pending)
is caught by `letter_missing` instead.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.integrations.gemini import (
    GeminiClient,
    GeminiError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.repositories.complaint_template_repo import ComplaintTemplateRepository
from app.repositories.contract_repo import ContractRepository
from app.schemas.contract import HostCountryCode, ReportLanguage
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_complaint import ContractComplaint, ContractFacts
from app.schemas.contract_pipeline import ContractReport, LetterPendingReason
from app.services.contract.complaint import (
    ComplaintIncompleteError,
    ComplaintTemplateNotFoundError,
    generate_complaint,
)

logger = logging.getLogger(__name__)


async def write_letter(
    host: HostCountryCode,
    clauses: list[ComparedClause],
    facts: ContractFacts,
    language: ReportLanguage,
    templates: ComplaintTemplateRepository,
    gemini: GeminiClient,
) -> tuple[ContractComplaint | None, LetterPendingReason | None]:
    """The complaint letter, or why it is still pending (worth trying again later)."""
    try:
        return await generate_complaint(host, clauses, facts, language, templates, gemini), None
    except ComplaintTemplateNotFoundError:
        reason: LetterPendingReason = "no_template"
        logger.warning("pipeline_letter_pending reason=no_template country=%s", host)
    except GeminiRateLimitError as exc:
        reason = "ai_daily_limit" if exc.daily else "ai_busy"
        logger.warning("pipeline_letter_pending reason=%s", reason)
    except (GeminiUnavailableError, GeminiTimeoutError):
        reason = "ai_busy"
        logger.warning("pipeline_letter_pending reason=ai_busy")
    except (GeminiError, ComplaintIncompleteError) as exc:
        reason = "ai_failed"
        logger.warning("pipeline_letter_pending reason=ai_failed error=%s", type(exc).__name__)
    return None, reason


async def add_pending_letter(
    contracts: ContractRepository,
    templates: ComplaintTemplateRepository,
    gemini: GeminiClient,
    uid: str,
    contract_id: str,
    contract: dict[str, Any],
    language: ReportLanguage,
) -> LetterPendingReason | None:
    """Write the letter an earlier failure left out and add it to every stored report.

    Returns:
        None when the letter was written, else why it is still pending (also stored on the
        contract, so a reopened report can say why).
    """
    stored = await run_in_threadpool(contracts.get_report, uid, contract_id, "en")
    if stored is None:
        return "ai_failed"
    source = ContractReport.model_validate(stored)
    clauses = [ComparedClause.model_validate(clause.model_dump()) for clause in source.clauses]
    facts = ContractFacts.model_validate(contract.get("extracted") or {})
    letter, reason = await write_letter(
        contract["host_country"], clauses, facts, language, templates, gemini
    )
    if reason is not None:
        await run_in_threadpool(
            contracts.update,
            uid,
            contract_id,
            {"complaint_pending": True, "complaint_pending_reason": reason},
        )
        return reason
    complaint = letter.model_dump(mode="json") if letter is not None else None
    for report_language in contract.get("report_languages", []):
        report = await run_in_threadpool(contracts.get_report, uid, contract_id, report_language)
        if report is not None:
            await run_in_threadpool(
                contracts.save_report, uid, contract_id, report | {"complaint": complaint}
            )
    await run_in_threadpool(
        contracts.update,
        uid,
        contract_id,
        {"complaint_pending": None, "complaint_pending_reason": None},
    )
    return None


async def letter_missing(
    contracts: ContractRepository, uid: str, contract_id: str, danger_count: int
) -> bool:
    """A stored analysis with an unlawful clause but no letter and nothing marked pending.

    Only contracts analysed while a missing template was still treated as final end up like
    this; reading `reports/en` tells them apart from a letter that exists.
    """
    if danger_count == 0:
        return False
    stored = await run_in_threadpool(contracts.get_report, uid, contract_id, "en")
    return stored is not None and stored.get("complaint") is None
