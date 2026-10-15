"""Masks personal identifiers in user-submitted text before it is logged, sent to analytics
or stored (NF-F0-008).

Covers phone numbers, emails, passport / national-ID numbers for the six corridors' countries
(SG, PH, IN, ID, MY, JP, AU), bank account / card numbers and URLs. It does not mask personal
names or amounts: an amount is the evidence a scam check or the coach
works from, and it identifies nobody.

Detection is pattern-based, so it favours masking too much over too little: a 9-digit order
number is replaced like an account number would be. Output is idempotent: the tokens contain
no digits, `@`, `.` or `://`, so a second pass finds nothing new.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

PHONE = "[PHONE]"
EMAIL = "[EMAIL]"
ID_NUMBER = "[ID]"
ACCOUNT = "[ACCOUNT]"
URL = "[URL]"

# Not at the start of a word, and not the tail of a longer number split by one space or
# hyphen ("1234 5678 9012 3456" must not yield a phone number from its first 8 digits).
_PRE = r"(?<![\w+])(?<!\d{3}[ \-])"
_POST = r"(?![\w]|[ \-]\d{3})"
# Stricter for fixed-size IDs: any further group means it is something longer (an account
# written 012-345-678-9 is not a TFN with a stray digit).
_ID_POST = r"(?![\w]|[ \-]\d)"
_SEP = r"(?:[ .\-]?\(?|\)[ .\-]?)?"

# A value after a label: tokens that carry a digit, so "passport expired" is left alone.
_GAP = r"[\s.:#=\-]*"
_LABEL_GAP = (
    rf"{_GAP}(?:(?:(?:no|num|number|nbr|id|card|nomor)\b|नंबर|नम्बर|संख्या|নম্বর|নং){_GAP})*"
    rf"(?:is\b{_GAP})?"
)
_ID_VALUE = r"((?=[A-Z0-9]*\d)[A-Z0-9]{5,20}(?:[ \-](?=[A-Z]*\d)[A-Z0-9]{2,6}\b)*)"

_URL_TAIL = r"""[^\s<>"']*[^\s<>"'.,;:!?)\]}]"""
# Lowercase only for the final label: "Sir.My name" is a typo, "sir.my" is rare enough to mask.
_TLDS = (
    "com|net|org|info|biz|co|io|me|ly|gl|in|ph|sg|my|id|jp|kr|hk|au|np|bd|link|xyz|top|app"
    "|site|online|live|club|shop|vip|cc|tk|ml|ga|cf|gq|ru|cn|us|uk"
)


@dataclass(frozen=True)
class _Rule:
    token: str
    pattern: re.Pattern[str]
    group: int = 0  # which part of the match is masked; labels before a value are kept
    min_digits: int = 0


def _rule(
    token: str, pattern: str, *, flags: int = 0, group: int = 0, min_digits: int = 0
) -> _Rule:
    return _Rule(token, re.compile(pattern, flags), group, min_digits)


# Order matters: a URL is masked whole before the email inside its query string is seen, and a
# labelled value is masked as what it is called before the generic digit rules guess at it.
_RULES: tuple[_Rule, ...] = (
    _rule(URL, rf"\bh(?:tt|xx)ps?(?:://|\[:\]//){_URL_TAIL}|\bftp://{_URL_TAIL}", flags=re.I),
    _rule(URL, rf"(?<![\w.@])www\d?(?:\.|\[\.\]){_URL_TAIL}", flags=re.I),
    _rule(
        URL,
        r"(?<![\w@.\-/])(?:(?i:[a-z0-9][a-z0-9\-]*)(?:\.|\[\.\]))+"
        rf"(?:{_TLDS})(?![\w\-@]|\.\w)(?::\d{{2,5}})?(?:/{_URL_TAIL})?",
    ),
    _rule(EMAIL, r"(?<![\w.+\-])[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"),
    # Written to dodge filters; scam messages do this.
    _rule(
        EMAIL,
        r"(?<![\w.+\-])[\w.+\-]+ ?[\[(] ?at ?[\])] ?[\w\-]+"
        r"(?: ?(?:[\[(] ?dot ?[\])]|\.) ?[\w\-]+)+",
        flags=re.I,
    ),
    _rule(
        EMAIL,
        r"(?<![\w.+\-])[\w.+\-]+ at [\w\-]+(?: dot [\w\-]+)+",
        flags=re.I,
    ),
    # A UPI payment address ("name@okbank"): an email-shaped string with no dotted domain.
    _rule(ACCOUNT, r"(?<![\w.@])[\w.\-]{2,64}@[A-Za-z][A-Za-z0-9]{1,30}(?![\w@]|\.\w)"),
    # A number named as a phone number, whatever its length or grouping.
    _rule(
        PHONE,
        r"(?:\b(?:phone|tel|telephone|mobile|mob|cell|whatsapp|viber|telegram|contact|call|text"
        r"|sms|hp|wa|telepon|telefon)\b|फोन|मोबाइल|ফোন|মোবাইল)"
        rf"{_GAP}(\+?\d{{2,}}(?:[ .\-]\d{{2,}}){{0,5}})",
        flags=re.I,
        group=1,
        min_digits=7,
    ),
    _rule(
        ID_NUMBER,
        r"(?:\b(?:passport|nric|fin|aadhaar|aadhar|pan|nik|ktp|tfn|philsys|umid|sss|tin|ssn|nid"
        r"|ic|paspor|national id|identity card)\b|पासपोर्ट|आधार|राहदानी|পাসপোর্ট)"
        rf"{_LABEL_GAP}{_ID_VALUE}",
        flags=re.I,
        group=1,
    ),
    _rule(
        ACCOUNT,
        r"(?:\b(?:a/c|acct?|account|iban|card|rek(?:ening)?|akaun|khata)\b|खाता|হিসাব|অ্যাকাউন্ট)"
        rf"{_LABEL_GAP}((?=(?:\d[ \-]?){{6}})\d{{3,}}(?:[ \-]\d+){{0,6}})",
        flags=re.I,
        group=1,
    ),
    # IBAN: country letters, check digits, then the bank's own letters and digits.
    _rule(ACCOUNT, r"(?<![\w])[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?(?![\w])"),
    # Letters-and-digits IDs. Singapore NRIC / FIN and the generic passport shape (one or two
    # letters, seven or eight digits: PH, IN, ID, MY, AU, JP, BD, NP) overlap on purpose.
    _rule(ID_NUMBER, r"(?<![\w])[STFGM]\d{7}[A-Z](?![\w])", flags=re.I),
    _rule(ID_NUMBER, r"(?<![\w])[A-Z]{5}\d{4}[A-Z](?![\w])", flags=re.I),  # India PAN
    _rule(ID_NUMBER, r"(?<![\w])[A-Z]{3}\d{7}(?![\w])", flags=re.I),  # India voter EPIC
    _rule(ID_NUMBER, r"(?<![\w])[A-Z]{2}\d{8}[A-Z]{2}(?![\w])", flags=re.I),  # Japan residence card
    _rule(ID_NUMBER, r"(?<![\w])[A-Z]{1,2}\d{7,8}[A-Z]?(?![\w])", flags=re.I),  # passports
    # International format. Needs the "+" so a bare 8-15 digit run is not read as a phone.
    _rule(PHONE, rf"(?<![\w+])\(?\+\d(?:{_SEP}\d){{7,14}}(?!\d)"),
    # Digit-only IDs whose grouping gives them away: Aadhaar / My Number / PhilSys (4-4-4),
    # Malaysian NRIC, Philippine SSS / UMID, Australian TFN.
    _rule(ID_NUMBER, rf"{_PRE}\d{{4}}[ \-]\d{{4}}[ \-]\d{{4}}{_ID_POST}"),
    _rule(ID_NUMBER, rf"{_PRE}\d{{6}}-\d{{2}}-\d{{4}}{_ID_POST}"),
    _rule(ID_NUMBER, rf"{_PRE}\d{{2,4}}-\d{{7}}-\d{_ID_POST}"),
    _rule(ID_NUMBER, rf"{_PRE}\d{{3}}[ \-]\d{{3}}[ \-]\d{{3}}{_ID_POST}"),
    _rule(PHONE, rf"{_PRE}\(\d{{2,4}}\) ?\d{{3,4}}[ \-]?\d{{3,4}}{_POST}"),
    # Digits typed one at a time to dodge filters.
    _rule(PHONE, r"(?<![\w])\d(?:[ .\-]\d){7,16}(?![\w])"),
    # Local formats, no "+": trunk-prefix 0 (PH, MY, JP, AU, KR, ...), Indonesian 08xx which
    # runs longer, Indian / Nepali mobiles (10 digits from 6-9), SG / HK (8 digits from 5-9).
    _rule(PHONE, rf"{_PRE}0\d(?:[ \-]?\d){{8,9}}{_POST}"),
    _rule(PHONE, rf"{_PRE}08\d{{2}}(?:[ \-]?\d){{7,9}}{_POST}"),
    _rule(PHONE, rf"{_PRE}[6-9]\d{{4}}[ \-]?\d{{5}}{_POST}"),
    _rule(PHONE, rf"{_PRE}[5-9]\d{{3}}[ \-]?\d{{4}}{_POST}"),
    # Whatever digit run is left and is long enough to be an account, card or national number.
    # Groups need 3+ digits so dates and "5 000 000"-style amounts are not caught.
    _rule(
        ACCOUNT, rf"{_PRE}\d{{3,}}(?:[ \-]\d{{3,}}){{0,5}}(?:[ \-]\d{{1,2}})?{_POST}", min_digits=9
    ),
)


@dataclass(frozen=True)
class MaskedValue:
    """One value `redact` masked: the token that replaced it and the value itself."""

    token: str
    value: str


@dataclass(frozen=True)
class RedactionResult:
    """Masked text plus how many values of each kind were masked, safe to log or count."""

    text: str
    counts: Mapping[str, int]

    @property
    def found(self) -> bool:
        return bool(self.counts)


def _ascii_digits(text: str) -> str:
    """Same-length copy with Devanagari, Bengali and other native digits as 0-9.

    Hindi, Nepali and Bengali messages write numbers in their own digits; the patterns are
    written for ASCII, and equal length lets spans found here be cut from the original.
    """
    if text.isascii():
        return text
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def _mask(
    text: str, rule: _Rule, counts: Counter[str], found: list[MaskedValue] | None = None
) -> str:
    parts: list[str] = []
    last = 0
    for match in rule.pattern.finditer(_ascii_digits(text)):
        start, end = match.span(rule.group)
        if start < 0:
            continue
        if (
            rule.min_digits
            and sum(c.isdecimal() for c in match.group(rule.group)) < rule.min_digits
        ):
            continue
        parts.append(text[last:start])
        parts.append(rule.token)
        if found is not None:
            found.append(MaskedValue(rule.token, text[start:end]))
        last = end
        counts[rule.token] += 1
    if not parts:
        return text
    parts.append(text[last:])
    return "".join(parts)


def redact(text: str) -> RedactionResult:
    """Mask phone numbers, emails, ID and account numbers and URLs in `text`.

    Returns the masked text and per-kind counts; the counts never hold the values.
    """
    counts: Counter[str] = Counter()
    for rule in _RULES:
        text = _mask(text, rule, counts)
    return RedactionResult(text=text, counts=dict(counts))


def redact_values(text: str) -> list[MaskedValue]:
    """The values `redact` would mask in `text`, in the order its rules find them.

    For code that must act on the values themselves (the Scam Analyzer's indicator extraction,
    NF-SA-011) and wants the same idea of "a phone number" or "a link" as the masking, not a
    second set of patterns that could disagree with it. The values are the worker's own
    message: keep them out of logs and out of anything sent to a model.
    """
    found: list[MaskedValue] = []
    counts: Counter[str] = Counter()
    for rule in _RULES:
        text = _mask(text, rule, counts, found)
    return found


def redact_text(text: str) -> str:
    """`redact(text).text`, for callers that only need the masked string."""
    return redact(text).text
