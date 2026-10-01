"""Financial Identity weekly recompute (NF-P3-013): `users/{uid}/financial_profile/current`.

Run by Cloud Scheduler (infra/cloud-scheduler/fib-recompute.yaml). For each user with
activity: read the four entry collections, compute the metrics (`profile_metrics.py`), have
the reasoning tier write the report text (`narrative.py`), and overwrite the profile.
"""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi.concurrency import run_in_threadpool
from google.api_core.exceptions import GoogleAPICallError

from app.integrations.gemini import GeminiClient, GeminiError
from app.repositories.fib_repo import EntryKind, FibRepository
from app.repositories.rate_repo import RateRepository
from app.repositories.user_repo import UserRepository
from app.schemas.fib_profile import RecomputeResponse
from app.services.fib.narrative import NARRATIVE_PROMPT, write_narrative
from app.services.fib.profile_metrics import (
    Convert,
    Entry,
    compute_metrics,
    entries_in_window,
    overall_score,
)
from app.utils.hashing import hash_user_id

logger = logging.getLogger(__name__)

# Home country (users.md) to the currency the money arrives in.
HOME_CURRENCY = {"PH": "PHP", "IN": "INR", "ID": "IDR", "NP": "NPR", "BD": "BDT"}
APP_LANGUAGES = {"en", "hi", "tl", "id", "ne", "bn"}

# The reasoning tier takes 20 to 40 s a call (D-08), so users are not run one at a time, but
# the free tier's per-model quota is small: a few at once, not all.
MAX_CONCURRENT_USERS = 3

# What an entry that does not match its stored shape raises. Handled per user, so one bad
# document does not stop the run for everyone else.
_BAD_DATA = (KeyError, ValueError, TypeError)


def _convert_with(reporting: str, rates: dict[str, float]) -> Convert:
    def convert(amount: float, currency: str) -> float | None:
        if currency == reporting:
            return amount
        rate = rates.get(currency)
        return None if rate is None else amount * rate

    return convert


async def _rates_to(
    reporting: str, currencies: set[str], rate_repo: RateRepository
) -> dict[str, float]:
    """Latest cached rate from each currency to the reporting currency, where one exists.

    Only the six corridor pairs are cached (rates_cache.md), so a currency outside them has
    no rate and its entries are left out of the money metrics.
    """
    rates: dict[str, float] = {}
    for currency in currencies - {reporting}:
        doc = await run_in_threadpool(rate_repo.get_rate, f"{currency}_{reporting}")
        if doc and doc.get("rate"):
            rates[currency] = float(doc["rate"])
    return rates


async def _reporting_currency(
    home_country: str | None,
    income: list[Entry],
    savings: list[Entry],
    transfers: list[Entry],
    bills: list[Entry],
    rate_repo: RateRepository,
) -> tuple[str, dict[str, float]] | None:
    """The worker's home currency when their entries can be converted to it, otherwise the
    currency they use most. Returns the currency and the rates into it, or None if no entry
    has a currency."""
    money = Counter(
        str(e.data.get("currency")) for e in [*income, *savings] if e.data.get("currency")
    )
    money.update(
        str(t.data.get("receive_currency")) for t in transfers if t.data.get("receive_currency")
    )
    others = Counter(str(b.data.get("currency")) for b in bills if b.data.get("currency"))
    home = HOME_CURRENCY.get(home_country or "")
    ordered = [home, *(c for c, _ in money.most_common()), *(c for c, _ in others.most_common())]
    candidates = list(dict.fromkeys(c for c in ordered if c))
    if not candidates:
        return None
    if not money:
        return candidates[0], {}
    for candidate in candidates:
        rates = await _rates_to(candidate, set(money), rate_repo)
        if any(c == candidate or c in rates for c in money):
            return candidate, rates
    return None


_CONTRACT_ENTRY_PREFIX = "contract_"


def _contract_income_once_a_month(
    raw: list[tuple[str, dict[str, Any]]],
) -> list[tuple[str, dict[str, Any]]]:
    """Repair contract income written before the 2026-10-01 fix, at read time.

    Those entries have no `contract_ref` (so they never showed as verified employment) and a
    second checked contract added a second salary in the same month. Now each gets its ref
    from its id (`contract_<contract_id>`), and only the newest contract salary of a month
    counts, as `contract_to_fib.log_contract_income` keeps it for new entries.
    """
    kept: dict[str, tuple[str, dict[str, Any]]] = {}
    others: list[tuple[str, dict[str, Any]]] = []
    for entry_id, data in raw:
        if data.get("source") != "contract":
            others.append((entry_id, data))
            continue
        if not data.get("contract_ref") and entry_id.startswith(_CONTRACT_ENTRY_PREFIX):
            data = data | {"contract_ref": entry_id.removeprefix(_CONTRACT_ENTRY_PREFIX)}
        month = str(data.get("entry_date", ""))[:7]
        current = kept.get(month)
        if current is None or (str(data.get("entry_date")), entry_id) >= (
            str(current[1].get("entry_date")),
            current[0],
        ):
            kept[month] = (entry_id, data)
    return others + list(kept.values())


def _verified_employment(income: list[Entry]) -> list[dict[str, Any]]:
    """One line per contract that backs an income entry (NF-P3-024), newest entry winning."""
    by_contract: dict[str, dict[str, Any]] = {}
    for entry in sorted(income, key=lambda e: e.day):
        ref = entry.data.get("contract_ref")
        if entry.data.get("verified") is True and ref:
            by_contract[str(ref)] = {
                "employer_name": entry.data.get("employer_name"),
                "salary_amount": entry.data["amount"],
                "salary_currency": entry.data["currency"],
                "contract_ref": str(ref),
            }
    return list(by_contract.values())


def _narrative_input(profile: dict[str, Any]) -> dict[str, Any]:
    """What the narrative prompt may see: no overall score, no employer names."""
    return {
        "period_start": profile["period_start"],
        "period_end": profile["period_end"],
        "months_of_data": profile["months_of_data"],
        "reporting_currency": profile["reporting_currency"],
        "entry_counts": profile["entry_counts"],
        "metrics": profile["metrics"],
        "income_verified_by_contract": bool(profile.get("verified_employment")),
    }


async def recompute_profile(
    uid: str,
    gemini: GeminiClient,
    fib: FibRepository,
    users: UserRepository,
    rate_repo: RateRepository,
    now: datetime,
) -> Literal["recomputed", "no_data"]:
    """Recompute one user's profile and overwrite `financial_profile/current`.

    Returns "no_data" (and writes nothing) when no entry in the last 12 months gives any
    metric a score.

    Raises:
        GeminiError: The narrative could not be written; the previous profile is kept.
    """
    today = now.date()
    loaded: dict[EntryKind, list[Entry]] = {}
    kinds: tuple[EntryKind, ...] = ("income", "transfers", "bills", "savings")
    for kind in kinds:
        raw = await run_in_threadpool(fib.list_entries, uid, kind)
        if kind == "income":
            raw = _contract_income_once_a_month(raw)
        loaded[kind] = entries_in_window(raw, today)
    income, transfers, bills, savings = (
        loaded["income"],
        loaded["transfers"],
        loaded["bills"],
        loaded["savings"],
    )
    everything = [*income, *transfers, *bills, *savings]
    if not everything:
        return "no_data"

    user = await run_in_threadpool(users.get_profile, uid)
    chosen = await _reporting_currency(
        user.get("home_country"), income, savings, transfers, bills, rate_repo
    )
    if chosen is None:
        return "no_data"
    reporting, rates = chosen
    metrics = compute_metrics(
        income, transfers, bills, savings, _convert_with(reporting, rates), today
    )
    overall = overall_score(metrics)
    if overall is None:
        return "no_data"

    first = min(e.day for e in everything)
    profile: dict[str, Any] = {
        "reporting_currency": reporting,
        "period_start": first.isoformat(),
        "period_end": today.isoformat(),
        "months_of_data": (today.year - first.year) * 12 + today.month - first.month + 1,
        "entry_counts": {
            "income": len(income),
            "transfers": len(transfers),
            "bills": len(bills),
            "savings": len(savings),
        },
        "metrics": metrics,
        "overall_score": overall,
    }
    verified = _verified_employment(income)
    if verified:
        profile["verified_employment"] = verified

    language = user.get("preferred_language")
    language = language if language in APP_LANGUAGES else "en"
    text, model = await write_narrative(_narrative_input(profile), language, gemini)
    profile["narrative"] = {"language": language, "text": text, "model": model}
    profile["prompt_versions"] = {NARRATIVE_PROMPT.key: NARRATIVE_PROMPT.version}
    profile["computed_at"] = now

    await run_in_threadpool(fib.save_profile, uid, profile)
    logger.info(
        "fib_profile_recomputed overall_score=%d months=%d", overall, profile["months_of_data"]
    )
    return "recomputed"


async def recompute_all(
    gemini: GeminiClient,
    fib: FibRepository,
    users: UserRepository,
    rate_repo: RateRepository,
    now: datetime,
) -> RecomputeResponse:
    """Recompute every user's profile. A failure on one user is logged and counted, never
    raised: the others still run, and the previous profile of that user stays."""
    uids = await run_in_threadpool(users.list_user_ids)
    gate = asyncio.Semaphore(MAX_CONCURRENT_USERS)

    async def one(uid: str) -> Literal["recomputed", "no_data", "failed"]:
        async with gate:
            try:
                return await recompute_profile(uid, gemini, fib, users, rate_repo, now)
            except (GeminiError, GoogleAPICallError, *_BAD_DATA):
                logger.exception("fib_profile_failed user=%s", hash_user_id(uid))
                return "failed"

    outcomes = Counter(await asyncio.gather(*(one(uid) for uid in uids)))
    logger.info(
        "fib_recompute_done users=%d recomputed=%d no_data=%d failed=%d",
        len(uids),
        outcomes["recomputed"],
        outcomes["no_data"],
        outcomes["failed"],
    )
    return RecomputeResponse(
        users_seen=len(uids),
        recomputed=outcomes["recomputed"],
        skipped_no_data=outcomes["no_data"],
        failed=outcomes["failed"],
        completed_at=datetime.now(UTC),
    )
