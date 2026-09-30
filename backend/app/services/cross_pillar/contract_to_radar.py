"""Contract Shield feeds Exploitation Radar (NF-P2-021, design doc's cross-pillar flow #2).

When a contract's comparison finds `danger` clauses (the same threshold that triggers the
complaint letter, `services/contract/letter.py`), the flagged employer or agency is reported
to `radar_reports` automatically, `source: "contract_signal"` (docs/data-model/collections/
radar.md). No Gemini call: the category is already a checked fact from step 4
(NF-P2-004), never a fresh model guess, and there is no free text to spam-check.

Anonymized on purpose: no `reporter_hash`, no fact about the worker, and never a clause's raw
`text` (only its English `explanation`), so a clause that happens to quote the worker's own
name is never repeated here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from fastapi.concurrency import run_in_threadpool

from app.repositories.radar_repo import RadarRepository
from app.schemas.contract import DocumentKind, HostCountryCode
from app.schemas.contract_compare import ClauseCategory, ComparedClause
from app.schemas.contract_complaint import ContractFacts
from app.schemas.radar import RadarEntityType, RadarReport, RadarValidation, RadarViolationType
from app.services.radar.aggregation import update_entity_risk
from app.utils.slugs import slugify

logger = logging.getLogger(__name__)

# Contract Shield's 15 curated categories, mapped to radar's 9 violation types. A category
# with no close match becomes "other": still a real report, never silently dropped.
VIOLATION_TYPE: dict[ClauseCategory, RadarViolationType] = {
    "minimum_wage": "wage_theft",
    "working_hours": "other",
    "overtime_pay": "wage_theft",
    "rest_days_and_holidays": "other",
    "annual_leave": "other",
    "sick_leave": "other",
    "salary_payment": "wage_theft",
    "salary_deductions": "illegal_deduction",
    "termination_notice": "other",
    "early_termination": "other",
    "recruitment_fees": "illegal_recruitment_fee",
    "passport_retention": "passport_retention",
    "accommodation": "other",
    "insurance_and_injury": "other",
    "social_security": "other",
    "other": "other",
}

# A contract_signal report is not free text a worker wrote and Gemini has not scored it, so
# these say that plainly rather than inventing a score. `category` is a checked fact from
# step 4 (never a model's raw guess), hence confidence 1.0, not a model's own number.
SIGNAL_VALIDATION = RadarValidation(
    spam_score=0.0, category_confidence=1.0, model="contract_shield"
)

# A description this long is already several clauses' worth; longer only repeats the point.
MAX_DESCRIPTION_CHARS = 1000


def choose_entity(
    document_kind: DocumentKind, facts: ContractFacts
) -> tuple[RadarEntityType, str] | None:
    """Who the report is about, or None if the contract named no one to report.

    A recruitment agreement is about the agency; anything else, including a recruitment
    agreement with no agency name, falls back to the employer.
    """
    if document_kind == "recruitment_agreement" and facts.agency_name:
        return "recruitment_agency", facts.agency_name
    if facts.employer_name:
        return "employer", facts.employer_name
    return None


def _description(clauses: list[ComparedClause]) -> str:
    text = " ".join(clause.explanation.strip() for clause in clauses)
    if len(text) <= MAX_DESCRIPTION_CHARS:
        return text
    return text[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "…"


def build_reports(
    host_country: HostCountryCode,
    document_kind: DocumentKind,
    clauses: list[ComparedClause],
    facts: ContractFacts,
    new_id: Callable[[], str],
    now: datetime,
) -> list[RadarReport]:
    """One `RadarReport` per distinct violation type among the danger clauses.

    Args:
        host_country: The contract's host country (`radar_reports.host_country`; Contract
            Shield never knows a remittance corridor, so `corridor_id` is never set).
        document_kind: From step 2; picks whether the agency or the employer is reported.
        clauses: The comparison's clauses; only `risk == "danger"` ones are used.
        facts: Employer and agency names from step 2.
        new_id: Called once per report that will actually be written
            (`RadarRepository.new_report_id`): a report's own id doubles as its `cluster_id`
            (radar.md), so it must be known before the report is built, not patched in after.
        now: Current UTC time.

    Returns:
        No danger clauses, or no employer/agency name on the contract: an empty list, and
        `new_id` is never called. Otherwise one report per distinct mapped violation type,
        each starting its own cluster: with no clustering pipeline running yet (NF-P3-002),
        every contract signal starts its own.
    """
    danger = [clause for clause in clauses if clause.risk == "danger"]
    if not danger:
        return []
    entity = choose_entity(document_kind, facts)
    if entity is None:
        logger.info("radar_signal_skipped reason=no_named_entity country=%s", host_country)
        return []
    entity_type, entity_name = entity
    slug = slugify(entity_name)

    grouped: dict[RadarViolationType, list[ComparedClause]] = {}
    for clause in danger:
        grouped.setdefault(VIOLATION_TYPE[clause.category], []).append(clause)

    return [
        RadarReport(
            entity_type=entity_type,
            entity_name=entity_name,
            entity_slug=slug,
            violation_type=violation_type,
            host_country=host_country,
            description=_description(group),
            language="en",
            cluster_id=new_id(),
            source="contract_signal",
            validation=SIGNAL_VALIDATION,
            created_at=now,
        )
        for violation_type, group in grouped.items()
    ]


async def create_radar_signals(
    host_country: HostCountryCode,
    document_kind: DocumentKind,
    clauses: list[ComparedClause],
    facts: ContractFacts,
    radar: RadarRepository,
) -> list[str]:
    """Write the radar reports for a contract's danger clauses. Cross-pillar flow #2.

    Returns:
        The ids written (possibly empty: no danger clauses, or no named employer/agency).
    """
    # new_report_id() only generates an id client-side (no Firestore round trip), so it is
    # called directly here, not through run_in_threadpool.
    now = datetime.now(UTC)
    reports = build_reports(host_country, document_kind, clauses, facts, radar.new_report_id, now)
    for report in reports:
        await run_in_threadpool(radar.create_report, report.cluster_id, report)
        # A contract signal always starts its own cluster (no clustering pipeline runs on
        # this path), so report_id == cluster_id here, same as a brand-new user report.
        await update_entity_risk(report, report.cluster_id, radar, now)
    if reports:
        logger.info(
            "radar_signal_created country=%s slug=%s reports=%d",
            host_country,
            reports[0].entity_slug,
            len(reports),
        )
    return [report.cluster_id for report in reports]
