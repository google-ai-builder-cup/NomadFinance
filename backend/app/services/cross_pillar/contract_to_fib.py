"""Contract Shield feeds the Financial Identity Builder (NF-P3-024, the cross-pillar
flow #5: "Verified employment adds" to P4).

When an employment contract's analysis reads a stated salary, it is logged as one verified
income entry (`source: "contract"`, `verified: true`, `contract_ref`), the same collection
NF-P3-010's manual entries write into. `financial_profile`'s `verified_employment` line and
the narrative (NF-P3-013) pick it up from there like any other income entry.

No Gemini call: `salary_amount`/`salary_currency` are already-checked facts from step 2
(`detector.py::_clean`), never a fresh model guess here.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi.concurrency import run_in_threadpool

from app.repositories.fib_repo import FibRepository
from app.schemas.contract import DocumentKind
from app.schemas.contract_complaint import ContractFacts

logger = logging.getLogger(__name__)

SOURCE = "contract"
CATEGORY = "salary"
# Firestore's auto ids: 20 letters and digits (contract_analysis.py's own ContractId pattern),
# safe to interpolate directly.
_ENTRY_ID_PREFIX = "contract_"


# Weeks in an average month: 52 weeks over 12 months.
WEEKS_PER_MONTH = 52 / 12


def monthly_equivalent(amount: float, period: str | None) -> float | None:
    """What a stated salary comes to in a month, or None when the contract does not say enough.

    No period is read as monthly (the common case, and what the figure was taken as before);
    an hourly or daily rate has no monthly figure without the hours or days worked.
    """
    if period is None or period == "month":
        return amount
    if period == "week":
        return round(amount * WEEKS_PER_MONTH, 2)
    return None


def build_income_entry(
    facts: ContractFacts, document_kind: DocumentKind
) -> dict[str, object] | None:
    """The income entry to log, or None when there is nothing to log.

    Only for an employment contract (a recruitment agreement's fee schedule is not the
    worker's own income) with a usable salary. `amount` is the stated figure exactly as the
    contract reads it, whatever `salary_period` is: the PDF export prints it verbatim as "the
    salary" (`report_html.py`), with the period beside it. What it comes to in a month is
    `monthly_amount`, which the score reads instead (`profile_metrics._stated_amount`): the
    same for a monthly salary, scaled for a weekly one, and None for an hourly or daily rate,
    where the contract does not say how many hours or days, so it is left out of the money
    metrics rather than added up as a month's pay.
    """
    if document_kind != "employment_contract":
        return None
    if facts.salary_amount is None or facts.salary_currency is None:
        return None

    entry: dict[str, object] = {
        "amount": facts.salary_amount,
        "currency": facts.salary_currency,
        "category": CATEGORY,
        "category_source": "user",
        "verified": True,
        "source": SOURCE,
    }
    if facts.salary_period is not None:
        entry["salary_period"] = facts.salary_period
    entry["monthly_amount"] = monthly_equivalent(facts.salary_amount, facts.salary_period)
    if facts.employer_name:
        entry["employer_name"] = facts.employer_name
    return entry


async def log_contract_income(
    uid: str,
    contract_id: str,
    document_kind: DocumentKind,
    facts: ContractFacts,
    fib: FibRepository,
    now: datetime,
) -> str | None:
    """Write the verified income entry for this contract, if it has a usable salary.

    The entry id is derived from `contract_id`, not `fib.new_id()`: re-analyzing the same
    contract (a different host country chosen, or the content changed) must overwrite the
    same entry rather than log a second one that would double-count toward
    `income_stability`. For the same reason, one contract salary per calendar month: a
    worker on a work permit has one employer, and checking a second contract (a new job, or
    a draft) in the same month replaces the first rather than doubling that month's income.
    `contract_ref` is what `financial_profile.verified_employment` is built from.

    Returns:
        The entry id written, or None when there was nothing to log.
    """
    entry = build_income_entry(facts, document_kind)
    if entry is None:
        logger.info("contract_income_skipped contract_id=%s kind=%s", contract_id, document_kind)
        return None

    entry_id = f"{_ENTRY_ID_PREFIX}{contract_id}"
    entry_date = now.date().isoformat()
    entry["entry_date"] = entry_date
    entry["contract_ref"] = contract_id
    month = entry_date[:7]
    for other_id, other in await run_in_threadpool(fib.list_entries, uid, "income"):
        same_month = str(other.get("entry_date", "")).startswith(month)
        if other_id != entry_id and other.get("source") == SOURCE and same_month:
            await run_in_threadpool(fib.delete_entry, uid, "income", other_id)
            logger.info("contract_income_replaced old=%s new=%s", other_id, entry_id)
    await run_in_threadpool(fib.save_entry, uid, "income", entry_id, entry)
    # The amount stays out of the log: a worker's pay is personal financial data (NF-P4-004).
    logger.info("contract_income_logged contract_id=%s", contract_id)
    return entry_id
