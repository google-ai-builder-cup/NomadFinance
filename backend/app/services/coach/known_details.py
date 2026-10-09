"""What the Coach already knows about a worker, offered before the first question (NF-FC-023).

The profile a worker filled in at sign-up (`users/{uid}`: the country, the kind of work) and the
Financial Identity they keep (income, savings, transfers) already hold several answers the
interview asks for, and so does their latest analysed contract (NF-FC-015). Asking for them again
is slow, so the Coach shows them in one card and the worker keeps or changes each one.

**Nothing here is used until the worker agrees.** An offer is stored on the session (`known`) with
no slot written; `kept_slots` turns the ones the worker keeps into confirmed answers, and the
others are asked as usual. Debts, fees, dependents and the leaving date are not in Financial
Identity, so they are always asked.

Pure functions over stored documents, like `prefill.py`; `session_service.py` calls them.
"""

from __future__ import annotations

import asyncio
import math
from collections import Counter
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.repositories.fib_repo import FibRepository
from app.repositories.user_repo import UserRepository
from app.schemas.coach_profile import SlotSource, parse_slot_value
from app.services.coach.prefill import CURRENCIES, PREFILL_SLOT, Prefill

# The order the interview asks in: the card lists in it too.
OFFER_ORDER = (
    "destination_country",
    "job_type",
    "monthly_salary",
    "remittance_target",
    "savings",
    "bank_or_wallet",
)
# Transfers older than this say little about what the worker sends now.
RECENT_TRANSFER_DAYS = 90
# The worker agreed, so the answer counts in full (the contract prefill's 0.9 is for an offer the
# coach had to put into words).
KEPT_CONFIDENCE = 1.0
SLOT_SOURCES: dict[str, SlotSource] = {
    "profile": "profile_prefill",
    "contract": "contract_prefill",
    "income": "identity_prefill",
    "savings": "identity_prefill",
    "transfers": "identity_prefill",
}
BANK_ANSWERS = {
    (True, False): "bank_account",
    (False, True): "mobile_wallet",
    (True, True): "both",
}

# One offered answer: `{"value", "source", "as_of"}`, the shape stored in `coach_sessions.known`.
Item = dict[str, Any]
# Finds the offer for a worker, given the salary of their contract if they have one (`dependencies`
# wires the real one).
KnownFinder = Callable[[str, "Prefill | None"], Awaitable[dict[str, Item]]]


class UnknownKnownSlotError(ValueError):
    """The worker kept an answer that was never offered: a bug of the caller."""


def _amount(value: object) -> float | None:
    """A positive, finite number (a boolean is not one), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def _day(value: object) -> str | None:
    """`YYYY-MM-DD` when it is a real date, else None."""
    if not isinstance(value, str):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _money(amount: float, currency: str, period: str) -> dict[str, Any]:
    return {"amount": round(amount, 2), "currency": currency, "period": period}


def _usual_currency(rows: Sequence[tuple[str, str, float]]) -> str | None:
    """The currency of most rows `(day, currency, amount)`; the newest, then the first by name,
    when two tie. Entries in other currencies are left out rather than added up."""
    if not rows:
        return None
    count = Counter(currency for _, currency, _ in rows)
    newest: dict[str, str] = {}
    for day, currency, _ in rows:
        newest[currency] = max(day, newest.get(currency, ""))
    # `max` keeps the first of equals, so a full tie goes to the first name alphabetically.
    return max(sorted(count), key=lambda c: (count[c], newest[c]))


def profile_items(profile: Mapping[str, Any]) -> dict[str, Item]:
    """The country and the kind of work from the sign-up profile."""
    found: dict[str, Item] = {}
    for slot, field in (("destination_country", "host_country"), ("job_type", "job_type")):
        value = profile.get(field)
        if isinstance(value, str):
            found[slot] = {"value": value, "source": "profile", "as_of": None}
    return found


def contract_item(offer: Prefill | None) -> Item | None:
    """The salary of the newest analysed contract, as `prefill.find_prefill` chose it."""
    if offer is None:
        return None
    value = _money(offer.amount, offer.currency, offer.period)
    return {"value": value, "source": "contract", "as_of": None}


def income_item(entries: Iterable[Mapping[str, Any]]) -> Item | None:
    """The newest logged salary, taken as one month's pay (the card shows its date, so the worker
    can tell when it is not)."""
    best: tuple[str, float, str] | None = None
    for entry in entries:
        amount, day = _amount(entry.get("amount")), _day(entry.get("entry_date"))
        currency = entry.get("currency")
        if entry.get("category") != "salary" or amount is None or day is None:
            continue
        if currency not in CURRENCIES:
            continue
        if best is None or day > best[0]:
            best = (day, amount, str(currency))
    if best is None:
        return None
    return {"value": _money(best[1], best[2], "month"), "source": "income", "as_of": best[0]}


def savings_items(entries: Iterable[Mapping[str, Any]]) -> dict[str, Item]:
    """The balance (deposits minus withdrawals, in the currency used most) and the kind of account
    the savings are in. A balance of zero or less says nothing, and `cash` or no account type says
    nothing about a bank: neither is offered."""
    rows: list[tuple[str, str, float]] = []
    accounts: set[str] = set()
    account_days: list[str] = []
    for entry in entries:
        day = _day(entry.get("entry_date"))
        if day is None:
            continue
        kind = entry.get("account_type")
        if kind in ("bank", "mobile_wallet"):
            accounts.add(str(kind))
            account_days.append(day)
        amount, currency = _amount(entry.get("amount")), entry.get("currency")
        if amount is None or currency not in CURRENCIES:
            continue
        signed = -amount if entry.get("direction") == "withdrawal" else amount
        rows.append((day, str(currency), signed))
    found: dict[str, Item] = {}
    usual = _usual_currency(rows)
    if usual is not None:
        own = [(day, amount) for day, currency, amount in rows if currency == usual]
        balance = sum(amount for _, amount in own)
        if balance > 0:
            found["savings"] = {
                "value": _money(balance, usual, "once"),
                "source": "savings",
                "as_of": max(day for day, _ in own),
            }
    answer = BANK_ANSWERS.get(("bank" in accounts, "mobile_wallet" in accounts))
    if answer is not None:
        found["bank_or_wallet"] = {"value": answer, "source": "savings", "as_of": max(account_days)}
    return found


def transfers_item(entries: Iterable[Mapping[str, Any]], today: date) -> Item | None:
    """What the worker sends home in a month they send: the transfers of the last 90 days, in the
    currency used most, added up and divided by the number of calendar months that have one."""
    since = (today - timedelta(days=RECENT_TRANSFER_DAYS)).isoformat()
    rows: list[tuple[str, str, float]] = []
    for entry in entries:
        day, amount = _day(entry.get("entry_date")), _amount(entry.get("send_amount"))
        currency = entry.get("send_currency")
        if day is None or amount is None or currency not in CURRENCIES:
            continue
        if since <= day <= today.isoformat():
            rows.append((day, str(currency), amount))
    usual = _usual_currency(rows)
    if usual is None:
        return None
    own = [(day, amount) for day, currency, amount in rows if currency == usual]
    months = {day[:7] for day, _ in own}
    average = sum(amount for _, amount in own) / len(months)
    return {
        "value": _money(average, usual, "month"),
        "source": "transfers",
        "as_of": max(day for day, _ in own),
    }


def collect_known(
    *,
    profile: Mapping[str, Any],
    contract: Prefill | None,
    income: Iterable[Mapping[str, Any]],
    savings: Iterable[Mapping[str, Any]],
    transfers: Iterable[Mapping[str, Any]],
    today: date,
) -> dict[str, Item]:
    """Every answer that can be offered, in the interview's order. A value the slot would refuse
    is left out, so the card never offers what the interview could not keep."""
    found = profile_items(profile)
    salary = contract_item(contract) or income_item(income)
    if salary is not None:
        found[PREFILL_SLOT] = salary
    sent = transfers_item(transfers, today)
    if sent is not None:
        found["remittance_target"] = sent
    found.update(savings_items(savings))
    offered: dict[str, Item] = {}
    for slot in OFFER_ORDER:
        item = found.get(slot)
        if item is None:
            continue
        try:
            parse_slot_value(slot, item["value"])
        except ValidationError:
            continue
        offered[slot] = item
    return offered


def known_document(items: Mapping[str, Item]) -> dict[str, Any]:
    """The offer as stored on the session (`coach_sessions.known`, docs/data-model)."""
    return {"state": "offered", "items": dict(items)}


def known_finder(users: UserRepository, fib: FibRepository) -> KnownFinder:
    """The finder that reads the worker's profile and Financial Identity from Firestore."""

    async def find(uid: str, contract: Prefill | None) -> dict[str, Item]:
        profile, income, savings, transfers = await asyncio.gather(
            run_in_threadpool(users.get_profile, uid),
            run_in_threadpool(fib.list_entries, uid, "income"),
            run_in_threadpool(fib.list_entries, uid, "savings"),
            run_in_threadpool(fib.list_entries, uid, "transfers"),
        )
        return collect_known(
            profile=profile,
            contract=contract,
            income=[entry for _, entry in income],
            savings=[entry for _, entry in savings],
            transfers=[entry for _, entry in transfers],
            today=datetime.now(UTC).date(),
        )

    return find


def kept_slots(
    known: Mapping[str, Any], keep: Iterable[str], now: datetime, turn: int
) -> dict[str, dict[str, Any]]:
    """The offered answers the worker keeps, as confirmed slot records.

    Raises:
        UnknownKnownSlotError: `keep` names a slot that was not offered.
    """
    items: Mapping[str, Item] = known["items"]
    wanted = set(keep)
    unknown = sorted(wanted - items.keys())
    if unknown:
        raise UnknownKnownSlotError(f"Not offered: {', '.join(unknown)}.")
    return {
        slot: {
            "value": item["value"],
            "confidence": KEPT_CONFIDENCE,
            "source": SLOT_SOURCES[item["source"]],
            "confirmed": True,
            "updated_at": now,
            "turn": turn,
        }
        for slot, item in items.items()
        if slot in wanted
    }
