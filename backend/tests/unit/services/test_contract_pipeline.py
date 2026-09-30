from __future__ import annotations

from typing import cast

import pytest

from app.integrations.gemini import GeminiClient, GeminiUnavailableError
from app.schemas.contract_pipeline import AnalyzeRequest
from app.services.contract import letter, pipeline, report_store, upload
from app.services.contract.complaint import ComplaintTemplateNotFoundError
from app.services.contract.pipeline import (
    AnalysisInProgressError,
    PipelineDeps,
    PipelineStopError,
    analyze_contract,
)
from app.services.contract.report_store import (
    ContractNotFoundError,
    ReportNotReadyError,
    current_prompt_versions,
    ensure_report,
)
from app.services.contract.translator import TranslationIncompleteError
from app.services.contract.upload import upload_contract
from tests.fixtures.pipeline_fakes import (
    FakeContracts,
    FakeLaws,
    FakeRadar,
    FakeTemplates,
    FakeUsers,
    Steps,
    _comparison,
    _detected,
)

pytestmark = pytest.mark.anyio

UID = "worker-1"
FILE = b"%PDF-1.4 contract bytes"
GEMINI = cast(GeminiClient, object())


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch) -> Steps:
    fake = Steps()
    monkeypatch.setattr(upload, "extract_contract", fake.extract)
    monkeypatch.setattr(pipeline, "detect_contract", fake.detect)
    monkeypatch.setattr(pipeline, "compare_contract", fake.compare)
    monkeypatch.setattr(letter, "generate_complaint", fake.complaint)
    monkeypatch.setattr(report_store, "translate_report", fake.translate)
    return fake


@pytest.fixture
def contracts() -> FakeContracts:
    return FakeContracts()


@pytest.fixture
def laws() -> FakeLaws:
    return FakeLaws()


@pytest.fixture
def users() -> FakeUsers:
    return FakeUsers({"host_country": "MY", "job_type": "care_worker", "preferred_language": "en"})


@pytest.fixture
def radar() -> FakeRadar:
    return FakeRadar()


@pytest.fixture
def deps(
    contracts: FakeContracts, users: FakeUsers, laws: FakeLaws, radar: FakeRadar
) -> PipelineDeps:
    return PipelineDeps(GEMINI, contracts, users, laws, FakeTemplates(), radar)  # type: ignore[arg-type]


async def _upload(contracts: FakeContracts, data: bytes = FILE) -> str:
    result = await upload_contract(UID, data, "application/pdf", "c.pdf", GEMINI, contracts)  # type: ignore[arg-type]
    return result.contract_id


# --- upload -----------------------------------------------------------------------------


async def test_upload_stores_the_extraction_but_not_the_file(
    steps: Steps, contracts: FakeContracts
) -> None:
    result = await upload_contract(UID, FILE, "application/pdf", "c.pdf", GEMINI, contracts)  # type: ignore[arg-type]

    assert (result.status, result.reused, result.legibility) == ("uploaded", False, "good")
    stored = contracts.contracts[(UID, result.contract_id)]
    assert stored["content_hash"] == upload.content_hash(FILE)
    assert stored["prompt_versions"] == {"contract.extract": 2}
    assert FILE not in str(stored).encode()
    extraction = contracts.extractions[(UID, result.contract_id)]
    assert [b["text"] for b in extraction["blocks"]][1] == "The employer keeps the passport."


async def test_the_same_file_is_read_once(steps: Steps, contracts: FakeContracts) -> None:
    first = await _upload(contracts)
    again = await upload_contract(UID, FILE, "application/pdf", "c.pdf", GEMINI, contracts)  # type: ignore[arg-type]

    assert again.contract_id == first
    assert again.reused is True
    assert steps.calls["extract"] == 1


async def test_a_file_read_with_an_older_prompt_is_read_again_into_the_same_contract(
    steps: Steps, contracts: FakeContracts
) -> None:
    first = await _upload(contracts)
    contracts.contracts[(UID, first)]["prompt_versions"] = {"contract.extract": 1}

    again = await upload_contract(UID, FILE, "application/pdf", "c.pdf", GEMINI, contracts)  # type: ignore[arg-type]

    assert (again.contract_id, again.reused) == (first, True)
    assert steps.calls["extract"] == 2


# --- analyze ----------------------------------------------------------------------------


async def test_analyze_runs_every_step_and_stores_the_english_report(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert (result.status, result.cached, result.risk_level) == ("completed", False, "danger")
    assert (result.host_country, result.job_type) == ("SG", "domestic_worker")
    assert contracts.steps == ["detect", "law", "compare", "complaint"]
    stored = contracts.contracts[(UID, contract_id)]
    assert stored["status"] == "completed" and "step" not in stored and "error" not in stored
    assert stored["prompt_versions"] == current_prompt_versions()
    assert stored["detected"]["document_kind"] == "employment_contract"
    assert stored["extracted"] == {
        "employer_name": "Tan",
        "salary_amount": 650.0,
        "salary_currency": "SGD",
        "salary_period": "month",
    }
    report = contracts.reports[(UID, contract_id, "en")]
    assert report["is_source"] is True
    assert report["complaint"]["authority_name"] == "Ministry of Manpower"
    assert report["full_text"].startswith("CONTRACT")
    assert steps.calls["translate"] == 0


async def test_the_worker_language_report_is_a_translation(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="hi"), deps)

    assert result.report_languages == ["en", "hi"]
    hindi = contracts.reports[(UID, contract_id, "hi")]
    assert hindi["is_source"] is False
    assert hindi["summary"].startswith("[hi]")
    assert hindi["complaint"] == contracts.reports[(UID, contract_id, "en")]["complaint"]
    assert contracts.steps[-1] == "translate"


async def test_the_profile_language_is_used_when_the_worker_did_not_choose(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, users: FakeUsers
) -> None:
    users.profile["preferred_language"] = "ne"
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert result.report_language == "ne"
    assert (UID, contract_id, "ne") in contracts.reports


async def test_a_current_analysis_is_served_without_gemini(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)
    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)
    before = steps.calls.copy()

    again = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert again.cached is True
    assert steps.calls == before


async def test_only_a_missing_language_is_translated(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)
    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    again = await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="tl"), deps)

    assert again.cached is True
    assert (steps.calls["detect"], steps.calls["compare"], steps.calls["translate"]) == (1, 1, 1)
    assert again.report_languages == ["en", "tl"]


@pytest.mark.parametrize(
    "change",
    ["new_law_version", "new_prompt_version", "other_country", "other_job"],
)
async def test_a_stale_or_different_analysis_runs_again(
    steps: Steps,
    contracts: FakeContracts,
    deps: PipelineDeps,
    laws: FakeLaws,
    change: str,
) -> None:
    contract_id = await _upload(contracts)
    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)
    request = AnalyzeRequest()
    if change == "new_law_version":
        laws.version = 2
    elif change == "new_prompt_version":
        contracts.contracts[(UID, contract_id)]["prompt_versions"]["contract.compare"] = 0
    elif change == "other_country":
        request = AnalyzeRequest(host_country="MY")
    else:
        request = AnalyzeRequest(job_type="care_worker")

    again = await analyze_contract(UID, contract_id, request, deps)

    assert again.cached is False
    assert steps.calls["compare"] == 2


async def test_country_falls_back_to_the_profile(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.detected = _detected(host_country=None, job_type="other")
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert (result.host_country, result.job_type) == ("MY", "care_worker")


async def test_the_workers_choice_wins_over_the_contract(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)

    result = await analyze_contract(
        UID, contract_id, AnalyzeRequest(host_country="JP", job_type="care_worker"), deps
    )

    assert (result.host_country, result.job_type) == ("JP", "care_worker")


async def _stopped(
    contracts: FakeContracts, deps: PipelineDeps, contract_id: str
) -> PipelineStopError:
    with pytest.raises(PipelineStopError) as info:
        await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)
    error = contracts.contracts[(UID, contract_id)]["error"]
    assert (error["step"], error["code"]) == (info.value.step, info.value.code)
    assert contracts.contracts[(UID, contract_id)]["status"] == "failed"
    return info.value


async def test_no_country_anywhere_stops_and_asks(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, users: FakeUsers
) -> None:
    steps.detected = _detected(host_country=None)
    users.profile.pop("host_country")
    contract_id = await _upload(contracts)

    stop = await _stopped(contracts, deps, contract_id)

    assert (stop.step, stop.code) == ("detect", "country_unknown")


async def test_an_unreadable_photo_is_refused_before_any_gemini_call(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)
    contracts.contracts[(UID, contract_id)]["legibility"] = "poor"

    stop = await _stopped(contracts, deps, contract_id)

    assert (stop.step, stop.code) == ("extract", "poor_legibility")
    assert steps.calls["detect"] == 0


async def test_a_loan_agreement_is_not_checked(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.detected = _detected(document_kind="loan_agreement")
    contract_id = await _upload(contracts)

    stop = await _stopped(contracts, deps, contract_id)

    assert (stop.step, stop.code) == ("compare", "not_employment_contract")


async def test_a_country_without_law_data_stops(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, laws: FakeLaws
) -> None:
    laws.version = None
    contract_id = await _upload(contracts)

    stop = await _stopped(contracts, deps, contract_id)

    assert (stop.step, stop.code) == ("law", "no_law_data")


async def test_a_gemini_failure_is_stored_with_its_step(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.fail["compare"] = GeminiUnavailableError("gemini-x: 503")
    contract_id = await _upload(contracts)

    with pytest.raises(GeminiUnavailableError):
        await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    stored = contracts.contracts[(UID, contract_id)]
    assert stored["status"] == "failed"
    assert stored["error"] == {"step": "compare", "code": "gemini_unavailable"}


async def test_after_a_failed_translation_the_next_run_only_translates(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.fail["translate"] = TranslationIncompleteError("clause 1 missing")
    contract_id = await _upload(contracts)
    with pytest.raises(TranslationIncompleteError):
        await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="id"), deps)
    assert contracts.contracts[(UID, contract_id)]["error"]["step"] == "translate"
    del steps.fail["translate"]

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="id"), deps)

    assert result.cached is True
    assert contracts.contracts[(UID, contract_id)]["status"] == "completed"
    assert (steps.calls["compare"], steps.calls["translate"]) == (1, 2)


async def test_a_missing_complaint_template_keeps_the_report(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.fail["complaint"] = ComplaintTemplateNotFoundError("SG")
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert (result.status, result.complaint_pending) == ("completed", False)
    assert contracts.reports[(UID, contract_id, "en")]["complaint"] is None


async def test_a_passing_letter_failure_is_retried_alone_on_the_next_analyze(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.fail["complaint"] = GeminiUnavailableError("gemini-x: 503")
    contract_id = await _upload(contracts)

    first = await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="hi"), deps)

    assert (first.status, first.complaint_pending) == ("completed", True)
    assert contracts.reports[(UID, contract_id, "hi")]["complaint"] is None
    del steps.fail["complaint"]

    second = await analyze_contract(UID, contract_id, AnalyzeRequest(report_language="hi"), deps)

    assert (second.cached, second.complaint_pending) == (True, False)
    assert steps.calls["compare"] == 1  # only the letter was written again
    for language in ("en", "hi"):
        letter_ = contracts.reports[(UID, contract_id, language)]["complaint"]
        assert letter_["authority_name"] == "Ministry of Manpower"
    assert "complaint_pending" not in contracts.contracts[(UID, contract_id)]


async def test_a_letter_that_fails_again_stays_pending(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.fail["complaint"] = GeminiUnavailableError("gemini-x: 503")
    contract_id = await _upload(contracts)
    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    again = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert again.complaint_pending is True
    assert steps.calls["complaint"] == 2


async def test_no_complaint_is_written_without_danger(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    steps.comparison = _comparison("caution")
    contract_id = await _upload(contracts)

    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert steps.calls["complaint"] == 0
    assert "complaint" not in contracts.steps


async def test_a_danger_clause_creates_a_radar_signal(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, radar: FakeRadar
) -> None:
    contract_id = await _upload(contracts)

    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert len(radar.reports) == 1
    report = next(iter(radar.reports.values()))
    assert (report.entity_name, report.violation_type) == ("Tan", "passport_retention")
    assert report.source == "contract_signal"


async def test_no_radar_signal_without_danger(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, radar: FakeRadar
) -> None:
    steps.comparison = _comparison("caution")
    contract_id = await _upload(contracts)

    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert radar.reports == {}


async def test_a_radar_write_failure_never_breaks_the_worker_s_report(
    steps: Steps,
    contracts: FakeContracts,
    deps: PipelineDeps,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def boom(*args: object, **kwargs: object) -> list[str]:
        raise RuntimeError("radar_reports is unreachable")

    monkeypatch.setattr(pipeline, "create_radar_signals", boom)
    contract_id = await _upload(contracts)

    result = await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    assert result.status == "completed"
    assert contracts.reports[(UID, contract_id, "en")]["complaint"] is not None


async def test_a_second_analysis_at_the_same_time_is_refused(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps
) -> None:
    contract_id = await _upload(contracts)
    contracts.busy = True

    with pytest.raises(AnalysisInProgressError):
        await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)
    assert steps.calls["detect"] == 0


async def test_unknown_contract(steps: Steps, deps: PipelineDeps) -> None:
    with pytest.raises(ContractNotFoundError):
        await analyze_contract(UID, "C0000000000000000404", AnalyzeRequest(), deps)


# --- report in another language ---------------------------------------------------------


async def test_ensure_report_translates_once_then_serves_the_stored_one(
    steps: Steps, contracts: FakeContracts, deps: PipelineDeps, laws: FakeLaws
) -> None:
    contract_id = await _upload(contracts)
    await analyze_contract(UID, contract_id, AnalyzeRequest(), deps)

    first = await ensure_report(contracts, laws, GEMINI, UID, contract_id, "bn")  # type: ignore[arg-type]
    second = await ensure_report(contracts, laws, GEMINI, UID, contract_id, "bn")  # type: ignore[arg-type]

    assert first == second
    assert first.language == "bn" and first.summary.startswith("[bn]")
    assert steps.calls["translate"] == 1


async def test_ensure_report_needs_a_current_analysis(
    steps: Steps, contracts: FakeContracts, laws: FakeLaws
) -> None:
    contract_id = await _upload(contracts)

    with pytest.raises(ReportNotReadyError):
        await ensure_report(contracts, laws, GEMINI, UID, contract_id, "hi")  # type: ignore[arg-type]
    with pytest.raises(ContractNotFoundError):
        await ensure_report(contracts, laws, GEMINI, UID, "C0000000000000000404", "hi")  # type: ignore[arg-type]
