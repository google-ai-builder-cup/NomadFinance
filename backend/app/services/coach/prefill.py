"""Offering the salary from the worker's latest contract analysis (NF-FC-015).

Contract Shield has already read the worker's employment contract (`extracted`: employer, salary,
currency, period). The Coach offers that salary instead of asking for it, but **never uses it
until the worker says it is right**: the offer becomes an unconfirmed `monthly_salary` slot
(`source: contract_prefill`) when the interview reaches the income stage, the coach asks "Is that
right?", and only a yes (`confirmed`) makes it an answer. Any other reply replaces or drops it.

Pure functions over stored documents; `session_service.py` and `turn_prompt.py` call them, so the
reply the worker sees and the answers that are stored follow the same rules.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.repositories.contract_repo import ContractRepository
from app.services.coach.guard_rules import is_attack

PREFILL_SLOT = "monthly_salary"
# A day or an hour is not offered: the coach never guesses the days a worker works.
OFFERED_PERIODS = ("month", "week", "year")
CURRENCIES = (
    "SGD",
    "KRW",
    "MYR",
    "JPY",
    "HKD",
    "AUD",
    "PHP",
    "INR",
    "IDR",
    "NPR",
    "BDT",
)
RECENT_CONTRACTS = 10
PREFILL_CONFIDENCE = 0.9
MAX_EMPLOYER_CHARS = 40
MAX_EMPLOYER_WORDS = 6
_EMPLOYER_PUNCTUATION = " .,&'()/-"


@dataclass(frozen=True)
class Prefill:
    contract_id: str
    amount: float
    currency: str
    period: str
    employer: str | None


# Finds the offer for a worker (`dependencies.get_coach_sessions` wires the real one).
PrefillFinder = Callable[[str], Awaitable["Prefill | None"]]


def _name_char(char: str) -> bool:
    """A letter or digit of any script, its combining marks (the vowel signs of Devanagari and
    Bengali are marks, not letters), or the punctuation a company name uses."""
    return char.isalnum() or unicodedata.category(char)[0] == "M" or char in _EMPLOYER_PUNCTUATION


def clean_employer(name: object) -> str | None:
    """The employer's name if it is short and looks like a name, else None.

    The name comes from a document the worker uploaded, and it is shown to the model inside the
    question, so a long text, markup or anything that gives the coach orders is dropped.
    """
    if not isinstance(name, str):
        return None
    text = " ".join(name.split())
    if not text or len(text) > MAX_EMPLOYER_CHARS or len(text.split()) > MAX_EMPLOYER_WORDS:
        return None
    if not text[0].isalnum() or not all(_name_char(c) for c in text) or is_attack(text):
        return None
    return text


def find_prefill(contracts: list[tuple[str, dict[str, Any]]]) -> Prefill | None:
    """The salary of the newest employment contract that has a usable one (`contracts` newest
    first). Contracts that are not analysed, are not employment contracts, or state a pay the
    Coach does not take (daily, hourly, zero) are passed over."""
    for contract_id, document in contracts:
        detected = document.get("detected") or {}
        extracted = document.get("extracted") or {}
        if document.get("status") != "completed":
            continue
        if detected.get("document_kind") != "employment_contract":
            continue
        amount, currency = extracted.get("salary_amount"), extracted.get("salary_currency")
        period = extracted.get("salary_period")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
            continue
        if currency not in CURRENCIES or period not in OFFERED_PERIODS:
            continue
        employer = clean_employer(extracted.get("employer_name"))
        return Prefill(contract_id, float(amount), str(currency), str(period), employer)
    return None


def contract_prefill_finder(contracts: ContractRepository) -> PrefillFinder:
    """The finder that reads the worker's newest contracts from Firestore."""

    async def find(uid: str) -> Prefill | None:
        recent = await run_in_threadpool(contracts.recent, uid, RECENT_CONTRACTS)
        return find_prefill(recent)

    return find


def prefill_document(offer: Prefill) -> dict[str, Any]:
    """The offer as stored on the session (`coach_sessions.prefill`, docs/data-model)."""
    return {
        "contract_id": offer.contract_id,
        "fields": ["salary", "employer"] if offer.employer else ["salary"],
        "confirmed": False,
        "state": "offered",
        "salary": {"amount": offer.amount, "currency": offer.currency, "period": offer.period},
        "employer": offer.employer,
    }


def apply_prefill(
    document: dict[str, Any],
    slots: dict[str, dict[str, Any]],
    stage: str,
    *,
    now: datetime,
    turn: int,
    worker_spoke: bool,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    """The slots and the offer as they stand after a turn.

    `slots` and `stage` are what the turn gives before the offer is considered. States of the
    offer: `offered` (waiting for the income stage), `asked` (stored as an unconfirmed slot, the
    coach has asked), `resolved` (confirmed, answered another way, or turned down).

    * offered and the interview is at income with no salary yet: the offer becomes an
      unconfirmed slot and is asked about;
    * asked and the worker has since answered another way, or confirmed: resolved;
    * asked, the worker spoke, and the slot is still unconfirmed: turned down, the slot is
      removed and the plain question is asked.
    """
    offer = document.get("prefill")
    if not offer or offer.get("state") == "resolved":
        return slots, offer
    slots = dict(slots)
    record = slots.get(PREFILL_SLOT)
    if offer["state"] == "asked":
        if record is None or record.get("source") != "contract_prefill" or record.get("confirmed"):
            return slots, {**offer, "state": "resolved", "confirmed": record is not None}
        if worker_spoke:
            del slots[PREFILL_SLOT]
            return slots, {**offer, "state": "resolved"}
        return slots, offer
    if record is not None:
        return slots, {**offer, "state": "resolved"}
    if stage != "income":
        return slots, offer
    slots[PREFILL_SLOT] = {
        "value": offer["salary"],
        "confidence": PREFILL_CONFIDENCE,
        "source": "contract_prefill",
        "confirmed": False,
        "updated_at": now,
        "turn": turn,
    }
    return slots, {**offer, "state": "asked"}


def prefill_question(offer: dict[str, Any]) -> str:
    """The question to put in words, in English: the offer, and whether it is right."""
    salary = offer["salary"]
    amount = f"{salary['amount']:,.2f}".rstrip("0").rstrip(".")
    who = f" with {offer['employer']}" if offer.get("employer") else ""
    return (
        f"Your contract{who} says the pay is {amount} {salary['currency']} each "
        f"{salary['period']}. Ask whether that is right."
    )
