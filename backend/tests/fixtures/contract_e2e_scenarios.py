"""NF-P2-008: scripted Gemini answers for a full, real pipeline run per host country.

Unlike pipeline_fakes.py (which stands in for the pipeline's own step functions, for testing
pipeline.py's plumbing in isolation), ScriptedGemini stands in only at the Gemini API boundary.
The real extractor/detector/comparator/translator/complaint code, the real Firestore-backed
repositories and the real curated labor-law and complaint-template data all run for real
against the Firestore Emulator — only the model's answers are canned, so the whole pipeline is
exercised per country without spending the shared Gemini quota (D-58).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.contract import ContractBlock, DetectedContract, ExtractedContract
from app.schemas.contract_compare import (
    ClauseCategory,
    ClauseRisk,
    ComparisonAnswer,
    TermAssessment,
)
from app.schemas.contract_complaint import ComplaintAnswer
from app.schemas.contract_translate import TranslatedClauseAnswer, TranslationAnswer

FIXTURES = Path(__file__).resolve().parent / "contracts"


def _blocks(filename: str) -> list[ContractBlock]:
    raw = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    return [ContractBlock.model_validate(block) for block in raw]


def _term(ids: list[int], category: ClauseCategory, risk: ClauseRisk, note: str) -> TermAssessment:
    return TermAssessment(
        block_ids=ids,
        category=category,
        risk=risk,
        explanation=note,
        recommendation=None if risk == "safe" else f"Ask about: {note.lower()}",
    )


class Scenario:
    """Everything needed to run one real contract file through the real pipeline."""

    def __init__(
        self,
        country: str,
        file: str,
        blocks_file: str,
        job_type: str,
        preferred_language: str,
        detected: DetectedContract,
        comparison: ComparisonAnswer,
    ) -> None:
        self.country = country
        self.file = file
        self.blocks_file = blocks_file
        self.job_type = job_type
        self.preferred_language = preferred_language
        self.detected = detected
        self.comparison = comparison

    @property
    def content_type(self) -> str:
        return "application/pdf" if self.file.endswith(".pdf") else "image/jpeg"

    @property
    def data(self) -> bytes:
        return (FIXTURES / self.file).read_bytes()


def _extracted(blocks_file: str, title: str) -> ExtractedContract:
    blocks = _blocks(blocks_file)
    return ExtractedContract(
        is_document=True,
        page_count=max(block.page for block in blocks),
        title=title,
        legibility="good",
        blocks=blocks,
    )


SCENARIOS: dict[str, Scenario] = {
    "SG": Scenario(
        country="SG",
        file="sample_contract_sg.pdf",
        blocks_file="sample_contract_sg.blocks.json",
        job_type="domestic_worker",
        preferred_language="hi",
        detected=DetectedContract(
            language="en",
            host_country="SG",
            host_country_evidence="Republic of Singapore",
            document_kind="employment_contract",
            job_type="domestic_worker",
            employer_name="Tan Wei Ming",
            agency_name=None,
            salary_amount=650,
            salary_currency="SGD",
            salary_period="month",
        ),
        comparison=ComparisonAnswer(
            terms=[
                _term([3], "other", "safe", "24-month duration is a normal term."),
                _term([4], "minimum_wage", "safe", "SGD 650 a month is a stated wage."),
                _term([5], "recruitment_fees", "danger", "A placement loan is deducted."),
                _term([6], "rest_days_and_holidays", "danger", "Only one rest day a month."),
                _term([7], "working_hours", "caution", "Hours are not stated as a number."),
                _term([8], "passport_retention", "danger", "The employer keeps the passport."),
                _term([9], "early_termination", "caution", "Two months' pay on early exit."),
                _term([10], "insurance_and_injury", "safe", "Medical insurance is provided."),
            ],
            summary="The employer keeps the passport and gives only one rest day a month.",
        ),
    ),
    "AU": Scenario(
        country="AU",
        file="sample_contract_au.pdf",
        blocks_file="sample_contract_au.blocks.json",
        job_type="construction_worker",
        preferred_language="tl",
        detected=DetectedContract(
            language="en",
            host_country="AU",
            host_country_evidence="Fair Work Act 2009 (Cth)",
            document_kind="employment_contract",
            job_type="construction_worker",
            employer_name="Southern Cross Builders Pty Ltd",
            agency_name=None,
            salary_amount=26.50,
            salary_currency="AUD",
            salary_period="hour",
        ),
        comparison=ComparisonAnswer(
            terms=[
                _term([3], "other", "safe", "12-month renewable duration is a normal term."),
                _term([4], "minimum_wage", "safe", "AUD 26.50/hour is above the minimum wage."),
                _term([5], "working_hours", "danger", "55 hours a week exceeds the 38-hour cap."),
                _term([6], "passport_retention", "danger", "The employer holds the passport."),
                _term([7], "recruitment_fees", "danger", "AUD 3,000 charged before starting."),
                _term([8], "termination_notice", "safe", "2 weeks' notice or pay in lieu."),
                _term([9], "rest_days_and_holidays", "safe", "Public holidays at penalty rate."),
            ],
            summary="The contract requires excessive hours, holds the passport, and charges fees.",
        ),
    ),
    "KR": Scenario(
        country="KR",
        file="sample_contract_kr.pdf",
        blocks_file="sample_contract_kr.blocks.json",
        job_type="manufacturing_worker",
        preferred_language="bn",
        detected=DetectedContract(
            language="en",
            host_country="KR",
            host_country_evidence="Employment Permit System (E-9 visa)",
            document_kind="employment_contract",
            job_type="manufacturing_worker",
            employer_name="Hanbit Precision Co., Ltd.",
            agency_name=None,
            salary_amount=2060740,
            salary_currency="KRW",
            salary_period="month",
        ),
        comparison=ComparisonAnswer(
            terms=[
                _term([3], "other", "safe", "12-month E-9 duration is a normal term."),
                _term([4], "minimum_wage", "safe", "KRW 2,060,740/month meets the minimum wage."),
                _term([5], "working_hours", "safe", "40 hours/week, 8 hours/day is compliant."),
                _term([6], "passport_retention", "danger", "The employer keeps the passport."),
                _term([7], "recruitment_fees", "danger", "Extra agency fee beyond the set fee."),
                _term([8], "termination_notice", "danger", "Dismissal without cause or notice."),
                _term([9], "rest_days_and_holidays", "safe", "One paid weekly holiday."),
            ],
            summary="The contract allows passport retention, extra fees and dismissal at will.",
        ),
    ),
    "MY": Scenario(
        country="MY",
        file="sample_contract_my_id_photo.jpg",
        blocks_file="sample_contract_my_id.blocks.json",
        job_type="plantation_worker",
        preferred_language="id",
        detected=DetectedContract(
            language="ms",
            host_country="MY",
            host_country_evidence="RM, Johor, Malaysia",
            document_kind="employment_contract",
            job_type="plantation_worker",
            employer_name="Ladang Sawit Sri Jaya Sdn Bhd",
            agency_name=None,
            salary_amount=1500,
            salary_currency="MYR",
            salary_period="month",
        ),
        comparison=ComparisonAnswer(
            terms=[
                _term([4], "other", "safe", "Plantation worker role is a normal term."),
                _term([5], "minimum_wage", "safe", "RM 1,500 a month is a stated wage."),
                _term([6], "recruitment_fees", "danger", "RM 300/month for 12 months in fees."),
                _term([7], "working_hours", "danger", "10 hours a day, 6 days a week is too long."),
                _term([8], "passport_retention", "danger", "The employer keeps the passport."),
                _term([9], "other", "safe", "3-year duration is a normal term."),
            ],
            summary="The contract charges recruitment fees, exceeds hours and keeps the passport.",
        ),
    ),
    "JP": Scenario(
        country="JP",
        file="sample_contract_jp.pdf",
        blocks_file="sample_contract_jp.blocks.json",
        job_type="care_worker",
        preferred_language="ne",
        detected=DetectedContract(
            language="en",
            host_country="JP",
            host_country_evidence="Technical Intern Training program",
            document_kind="employment_contract",
            job_type="care_worker",
            employer_name="Sakura Care Support Organisation",
            agency_name=None,
            salary_amount=1064,
            salary_currency="JPY",
            salary_period="hour",
        ),
        comparison=ComparisonAnswer(
            terms=[
                _term([3], "other", "safe", "3-year training duration is a normal term."),
                _term([4], "minimum_wage", "safe", "JPY 1,064/hour meets the regional minimum."),
                _term([5], "working_hours", "safe", "40 hours/week, 8 hours/day is compliant."),
                _term([6], "passport_retention", "danger", "The organisation retains the passport"),
                _term([7], "recruitment_fees", "danger", "A monthly supervision fee is deducted."),
                _term([8], "termination_notice", "safe", "30 days' notice or pay instead."),
                _term([9], "rest_days_and_holidays", "safe", "At least one day off a week."),
            ],
            summary="The passport is retained and a supervision fee is deducted from wages.",
        ),
    ),
}


def _generic_complaint(country: str) -> ComplaintAnswer:
    """A placeholder-free letter and worker copy; content isn't under test here."""
    return ComplaintAnswer(
        letter_text=(
            f"To the labor authority: I am writing to report violations of my employment "
            f"rights under a contract in {country}. [Details of each violation follow.]"
        ),
        worker_copy=(
            f"[Translated] I am reporting violations of my employment rights under my "
            f"contract in {country}."
        ),
    )


class ScriptedGemini:
    """A GeminiClient stand-in that answers each step from a `Scenario`, by response model."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        model = kwargs["response_model"]
        if model is ExtractedContract:
            return _extracted(self.scenario.blocks_file, self.scenario.country)
        if model is DetectedContract:
            return self.scenario.detected
        if model is ComparisonAnswer:
            return self.scenario.comparison
        if model is ComplaintAnswer:
            return _generic_complaint(self.scenario.country)
        if model is TranslationAnswer:
            return _echo_translation(kwargs["contents"])
        raise AssertionError(f"ScriptedGemini has no answer for {model!r}")


def _echo_translation(contents: str) -> TranslationAnswer:
    """A generic, deterministic stand-in translation: read back the real report_json that
    translator.py built, unchanged except for a `[T] ` tag, so the real merge logic in
    translator.py still runs against real data."""
    start = contents.index("<report>\n") + len("<report>\n")
    end = contents.index("\n</report>")
    data = json.loads(contents[start:end])
    return TranslationAnswer(
        full_text=f"[T] {data['full_text']}",
        summary=f"[T] {data['summary']}",
        clauses=[
            TranslatedClauseAnswer(
                index=clause["index"],
                category=clause["category"],
                risk=clause["risk"],
                text=f"[T] {clause['text']}",
                explanation=f"[T] {clause['explanation']}",
                recommendation=(
                    f"[T] {clause['recommendation']}" if clause["recommendation"] else None
                ),
            )
            for clause in data["clauses"]
        ],
    )
