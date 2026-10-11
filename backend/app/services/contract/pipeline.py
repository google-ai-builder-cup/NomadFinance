"""Contract Shield analysis (NF-P2-007): steps 2 to 6 on an uploaded contract.

Step 1 runs at upload (upload.py). Stored results are reused while current (report_store).
The contract document's `status` and `step` show progress to the app while this runs. See
docs/pipelines/contract-shield.md.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi.concurrency import run_in_threadpool

from app.core.cache import log_cache_lookup
from app.integrations.gemini import (
    GeminiClient,
    GeminiError,
    GeminiRateLimitError,
    GeminiTimeoutError,
    GeminiUnavailableError,
)
from app.repositories.complaint_template_repo import ComplaintTemplateRepository
from app.repositories.contract_repo import ContractRepository
from app.repositories.fib_repo import FibRepository
from app.repositories.labor_law_repo import LaborLawRepository
from app.repositories.radar_repo import RadarRepository
from app.repositories.user_repo import UserRepository
from app.schemas.contract import ContractBlock, HostCountryCode, JobTypeId, ReportLanguage
from app.schemas.contract_complaint import ContractFacts
from app.schemas.contract_pipeline import (
    AnalyzeRequest,
    ContractAnalysis,
    PipelineErrorCode,
    PipelineStep,
)
from app.schemas.contract_translate import TranslatedClause
from app.services.contract.comparator import NotComparableError, NoTermsError, compare_contract
from app.services.contract.detector import detect_contract
from app.services.contract.letter import add_pending_letter, letter_missing, write_letter
from app.services.contract.rag import LaborLawNotFoundError, get_labor_law_context
from app.services.contract.report_store import (
    SOURCE_LANGUAGE,
    ContractNotFoundError,
    build_report,
    current_prompt_versions,
    model_ids,
    reuse_analysis,
    save_report,
    stored_analysis,
    translate_and_store,
)
from app.services.cross_pillar.contract_to_fib import log_contract_income
from app.services.cross_pillar.contract_to_radar import create_radar_signals

logger = logging.getLogger(__name__)

HOST_COUNTRIES = frozenset({"SG", "KR", "MY", "JP", "HK", "AU"})
REPORT_LANGUAGES = frozenset({"en", "hi", "tl", "id", "ne", "bn"})
# A request that died mid-analysis leaves `processing` behind; after this long a new analyze
# may take over. Longer than one full run with retries (Cloud Run request timeout, 900 s).
STALE_ANALYSIS = timedelta(minutes=16)


class AnalysisInProgressError(Exception):
    """Another request is analysing this contract right now."""


class PipelineStopError(Exception):
    """The analysis stopped for a reason the worker can act on; stored on the contract."""

    def __init__(self, step: PipelineStep, code: PipelineErrorCode) -> None:
        super().__init__(f"{step}: {code}")
        self.step = step
        self.code = code


@dataclass(frozen=True)
class PipelineDeps:
    """Everything the pipeline talks to, so tests can swap each one."""

    gemini: GeminiClient
    contracts: ContractRepository
    users: UserRepository
    laws: LaborLawRepository
    templates: ComplaintTemplateRepository
    radar: RadarRepository
    fib: FibRepository


# --- fallbacks (D-55) -------------------------------------------------------------------


def choose_country(
    request: AnalyzeRequest, detected: str | None, profile: dict[str, Any]
) -> HostCountryCode:
    """The worker's choice, else what the contract shows, else the worker's profile."""
    for candidate in (request.host_country, detected, profile.get("host_country")):
        if candidate in HOST_COUNTRIES:
            return cast(HostCountryCode, candidate)
    raise PipelineStopError("detect", "country_unknown")


def choose_job(request: AnalyzeRequest, detected: str, profile: dict[str, Any]) -> JobTypeId:
    """The worker's choice, else the contract's duties, else the profile; "other" = unknown."""
    if request.job_type is not None:
        return request.job_type
    if detected != "other":
        return cast(JobTypeId, detected)
    return cast(JobTypeId, profile.get("job_type") or "other")


def choose_language(request: AnalyzeRequest, profile: dict[str, Any]) -> ReportLanguage:
    """The worker's choice, else their profile's preferred language, else English."""
    if request.report_language is not None:
        return request.report_language
    preferred = profile.get("preferred_language")
    return cast(ReportLanguage, preferred) if preferred in REPORT_LANGUAGES else SOURCE_LANGUAGE


# --- analyze ----------------------------------------------------------------------------


def error_code(exc: GeminiError) -> PipelineErrorCode:
    if isinstance(exc, GeminiRateLimitError):
        return "gemini_busy"
    if isinstance(exc, GeminiTimeoutError):
        return "gemini_timeout"
    if isinstance(exc, GeminiUnavailableError):
        return "gemini_unavailable"
    return "gemini_bad_answer"


async def analyze_contract(
    uid: str, contract_id: str, request: AnalyzeRequest, deps: PipelineDeps
) -> ContractAnalysis:
    """Run steps 2 to 6 on a stored contract, or reuse the stored analysis while current.

    The contract's `status` and `step` are updated as it goes, so the app can show progress by
    watching the document. A failure is stored as `error: {step, code}` before it is raised.

    Raises:
        ContractNotFoundError: No such contract for this user.
        AnalysisInProgressError: Another request is analysing it.
        PipelineStopError: A reason the worker can act on (unreadable photo, unknown country,
            not an employment contract, no law data, no terms).
        GeminiError: A Gemini failure; the endpoint maps it to 503/504/502.
    """
    contracts = deps.contracts
    contract = await run_in_threadpool(contracts.get, uid, contract_id)
    if contract is None:
        raise ContractNotFoundError(contract_id)
    profile = await run_in_threadpool(deps.users.get_profile, uid)
    language = choose_language(request, profile)

    reused = await reuse_analysis(
        contracts,
        deps.laws,
        deps.gemini,
        uid,
        contract_id,
        contract,
        request.host_country,
        request.job_type,
        language,
    )
    log_cache_lookup("contract", "analysis", hit=reused is not None)
    if reused is not None:
        if reused.complaint_pending or await letter_missing(
            contracts, uid, contract_id, reused.clause_counts.danger
        ):
            reason = await add_pending_letter(
                contracts, deps.templates, deps.gemini, uid, contract_id, contract, language
            )
            return reused.model_copy(
                update={"complaint_pending": reason is not None, "complaint_pending_reason": reason}
            )
        return reused
    if not await run_in_threadpool(contracts.claim_for_analysis, uid, contract_id, STALE_ANALYSIS):
        raise AnalysisInProgressError(contract_id)

    step: PipelineStep = "detect"

    async def enter(next_step: PipelineStep, **fields: Any) -> None:
        nonlocal step
        step = next_step
        await run_in_threadpool(contracts.update, uid, contract_id, {"step": step, **fields})

    try:
        extraction = await run_in_threadpool(contracts.get_extraction, uid, contract_id)
        if extraction is None:
            raise PipelineStopError("extract", "internal")
        if contract.get("legibility") == "poor":
            raise PipelineStopError("extract", "poor_legibility")
        blocks = [ContractBlock.model_validate(block) for block in extraction["blocks"]]
        text: str = extraction["text"]
        digest: str = contract["content_hash"]

        detected = await detect_contract(text, deps.gemini)
        host = choose_country(request, detected.host_country, profile)
        job = choose_job(request, detected.job_type, profile)
        facts = ContractFacts(
            employer_name=detected.employer_name,
            agency_name=detected.agency_name,
            salary_amount=detected.salary_amount,
            salary_currency=detected.salary_currency,
            salary_period=detected.salary_period,
        )
        await enter(
            "law",
            detected={
                "language": detected.language,
                "host_country": detected.host_country,
                "document_kind": detected.document_kind,
                "job_type": detected.job_type,
            },
            extracted=facts.model_dump(exclude_none=True),
            host_country=host,
            job_type=job,
        )
        try:
            law = await get_labor_law_context(host, job, deps.laws)
        except LaborLawNotFoundError as exc:
            raise PipelineStopError("law", "no_law_data") from exc

        await enter("compare")
        try:
            comparison = await compare_contract(blocks, law, deps.gemini, detected.document_kind)
        except NotComparableError as exc:
            raise PipelineStopError("compare", "not_employment_contract") from exc
        except NoTermsError as exc:
            raise PipelineStopError("compare", "no_terms") from exc

        # Financial Identity Builder (NF-P3-024): never lets a Firestore hiccup here cost the
        # worker their own report, the same resilience as the radar signal below.
        try:
            await log_contract_income(
                uid, contract_id, detected.document_kind, facts, deps.fib, datetime.now(UTC)
            )
        except Exception:
            logger.warning("pipeline_fib_income_failed", exc_info=True)

        complaint, letter_reason = None, None
        if comparison.clause_counts.danger:
            await enter("complaint")
            complaint, letter_reason = await write_letter(
                host, comparison.clauses, facts, language, deps.templates, deps.gemini
            )
            # A background signal to Exploitation Radar (NF-P2-021): never lets a Firestore
            # hiccup here cost the worker their own report, so it is never awaited for its
            # result and never re-raised.
            try:
                await create_radar_signals(
                    host, detected.document_kind, comparison.clauses, facts, deps.radar
                )
            except Exception:
                logger.warning("pipeline_radar_signal_failed", exc_info=True)

        clauses = [TranslatedClause.model_validate(c.model_dump()) for c in comparison.clauses]
        source = build_report(
            SOURCE_LANGUAGE, text, comparison.summary, clauses, complaint, digest, law.law_version
        )
        await save_report(contracts, uid, contract_id, source)
        # Stored before translating: if the translation fails, the next analyze reuses all
        # of this and only translates.
        analysis_fields: dict[str, Any] = {
            "health_score": comparison.health_score,
            "risk_level": comparison.risk_level,
            "clause_counts": comparison.clause_counts.model_dump(),
            "law_version": law.law_version,
            "prompt_versions": current_prompt_versions(),
            "models": model_ids(),
            # None removes the field: only a passing failure leaves the letter pending.
            "complaint_pending": True if letter_reason else None,
            "complaint_pending_reason": letter_reason,
        }
        if language != SOURCE_LANGUAGE:
            await enter("translate", **analysis_fields)
            await translate_and_store(contracts, deps.gemini, uid, contract_id, source, language)
        await run_in_threadpool(
            contracts.update,
            uid,
            contract_id,
            {"status": "completed", "step": None, "error": None, **analysis_fields},
        )
    except PipelineStopError as stop:
        await _record_failure(contracts, uid, contract_id, stop.step, stop.code)
        raise
    except GeminiError as exc:
        await _record_failure(contracts, uid, contract_id, step, error_code(exc))
        raise
    except Exception:
        await _record_failure(contracts, uid, contract_id, step, "internal")
        raise

    stored = contract | {"host_country": host, "job_type": job, **analysis_fields}
    return stored_analysis(contract_id, stored, language, cached=False)


async def _record_failure(
    contracts: ContractRepository,
    uid: str,
    contract_id: str,
    step: PipelineStep,
    code: PipelineErrorCode,
) -> None:
    logger.warning("pipeline_failed step=%s code=%s", step, code)
    await run_in_threadpool(
        contracts.update,
        uid,
        contract_id,
        {"status": "failed", "step": None, "error": {"step": step, "code": code}},
    )
