from __future__ import annotations

from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.repositories.labor_law_repo import LaborLawRepository
from app.schemas.contract import (
    HostCountryCode,
    JobTypeId,
    LaborLawContext,
    LaborLawRule,
    LaborLawVariant,
)


class LaborLawNotFoundError(Exception):
    """No curated labor-law data is loaded for this country yet (NF-P1-018)."""


def _applicable_variant(variants: list[LaborLawVariant], job_type: JobTypeId) -> LaborLawVariant:
    """The variant that applies to this job type: a job-type variant if one exists for it,
    else the `all` variant.

    NF-P1-017/018 curation guarantees each job type and `all` appear in at most one variant
    and never together, so at most one of the two loops below ever matches.
    """
    for variant in variants:
        if job_type in variant.applies_to:
            return variant
    for variant in variants:
        if "all" in variant.applies_to:
            return variant
    # Unreachable for data written by the loader: every curated rule has an `all` variant or
    # one for every job type. Raised instead of assumed, in case a rule is ever hand-edited.
    raise LaborLawNotFoundError(f"no variant of this rule applies to job type {job_type!r}")


def _rule(category: str, payload: dict[str, Any], job_type: JobTypeId) -> LaborLawRule:
    variants = [LaborLawVariant.model_validate(v) for v in payload["variants"]]
    return LaborLawRule(
        category=category,
        coverage=payload["coverage"],
        title=payload["title"],
        summary=payload["summary"],
        applicable_variant=_applicable_variant(variants, job_type),
        variants=variants,
        references=payload["references"],
        confidence=payload["confidence"],
        notes=payload.get("notes"),
    )


async def get_labor_law_context(
    country: HostCountryCode, job_type: JobTypeId, repo: LaborLawRepository
) -> LaborLawContext:
    """Fetch a host country's curated labor law, with the variant that applies to a job type.

    Args:
        country: The contract's host country, from step 2. The pipeline decides what to do
            when detection found none (D-55) before ever calling this step.
        job_type: The worker's job type, from step 2, used to pick each rule's variant.
        repo: Repository for the `labor_laws` collection.

    Returns:
        Every curated category for the country, plus the `law_version` a stored report would
        be cached against (`docs/data-model/versioning.md`).

    Raises:
        LaborLawNotFoundError: The country has no curated data loaded yet.
    """
    version = await run_in_threadpool(repo.get_version, country)
    raw_rules = await run_in_threadpool(repo.get_rules, country)
    if version is None or not raw_rules:
        raise LaborLawNotFoundError(f"no labor-law data loaded for {country!r}")

    rules = [_rule(category, payload, job_type) for category, payload in sorted(raw_rules.items())]
    return LaborLawContext(country=country, job_type=job_type, law_version=version, rules=rules)
