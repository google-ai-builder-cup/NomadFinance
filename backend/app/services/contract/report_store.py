"""Stored Contract Shield reports and the cache rule (NF-P2-007).

A stored analysis or report is reused while its file hash, law version and prompt versions
all match what would be used now (docs/data-model/versioning.md). The English report is the
one the comparison writes; every other language is a translation of it, made once.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi.concurrency import run_in_threadpool

from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.repositories.contract_repo import ContractRepository
from app.repositories.labor_law_repo import LaborLawRepository
from app.schemas.contract import HostCountryCode, JobTypeId, ReportLanguage
from app.schemas.contract_compare import ClauseCounts, ComparedClause
from app.schemas.contract_complaint import ContractComplaint
from app.schemas.contract_pipeline import ContractAnalysis, ContractReport
from app.schemas.contract_translate import TranslatedClause
from app.services.contract.comparator import COMPARE_PROMPT
from app.services.contract.complaint import COMPLAINT_PROMPT
from app.services.contract.detector import DETECT_PROMPT
from app.services.contract.extractor import EXTRACT_PROMPT
from app.services.contract.translator import TRANSLATE_PROMPT, translate_report

SOURCE_LANGUAGE: ReportLanguage = "en"


class ContractNotFoundError(Exception):
    """No contract with this id for this user."""


class ReportNotReadyError(Exception):
    """The contract has no current analysis yet: run analyze first."""


def current_prompt_versions() -> dict[str, int]:
    """The prompt versions the code uses now; a stored result made with others is stale."""
    prompts = (EXTRACT_PROMPT, DETECT_PROMPT, COMPARE_PROMPT, TRANSLATE_PROMPT, COMPLAINT_PROMPT)
    return {prompt.key: prompt.version for prompt in prompts}


def model_ids() -> dict[str, str]:
    """The model behind each tier, stored with every result (ADR-002 lets it change)."""
    settings = get_settings()
    return {
        "extraction": settings.gemini_model_extraction,
        "reasoning": settings.gemini_model_reasoning,
        "classification": settings.gemini_model_classification,
    }


def is_current(stored: dict[str, Any], digest: str, law_version: int | None) -> bool:
    """Whether a stored analysis or report may be reused: all cache keys still match."""
    return (
        stored.get("content_hash", digest) == digest
        and law_version is not None
        and stored.get("law_version") == law_version
        and stored.get("prompt_versions") == current_prompt_versions()
    )


def build_report(
    language: ReportLanguage,
    full_text: str,
    summary: str,
    clauses: list[TranslatedClause],
    complaint: ContractComplaint | None,
    digest: str,
    law_version: int,
) -> ContractReport:
    return ContractReport(
        language=language,
        is_source=language == SOURCE_LANGUAGE,
        full_text=full_text,
        summary=summary,
        clauses=clauses,
        complaint=complaint,
        content_hash=digest,
        law_version=law_version,
        prompt_versions=current_prompt_versions(),
        models=model_ids(),
    )


async def current_report(
    contracts: ContractRepository,
    uid: str,
    contract_id: str,
    digest: str,
    language: str,
    law_version: int | None,
) -> ContractReport | None:
    """The stored report in `language`, if there is one and it is still current."""
    report = await run_in_threadpool(contracts.get_report, uid, contract_id, language)
    if report is None or not is_current(report, digest, law_version):
        return None
    return ContractReport.model_validate(report)


async def save_report(
    contracts: ContractRepository, uid: str, contract_id: str, report: ContractReport
) -> None:
    await run_in_threadpool(contracts.save_report, uid, contract_id, report.model_dump(mode="json"))


async def translate_and_store(
    contracts: ContractRepository,
    gemini: GeminiClient,
    uid: str,
    contract_id: str,
    source: ContractReport,
    language: ReportLanguage,
) -> ContractReport:
    """Translate the English report into `language` (step 5), store it and return it."""
    clauses = [ComparedClause.model_validate(clause.model_dump()) for clause in source.clauses]
    translated = await translate_report(source.full_text, source.summary, clauses, language, gemini)
    report = build_report(
        language,
        translated.full_text,
        translated.summary,
        translated.clauses,
        # The letter to the authority is the same in every language; the worker's own copy
        # stays in the language of the analysis that wrote it.
        source.complaint,
        source.content_hash,
        source.law_version,
    )
    await save_report(contracts, uid, contract_id, report)
    return report


async def ensure_report(
    contracts: ContractRepository,
    laws: LaborLawRepository,
    gemini: GeminiClient,
    uid: str,
    contract_id: str,
    language: ReportLanguage,
) -> ContractReport:
    """The report in `language`: served from Firestore if current, else translated once.

    This is the report language switch (NF-P2-012): no re-upload, no new analysis.

    Raises:
        ContractNotFoundError: No such contract for this user.
        ReportNotReadyError: No current analysis to translate: run analyze first.
        TranslationIncompleteError, GeminiError: The translation failed.
    """
    contract = await run_in_threadpool(contracts.get, uid, contract_id)
    if contract is None:
        raise ContractNotFoundError(contract_id)
    host = contract.get("host_country")
    if host is None:
        raise ReportNotReadyError(contract_id)
    digest: str = contract["content_hash"]
    law_version = await run_in_threadpool(laws.get_version, host)
    stored = await current_report(contracts, uid, contract_id, digest, language, law_version)
    if stored is not None:
        return stored
    if not is_current(contract, digest, law_version):
        raise ReportNotReadyError(contract_id)
    source = await current_report(contracts, uid, contract_id, digest, SOURCE_LANGUAGE, law_version)
    if source is None:
        raise ReportNotReadyError(contract_id)
    return await translate_and_store(contracts, gemini, uid, contract_id, source, language)


def stored_analysis(
    contract_id: str, contract: dict[str, Any], language: ReportLanguage, *, cached: bool
) -> ContractAnalysis:
    """The analyze response, built from the stored contract document."""
    languages = sorted(set(contract.get("report_languages", [])) | {SOURCE_LANGUAGE, language})
    return ContractAnalysis(
        contract_id=contract_id,
        status="completed",
        cached=cached,
        host_country=contract["host_country"],
        job_type=contract["job_type"],
        health_score=contract["health_score"],
        risk_level=contract["risk_level"],
        clause_counts=ClauseCounts.model_validate(contract["clause_counts"]),
        report_language=language,
        report_languages=cast(list[ReportLanguage], languages),
        complaint_pending=bool(contract.get("complaint_pending")),
    )


async def reuse_analysis(
    contracts: ContractRepository,
    laws: LaborLawRepository,
    gemini: GeminiClient,
    uid: str,
    contract_id: str,
    contract: dict[str, Any],
    chosen_country: HostCountryCode | None,
    chosen_job: JobTypeId | None,
    language: ReportLanguage,
) -> ContractAnalysis | None:
    """The stored analysis while it is current, translating only a missing language.

    None when there is none, it is stale, or the worker now chose a different country or job
    than it used: the caller then runs the analysis again.
    """
    host = contract.get("host_country")
    if host is None or "health_score" not in contract:
        return None
    if chosen_country not in (None, host) or chosen_job not in (None, contract.get("job_type")):
        return None
    digest: str = contract["content_hash"]
    law_version = await run_in_threadpool(laws.get_version, host)
    if not is_current(contract, digest, law_version):
        return None
    source = await current_report(contracts, uid, contract_id, digest, SOURCE_LANGUAGE, law_version)
    if source is None:
        return None
    if await current_report(contracts, uid, contract_id, digest, language, law_version) is None:
        await translate_and_store(contracts, gemini, uid, contract_id, source, language)
    await run_in_threadpool(
        contracts.update, uid, contract_id, {"status": "completed", "step": None, "error": None}
    )
    return stored_analysis(contract_id, contract, language, cached=True)
