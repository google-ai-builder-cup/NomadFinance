"""The complaint letter inside the pipeline (NF-P2-007, step 6 of NF-P2-006).

A report is worth having without its letter, so a failed letter never throws the analysis
away. But a failure Gemini might not repeat (overloaded, timeout, bad answer) must not be
cached as "no letter": the contract is marked `complaint_pending` and the next analyze writes
only the letter. A country without a template is final: no letter, nothing pending.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.integrations.gemini import GeminiClient, GeminiError
from app.repositories.complaint_template_repo import ComplaintTemplateRepository
from app.repositories.contract_repo import ContractRepository
from app.schemas.contract import HostCountryCode, ReportLanguage
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_complaint import ContractComplaint, ContractFacts
from app.schemas.contract_pipeline import ContractReport
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
) -> tuple[ContractComplaint | None, bool]:
    """The complaint letter, and whether it is still pending (worth trying again later)."""
    try:
        return await generate_complaint(host, clauses, facts, language, templates, gemini), False
    except ComplaintTemplateNotFoundError:
        logger.warning("pipeline_letter_skipped reason=no_template country=%s", host)
        return None, False
    except (GeminiError, ComplaintIncompleteError) as exc:
        logger.warning("pipeline_letter_pending reason=%s", type(exc).__name__)
        return None, True


async def add_pending_letter(
    contracts: ContractRepository,
    templates: ComplaintTemplateRepository,
    gemini: GeminiClient,
    uid: str,
    contract_id: str,
    contract: dict[str, Any],
    language: ReportLanguage,
) -> bool:
    """Write the letter an earlier failure left out and add it to every stored report.

    Returns:
        True when the letter is no longer pending (written, or no template exists).
    """
    stored = await run_in_threadpool(contracts.get_report, uid, contract_id, "en")
    if stored is None:
        return False
    source = ContractReport.model_validate(stored)
    clauses = [ComparedClause.model_validate(clause.model_dump()) for clause in source.clauses]
    facts = ContractFacts.model_validate(contract.get("extracted") or {})
    letter, pending = await write_letter(
        contract["host_country"], clauses, facts, language, templates, gemini
    )
    if pending:
        return False
    complaint = letter.model_dump(mode="json") if letter is not None else None
    for report_language in contract.get("report_languages", []):
        report = await run_in_threadpool(contracts.get_report, uid, contract_id, report_language)
        if report is not None:
            await run_in_threadpool(
                contracts.save_report, uid, contract_id, report | {"complaint": complaint}
            )
    await run_in_threadpool(contracts.update, uid, contract_id, {"complaint_pending": None})
    return True
