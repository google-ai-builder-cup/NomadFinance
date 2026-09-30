from __future__ import annotations

from datetime import UTC, datetime
from itertools import count
from typing import Any, cast

import pytest

from app.repositories.radar_repo import RadarRepository
from app.schemas.contract import DocumentKind
from app.schemas.contract_compare import ComparedClause
from app.schemas.contract_complaint import ContractFacts
from app.services.cross_pillar.contract_to_radar import (
    VIOLATION_TYPE,
    build_reports,
    choose_entity,
    create_radar_signals,
)

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _clause(
    index: int = 1, category: str = "passport_retention", risk: str = "danger", **over: Any
) -> ComparedClause:
    values: dict[str, Any] = {
        "index": index,
        "number": str(index),
        "page": 1,
        "text": "The employer may keep the worker's passport for safekeeping.",
        "category": category,
        "risk": risk,
        "law_reference": "Passports Act, s. 47",
        "explanation": "The employer keeps your passport; the rule forbids it.",
        "recommendation": "Ask to keep your own passport." if risk != "safe" else None,
        "block_ids": [index],
    }
    return ComparedClause.model_validate(values | over)


def _facts(**over: Any) -> ContractFacts:
    values: dict[str, Any] = {"employer_name": "Acme Pte Ltd", "agency_name": None}
    return ContractFacts.model_validate(values | over)


def _new_id() -> Any:
    counter = count(1)
    return lambda: f"r{next(counter)}"


# --- choose_entity ------------------------------------------------------------------------


def test_a_recruitment_agreement_with_an_agency_name_reports_the_agency() -> None:
    entity = choose_entity("recruitment_agreement", _facts(agency_name="Best Jobs Agency"))

    assert entity == ("recruitment_agency", "Best Jobs Agency")


def test_a_recruitment_agreement_with_no_agency_name_falls_back_to_the_employer() -> None:
    entity = choose_entity(
        "recruitment_agreement", _facts(employer_name="Acme Pte Ltd", agency_name=None)
    )

    assert entity == ("employer", "Acme Pte Ltd")


def test_an_employment_contract_reports_the_employer() -> None:
    entity = choose_entity("employment_contract", _facts(agency_name="Best Jobs Agency"))

    assert entity == ("employer", "Acme Pte Ltd")


@pytest.mark.parametrize(
    "document_kind", ["employment_contract", "recruitment_agreement", "loan_agreement", "other"]
)
def test_no_name_at_all_is_nothing_to_report(document_kind: DocumentKind) -> None:
    assert choose_entity(document_kind, _facts(employer_name=None, agency_name=None)) is None


# --- build_reports: gating and grouping ----------------------------------------------------


def _unexpected_id() -> str:
    raise AssertionError("new_id must not be called when nothing is reportable")


def test_no_danger_clauses_builds_nothing_and_never_calls_new_id() -> None:
    reports = build_reports(
        "SG", "employment_contract", [_clause(risk="caution")], _facts(), _unexpected_id, NOW
    )

    assert reports == []


def test_no_named_entity_builds_nothing_even_with_danger_clauses() -> None:
    reports = build_reports(
        "SG", "employment_contract", [_clause()], _facts(employer_name=None), _unexpected_id, NOW
    )

    assert reports == []


def test_only_danger_clauses_count_toward_a_report() -> None:
    clauses = [_clause(1, risk="safe"), _clause(2, risk="caution"), _clause(3, risk="danger")]

    reports = build_reports("SG", "employment_contract", clauses, _facts(), _new_id(), NOW)

    assert len(reports) == 1


def test_distinct_violation_types_become_separate_reports() -> None:
    clauses = [
        _clause(1, category="passport_retention"),
        _clause(2, category="recruitment_fees"),
    ]

    reports = build_reports("SG", "employment_contract", clauses, _facts(), _new_id(), NOW)

    assert {r.violation_type for r in reports} == {"passport_retention", "illegal_recruitment_fee"}
    assert len(reports) == 2


def test_several_clauses_of_the_same_mapped_type_collapse_into_one_report() -> None:
    # working_hours, rest_days_and_holidays, sick_leave all map to "other".
    clauses = [
        _clause(1, category="working_hours"),
        _clause(2, category="rest_days_and_holidays"),
        _clause(3, category="sick_leave"),
    ]

    reports = build_reports("SG", "employment_contract", clauses, _facts(), _new_id(), NOW)

    assert len(reports) == 1
    assert reports[0].violation_type == "other"
    for clause in clauses:
        assert clause.explanation in reports[0].description


def test_every_category_maps_to_a_valid_violation_type() -> None:
    valid = {
        "hidden_fees", "exchange_rate_markup", "illegal_recruitment_fee", "wage_theft",
        "illegal_deduction", "contract_substitution", "passport_retention",
        "unlicensed_operator", "other",
    }  # fmt: skip

    assert set(VIOLATION_TYPE.values()) <= valid
    assert len(VIOLATION_TYPE) == 16  # the 15 curated categories + "other"


# --- build_reports: field content -----------------------------------------------------------


def test_a_report_has_the_documented_shape() -> None:
    report = build_reports("SG", "employment_contract", [_clause()], _facts(), _new_id(), NOW)[0]

    assert report.entity_type == "employer"
    assert report.entity_name == "Acme Pte Ltd"
    assert report.entity_slug == "acme-pte-ltd"
    assert report.violation_type == "passport_retention"
    assert report.host_country == "SG"
    assert report.corridor_id is None
    assert report.language == "en"
    assert report.cluster_id  # non-empty
    assert report.source == "contract_signal"
    assert report.reporter_hash is None
    assert report.created_at == NOW
    assert report.schema_version == 1


def test_the_cluster_id_is_the_reports_own_new_id() -> None:
    ids = iter(["abc123"])
    report = build_reports(
        "SG", "employment_contract", [_clause()], _facts(), lambda: next(ids), NOW
    )[0]

    assert report.cluster_id == "abc123"


def test_the_description_never_contains_the_clauses_raw_text_only_the_explanation() -> None:
    clause = _clause(text="Clause text that must never appear.", explanation="Plain summary.")

    report = build_reports("SG", "employment_contract", [clause], _facts(), _new_id(), NOW)[0]

    assert "Clause text that must never appear." not in report.description
    assert "Plain summary." in report.description


def test_no_worker_identity_or_reporter_hash_anywhere_in_a_report() -> None:
    report = build_reports("SG", "employment_contract", [_clause()], _facts(), _new_id(), NOW)[0]

    dumped = report.model_dump()
    assert "reporter_hash" not in dumped or dumped["reporter_hash"] is None
    assert "worker" not in str(dumped).lower()


def test_the_validation_block_is_a_documented_placeholder_not_a_model_guess() -> None:
    report = build_reports("SG", "employment_contract", [_clause()], _facts(), _new_id(), NOW)[0]

    assert report.validation.spam_score == 0.0
    assert report.validation.category_confidence == 1.0
    assert report.validation.model == "contract_shield"


def test_a_long_description_is_capped_with_an_ellipsis() -> None:
    long_clauses = [_clause(n, explanation="x" * 200) for n in range(1, 10)]

    report = build_reports("SG", "employment_contract", long_clauses, _facts(), _new_id(), NOW)[0]

    assert len(report.description) <= 1000
    assert report.description.endswith("…")


def test_a_name_with_punctuation_still_produces_a_clean_slug() -> None:
    report = build_reports(
        "SG",
        "employment_contract",
        [_clause()],
        _facts(employer_name="O'Brien & Sons, Ltd."),
        _new_id(),
        NOW,
    )[0]

    assert report.entity_slug == "o-brien-sons-ltd"


# --- create_radar_signals: the async orchestration ------------------------------------------


class FakeRadar:
    def __init__(self) -> None:
        self.reports: dict[str, Any] = {}
        self.entities: dict[str, dict[str, Any]] = {}
        self._next = 0

    def new_report_id(self) -> str:
        self._next += 1
        return f"r{self._next}"

    def create_report(self, report_id: str, report: Any) -> None:
        self.reports[report_id] = report

    def get_entity(self, slug: str) -> dict[str, Any] | None:
        return self.entities.get(slug)

    def set_entity(self, entity: Any) -> None:
        self.entities[entity.slug] = entity.model_dump()


async def test_writes_one_document_per_report_and_returns_their_ids() -> None:
    radar = FakeRadar()
    clauses = [_clause(1, category="passport_retention"), _clause(2, category="recruitment_fees")]

    ids = await create_radar_signals(
        "SG", "employment_contract", clauses, _facts(), cast(RadarRepository, radar)
    )

    assert len(ids) == 2 and set(ids) == set(radar.reports)
    assert {r.violation_type for r in radar.reports.values()} == {
        "passport_retention",
        "illegal_recruitment_fee",
    }


async def test_a_contract_signal_also_updates_the_entitys_risk_profile() -> None:
    radar = FakeRadar()
    clauses = [_clause(1, category="passport_retention"), _clause(2, category="recruitment_fees")]

    await create_radar_signals(
        "SG", "employment_contract", clauses, _facts(), cast(RadarRepository, radar)
    )

    entity = radar.entities["acme-pte-ltd"]
    # Two distinct violation types on one contract: two separate reports, each its own
    # incident (no clustering runs on this path), so this alone is already 2 incidents.
    assert (entity["report_count"], entity["incident_count"]) == (2, 2)
    assert entity["flagged"] is True


async def test_no_danger_clauses_writes_nothing() -> None:
    radar = FakeRadar()

    ids = await create_radar_signals(
        "SG",
        "employment_contract",
        [_clause(risk="caution")],
        _facts(),
        cast(RadarRepository, radar),
    )

    assert ids == [] and radar.reports == {}


async def test_no_named_entity_writes_nothing() -> None:
    radar = FakeRadar()

    ids = await create_radar_signals(
        "SG",
        "employment_contract",
        [_clause()],
        _facts(employer_name=None),
        cast(RadarRepository, radar),
    )

    assert ids == [] and radar.reports == {}
