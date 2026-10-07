"""Amounts of money a message names, found by fixed rules (NF-SA-011).

Only an amount next to a currency the project works with (a code such as `SGD`, a symbol such as
`RM` or `₱`, or a word such as `ringgit`) is an amount: a bare "800" may be a year, a time or a
house number. The classifier decides which amount is the one being asked for (`details.amount`);
these are a second pair of eyes for a model that reads "5.000" in Indonesian as five.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.scam import ScamAmount

MAX_AMOUNTS = 5

# Unambiguous markers only. "$" and "Rs" are left out: they mean several currencies at once.
_CODES = "SGD|AUD|MYR|IDR|INR|PHP|JPY|HKD|USD|NPR|BDT|KRW"
_BEFORE: dict[str, str] = {
    "S$": "SGD", "A$": "AUD", "HK$": "HKD", "US$": "USD", "RM": "MYR", "Rp": "IDR",
    "₹": "INR", "₱": "PHP", "¥": "JPY",
}  # fmt: skip
_AFTER: dict[str, str] = {
    "ringgit": "MYR", "rupiah": "IDR", "peso": "PHP", "pesos": "PHP", "yen": "JPY", "円": "JPY",
}  # fmt: skip

_NUMBER = r"\d{1,3}(?:[ ,.]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?"
_SYMBOLS = "|".join(re.escape(s) for s in sorted(_BEFORE, key=len, reverse=True))
_WORDS = "|".join(re.escape(w) for w in sorted(_AFTER, key=len, reverse=True))
# Codes in any case ("sgd800"); symbols as written, so a stray "rm" is not read as ringgit.
_MARKER_FIRST = re.compile(rf"(?<![A-Za-z])((?i:{_CODES})|{_SYMBOLS})\s?({_NUMBER})")
_NUMBER_FIRST = re.compile(rf"(?<![\d.,])({_NUMBER})\s?({_CODES}|{_WORDS})(?![A-Za-z])", re.I)


def _ascii_digits(text: str) -> str:
    """Devanagari, Bengali and other native digits as 0-9; the same length."""
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)


def parse_number(raw: str) -> float | None:
    """`1,800` `1.800` `5 000` `50,000.00` `1.234,56` `12.5` `800` as numbers.

    The last `.` or `,` is the decimal point unless exactly three digits follow it, which makes
    it a thousands mark. So "1.800" is eighteen hundred, not one point eight: in the corridors
    that write amounts this way (Indonesia) it is the common reading, and a scam that asks for
    "1.8" of anything is rare.
    """
    text = raw.strip()
    last = max(text.rfind("."), text.rfind(","))
    tail = text[last + 1 :] if last >= 0 else ""
    try:
        if last >= 0 and len(tail) != 3:
            return float(re.sub(r"[ ,.]", "", text[:last]) + "." + tail)
        return float(re.sub(r"[ ,.]", "", text))
    except ValueError:
        return None


def _currency(marker: str) -> str:
    if marker.upper() in _CODES.split("|"):
        return marker.upper()
    return _BEFORE.get(marker) or _AFTER.get(marker.lower(), "")


def _amount(number: str, marker: str) -> ScamAmount | None:
    value = parse_number(number)
    currency = _currency(marker)
    if value is None or value <= 0 or not currency:
        return None
    return ScamAmount(amount=value, currency=currency)


def find_amounts(text: str) -> list[ScamAmount]:
    """Distinct amounts with a known currency, in the order they appear, at most five."""
    plain = _ascii_digits(text)
    found: list[tuple[int, ScamAmount | None]] = []
    for match in _MARKER_FIRST.finditer(plain):
        found.append((match.start(), _amount(match.group(2), match.group(1))))
    for match in _NUMBER_FIRST.finditer(plain):
        found.append((match.start(), _amount(match.group(1), match.group(2))))
    seen: set[tuple[float, str]] = set()
    out: list[ScamAmount] = []
    for _, amount in sorted(found, key=lambda item: item[0]):
        if amount is not None and (amount.amount, amount.currency) not in seen:
            seen.add((amount.amount, amount.currency))
            out.append(amount)
    return out[:MAX_AMOUNTS]
