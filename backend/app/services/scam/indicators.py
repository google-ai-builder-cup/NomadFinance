from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from app.core.redact import redact_values
from app.schemas.scam import CorridorId, IndicatorFlag, IndicatorKind, ScamAmount, ScamIndicator
from app.services.scam import indicator_checks as checks
from app.services.scam.amounts import find_amounts

logger = logging.getLogger(__name__)

MAX_INDICATORS = 10  # the contract's limit on `indicators`
_MAX_VALUE = 254  # `ScamIndicator.value`

_HANDLE = re.compile(r"(?<![\w@.\-/])@([A-Za-z][A-Za-z0-9_.]{2,31})(?![\w@])")
_DEFANGED_DOT = re.compile(r"\[\.\]|\(\.\)|\[dot\]", re.IGNORECASE)
_TELEGRAM_HOSTS = frozenset({"t.me", "telegram.me", "telegram.dog"})
_WHATSAPP_HOSTS = frozenset({"wa.me", "api.whatsapp.com", "chat.whatsapp.com"})
_HANDLE_PATH = re.compile(r"^/(?:s/)?(\+?[A-Za-z0-9_]{3,64})")


@dataclass(frozen=True)
class Signals:
    """What the fixed rules found in one message: indicators for the answer, amounts for the
    classifier. Holds the worker's own contact points: keep it out of logs and out of prompts
    (use `for_prompt`)."""

    indicators: list[ScamIndicator]
    amounts: list[ScamAmount]

    def for_prompt(self) -> dict[str, object]:
        """What the classifier may see: the kinds, the flags and the amounts, never a value.

        A phone number in a message may be the worker's own, and a scammer's address is no help
        to a model that cannot open it; a flag ("imitates a real bank") is.
        """
        out: dict[str, object] = {}
        groups = {"links": "url", "phones": "phone", "emails": "email", "handles": "handle"}
        for name, kind in groups.items():
            items = []
            for indicator in self.indicators:
                if indicator.kind != kind:
                    continue
                item: dict[str, object] = {"flags": list(indicator.flags)}
                if indicator.imitates:
                    item["imitates"] = indicator.imitates  # a public domain, from our own list
                items.append(item)
            if items:
                out[name] = items
        if self.amounts:
            out["amounts"] = [{"amount": a.amount, "currency": a.currency} for a in self.amounts]
        return out


EMPTY_SIGNALS = Signals(indicators=[], amounts=[])


def make_indicator(
    kind: IndicatorKind,
    value: str,
    flags: list[IndicatorFlag] | None = None,
    imitates: str | None = None,
) -> ScamIndicator:
    """An indicator with its id: the first 8 hex characters of SHA-256 of `kind:value`, the
    key of the data model (scam.md, "The key of an indicator")."""
    key = hashlib.sha256(f"{kind}:{value}".encode()).hexdigest()
    return ScamIndicator(
        id=key[:8],
        kind=kind,
        value=value[:_MAX_VALUE],
        flags=flags or [],
        imitates=imitates,
        seen=None,  # read live from `scam_indicators` when a check is shown (NF-SA-013 writes it)
    )


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.decimal(ch)) if ch.isdecimal() else ch for ch in text)


def _phone(raw: str, corridor_id: CorridorId | None) -> ScamIndicator | None:
    """A phone number as digits with the country code, flagged when it needs it."""
    text = _ascii_digits(raw).strip()
    digits = re.sub(r"\D", "", text)
    international = text.startswith("+") or digits.startswith("00")
    if digits.startswith("00"):
        digits = digits[2:]
    if not 7 <= len(digits) <= 15:
        return None
    flags: list[IndicatorFlag] = []
    if checks.is_premium_rate(digits, international):
        flags.append("premium_rate")
    if checks.is_unexpected_country(digits, international, corridor_id):
        flags.append("unexpected_country")
    return make_indicator("phone", digits, flags)


def _host_flags(host: str) -> tuple[list[IndicatorFlag], str | None]:
    flags: list[IndicatorFlag] = []
    imitates = checks.lookalike_of(host)
    if checks.is_shortener(host):
        flags.append("shortener")
    if checks.is_punycode(host):
        flags.append("punycode")
    if imitates:
        flags.append("lookalike")
    return flags, imitates


def _from_url(raw: str, corridor_id: CorridorId | None) -> ScamIndicator | None:
    """The host of a link (never the path or query: they can carry tokens and ids). A link to a
    chat app names a person, not a website: it becomes that person's phone or handle."""
    text = _DEFANGED_DOT.sub(".", raw.strip()).replace("hxxp", "http")
    parts = urlsplit(text if "//" in text else f"//{text}")
    try:
        host = checks.normalise_host(parts.hostname or "")
    except ValueError:  # a port or bracket that does not parse
        return None
    if not host or "." not in host:
        return None
    if host in _TELEGRAM_HOSTS and (found := _HANDLE_PATH.match(parts.path)):
        return make_indicator("handle", found.group(1).lower())
    if host in _WHATSAPP_HOSTS:
        number = parts.path.strip("/") or "".join(parse_qs(parts.query).get("phone", []))
        if number.lstrip("+").isdigit():
            return _phone(f"+{number.lstrip('+')}", corridor_id)
    flags, imitates = _host_flags(host)
    return make_indicator("url", host, flags, imitates)


def _from_email(raw: str) -> ScamIndicator | None:
    address = raw.strip().lower()
    local, _, domain = address.partition("@")
    if not local or "." not in domain:
        return None  # an obfuscated "name (at) site (dot) com" is masked, but is not read here
    flags, imitates = _host_flags(checks.normalise_host(domain))
    # A shortener is not an email host: only the flags that mean a copy are kept.
    return make_indicator("email", address, [f for f in flags if f != "shortener"], imitates)


def _by_appearance(items: list[tuple[str, ScamIndicator]], raw_text: str) -> list[ScamIndicator]:
    """Distinct indicators in the order they appear in the message; at most ten, and when
    there are more, the flagged ones are kept first."""
    lowered = raw_text.lower()
    seen: dict[str, tuple[int, ScamIndicator]] = {}
    for original, indicator in items:
        position = lowered.find(original.lower())
        seen.setdefault(indicator.id, (position if position >= 0 else len(raw_text), indicator))
    ranked = sorted(seen.values(), key=lambda item: (not item[1].flags, item[0]))[:MAX_INDICATORS]
    return [indicator for _, indicator in sorted(ranked, key=lambda item: item[0])]


def extract_signals(
    raw_text: str, redacted_text: str, *, corridor_id: CorridorId | None
) -> Signals:
    """Find the links, phone numbers, emails, handles and amounts in a message.

    Args:
        raw_text: The message as received. The only place the values can be read: the redacted
            text has them masked. Nothing here is fetched, resolved or sent anywhere.
        redacted_text: The same message after `redact_text`; amounts and @handles are read from
            it, so a number long enough to be an account is not taken for an amount.
        corridor_id: The worker's route, to tell a number from an expected country from one that
            is not; None when not given.

    Returns:
        At most ten distinct indicators, each with the flags the fixed rules found.
    """
    found: list[tuple[str, ScamIndicator]] = []
    for masked in redact_values(raw_text):
        indicator = None
        if masked.token == "[URL]":
            indicator = _from_url(masked.value, corridor_id)
        elif masked.token == "[EMAIL]":
            indicator = _from_email(masked.value)
        elif masked.token == "[PHONE]":
            indicator = _phone(masked.value, corridor_id)
        if indicator is not None:
            found.append((masked.value, indicator))
    for handle in _HANDLE.findall(redacted_text):
        found.append((f"@{handle}", make_indicator("handle", handle.lower())))

    signals = Signals(_by_appearance(found, raw_text), find_amounts(redacted_text))
    # Counts and flags only: a value is the worker's own contact point (scam.md).
    logger.info(
        "scam_indicators kinds=%s flags=%s amounts=%d",
        sorted({i.kind for i in signals.indicators}),
        sorted({f for i in signals.indicators for f in i.flags}),
        len(signals.amounts),
    )
    return signals
