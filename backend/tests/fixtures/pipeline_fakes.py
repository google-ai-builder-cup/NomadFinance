"""In-memory stand-ins for the Contract Shield pipeline's repositories (NF-P2-007 tests)."""

from __future__ import annotations

import copy
from collections import Counter
from datetime import timedelta
from typing import Any

from app.schemas.contract import ContractBlock, DetectedContract, ExtractedContract
from app.schemas.contract_compare import ClauseCounts, ComparedClause, ContractComparison
from app.schemas.contract_complaint import ContractComplaint
from app.schemas.contract_translate import ContractReportTranslation, TranslatedClause
from app.services.contract.comparator import NotComparableError

LAW_RULE: dict[str, Any] = {
    "coverage": "regulated",
    "title": "Keeping the passport",
    "summary": "The employer must not keep the worker's passport.",
    "variants": [{"applies_to": ["all"], "requirements": ["Must not keep the passport."]}],
    "references": [{"law": "Passports Act", "section": "s. 47", "url": "https://x"}],
    "confidence": "high",
}


class FakeContracts:
    """ContractRepository in memory, with the same semantics the pipeline relies on."""

    def __init__(self) -> None:
        self.contracts: dict[tuple[str, str], dict[str, Any]] = {}
        self.extractions: dict[tuple[str, str], dict[str, Any]] = {}
        self.reports: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.updates: list[dict[str, Any]] = []
        self.busy = False  # another request holds a fresh `processing` claim
        self._next = 0

    def new_id(self, uid: str) -> str:
        self._next += 1
        return f"C{self._next:019d}"

    def get(self, uid: str, contract_id: str) -> dict[str, Any] | None:
        stored = self.contracts.get((uid, contract_id))
        return copy.deepcopy(stored) if stored is not None else None

    def find_by_hash(self, uid: str, content_hash: str) -> tuple[str, dict[str, Any]] | None:
        for (owner, contract_id), data in self.contracts.items():
            if owner == uid and data.get("content_hash") == content_hash:
                return contract_id, copy.deepcopy(data)
        return None

    def save_upload(
        self, uid: str, contract_id: str, contract: dict[str, Any], extraction: dict[str, Any]
    ) -> None:
        self.contracts[(uid, contract_id)] = copy.deepcopy(contract)
        self.extractions[(uid, contract_id)] = copy.deepcopy(extraction)

    def get_extraction(self, uid: str, contract_id: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.extractions.get((uid, contract_id)))

    def update(self, uid: str, contract_id: str, changes: dict[str, Any]) -> None:
        self.updates.append(copy.deepcopy(changes))
        doc = self.contracts[(uid, contract_id)]
        for key, value in changes.items():
            if value is None:
                doc.pop(key, None)
            else:
                doc[key] = copy.deepcopy(value)

    def claim_for_analysis(self, uid: str, contract_id: str, stale_after: timedelta) -> bool:
        if self.busy:
            return False
        self.update(uid, contract_id, {"status": "processing", "step": "detect", "error": None})
        return True

    def get_report(self, uid: str, contract_id: str, language: str) -> dict[str, Any] | None:
        return copy.deepcopy(self.reports.get((uid, contract_id, language)))

    def save_report(self, uid: str, contract_id: str, report: dict[str, Any]) -> None:
        self.reports[(uid, contract_id, report["language"])] = copy.deepcopy(report)
        languages = self.contracts[(uid, contract_id)].setdefault("report_languages", [])
        if report["language"] not in languages:
            languages.append(report["language"])

    @property
    def steps(self) -> list[str]:
        """The `step` values written, in order: the progress the app would have shown."""
        return [update["step"] for update in self.updates if update.get("step")]


class FakeUsers:
    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile or {}

    def get_profile(self, uid: str) -> dict[str, Any]:
        return dict(self.profile)


class FakeLaws:
    def __init__(self, version: int | None = 1) -> None:
        self.version = version

    def get_version(self, country: str) -> int | None:
        return self.version

    def get_rules(self, country: str) -> dict[str, dict[str, Any]]:
        return {"passport_retention": LAW_RULE} if self.version is not None else {}


class FakeTemplates:
    def get_template(self, country: str, template_type: str) -> dict[str, Any] | None:
        return None


class FakeRadar:
    """RadarRepository in memory: every write kept, in order (NF-P2-021)."""

    def __init__(self) -> None:
        self.reports: dict[str, Any] = {}
        self._next = 0

    def new_report_id(self) -> str:
        self._next += 1
        return f"R{self._next:019d}"

    def create_report(self, report_id: str, report: Any) -> None:
        self.reports[report_id] = report


class FakeFib:
    """FibRepository in memory: what NF-P3-024's contract income needs."""

    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    def save_entry(self, uid: str, kind: str, entry_id: str, data: dict[str, Any]) -> None:
        self.docs[f"{uid}/{kind}/{entry_id}"] = copy.deepcopy(data)

    def list_entries(self, uid: str, kind: str) -> list[tuple[str, dict[str, Any]]]:
        prefix = f"{uid}/{kind}/"
        return [
            (k[len(prefix) :], copy.deepcopy(v))
            for k, v in self.docs.items()
            if k.startswith(prefix)
        ]

    def delete_entry(self, uid: str, kind: str, entry_id: str) -> None:
        self.docs.pop(f"{uid}/{kind}/{entry_id}", None)


# --- the Gemini steps -------------------------------------------------------------------


BLOCKS = [
    ContractBlock(page=1, kind="heading", number=None, text="CONTRACT"),
    ContractBlock(page=1, kind="clause", number="1", text="The employer keeps the passport."),
]
CLAUSE = ComparedClause(
    index=1,
    number="1",
    page=1,
    text="1 The employer keeps the passport.",
    category="passport_retention",
    risk="danger",
    law_reference="Passports Act, s. 47",
    explanation="The employer keeps your passport.",
    recommendation="Keep your own passport.",
    block_ids=[2],
)


def _detected(**changes: Any) -> DetectedContract:
    values: dict[str, Any] = {
        "language": "en",
        "host_country": "SG",
        "host_country_evidence": "Singapore",
        "document_kind": "employment_contract",
        "job_type": "domestic_worker",
        "employer_name": "Tan",
        "agency_name": None,
        "salary_amount": 650,
        "salary_currency": "SGD",
        "salary_period": "month",
    }
    return DetectedContract.model_validate(values | changes)


def _comparison(risk: str = "danger") -> ContractComparison:
    clause = CLAUSE.model_copy(update={"risk": risk})
    counts = ClauseCounts.model_validate({risk: 1})
    score = {"danger": 49, "caution": 79, "safe": 100}[risk]
    return ContractComparison(
        country="SG",
        job_type="domestic_worker",
        law_version=1,
        health_score=score,
        risk_level=risk,
        clause_counts=counts,
        summary="The employer keeps the passport.",
        clauses=[clause],
        unassessed_block_ids=[],
    )


COMPLAINT = ContractComplaint(
    template_type="general",
    authority_name="Ministry of Manpower",
    authority_url=None,
    channels=[],
    letter_language="en",
    letter_text="Dear Sir, ...",
    worker_language="hi",
    worker_copy="प्रिय महोदय, ...",
    violation_count=1,
)


class Steps:
    """Stand-ins for the Gemini steps, counting calls; each can be told to fail."""

    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.detected = _detected()
        self.comparison = _comparison()
        self.fail: dict[str, Exception] = {}

    def _check(self, name: str) -> None:
        self.calls[name] += 1
        if name in self.fail:
            raise self.fail[name]

    async def extract(self, data: bytes, mime: str, gemini: Any) -> tuple[ExtractedContract, str]:
        self._check("extract")
        contract = ExtractedContract(
            is_document=True, page_count=1, title="CONTRACT", legibility="good", blocks=BLOCKS
        )
        return contract, "CONTRACT\n\n1 The employer keeps the passport."

    async def detect(self, text: str, gemini: Any) -> DetectedContract:
        self._check("detect")
        return self.detected

    async def compare(self, blocks: Any, law: Any, gemini: Any, kind: str) -> ContractComparison:
        self._check("compare")
        if kind == "loan_agreement":
            raise NotComparableError(kind)
        return self.comparison

    async def complaint(self, *args: Any) -> ContractComplaint:
        self._check("complaint")
        return COMPLAINT

    async def translate(
        self, full_text: str, summary: str, clauses: list[ComparedClause], language: str, g: Any
    ) -> ContractReportTranslation:
        self._check("translate")
        return ContractReportTranslation(
            language=language,
            full_text=f"[{language}] {full_text}",
            summary=f"[{language}] {summary}",
            clauses=[TranslatedClause.model_validate(c.model_dump()) for c in clauses],
        )
