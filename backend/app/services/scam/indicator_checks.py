"""The fixed rules behind an indicator's flags (NF-SA-011): no model, and **no network**.

A link found in a scam message is never fetched, resolved or opened: not by a request, not by a
DNS lookup. Everything here works on the text of the host name alone, so the worst a hostile link
can do is be flagged. The curated lists are in `indicator_data.json`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.utils.corridors import CORRIDOR_HOST_HOME

_DATA_FILE = Path(__file__).with_name("indicator_data.json")
_DOMAIN = re.compile(r"^[a-z0-9]([a-z0-9\-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9\-]*[a-z0-9])?)+$")

# Calling codes of the six host countries and the home countries of the corridors, plus Nepal
# and Bangladesh (onboarding offers both and neither is a corridor). A number from any other
# country, in a message about a job or a bank, is worth a flag.
COUNTRY_CODES: dict[str, str] = {
    "SG": "65", "IN": "91", "AU": "61", "MY": "60", "ID": "62", "JP": "81", "PH": "63",
    "HK": "852", "KR": "82", "NP": "977", "BD": "880",
}  # fmt: skip

# Hosts under these are registered only to the governments they name, so a host that merely
# looks like a listed ministry but sits under the same suffix is another real office, not a copy
# (`moe.gov.sg` is not a lookalike of `mom.gov.sg`).
_GOVERNMENT_SUFFIXES = (
    ".gov.sg", ".gov.au", ".gov.in", ".gov.ph", ".gov.my", ".go.id", ".go.jp",
)  # fmt: skip

# Written to look like letters, the way a copy of a bank's address is: "dbs" as "d8s".
_HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "8": "b"})
_MULTI_GLYPHS = (("rn", "m"), ("vv", "w"))


@dataclass(frozen=True)
class Protected:
    """A real organisation's official domain, which a scam may imitate."""

    domain: str
    org: str
    brand: str | None


@dataclass(frozen=True)
class IndicatorData:
    shorteners: frozenset[str]
    protected: tuple[Protected, ...]


@lru_cache(maxsize=1)
def load_data() -> IndicatorData:
    """Read and check the curated lists once; a bad entry stops the app at startup."""
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    shorteners = frozenset(raw["shorteners"])
    protected = tuple(
        Protected(item["domain"], item["org"], item.get("brand")) for item in raw["protected"]
    )
    for domain in (*shorteners, *(p.domain for p in protected)):
        if not _DOMAIN.match(domain):
            raise ValueError(f"indicator_data.json: {domain!r} is not a lowercase domain")
    if len({p.domain for p in protected}) != len(protected):
        raise ValueError("indicator_data.json: a protected domain is listed twice")
    return IndicatorData(shorteners, protected)


def normalise_host(host: str) -> str:
    """Lowercase, no trailing dot, no leading `www.`, written in ASCII (punycode)."""
    cleaned = host.strip().strip(".").lower().removeprefix("www.")
    try:
        return cleaned.encode("idna").decode("ascii")
    except UnicodeError:
        return cleaned  # a label too long or empty for IDNA: keep the text, it is still checked


def _is_or_under(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def is_shortener(host: str) -> bool:
    return any(_is_or_under(host, short) for short in load_data().shorteners)


def is_punycode(host: str) -> bool:
    """An address that uses `xn--` labels: other alphabets in the name, a classic way to make
    one that reads like another."""
    return any(label.startswith("xn--") for label in host.split("."))


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).translate(_HOMOGLYPHS)
    for glyphs, letter in _MULTI_GLYPHS:
        text = text.replace(glyphs, letter)
    return text


def _distance(a: str, b: str) -> int:
    """Edit distance (insert, delete, replace): hosts are short, so the plain table is enough."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        row = [i]
        for j, cb in enumerate(b, start=1):
            row.append(min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = row
    return previous[-1]


def _tokens(host: str) -> list[str]:
    return [t for t in re.split(r"[.\-]", host) if t]


def _contains_run(tokens: list[str], run: list[str]) -> int:
    """Index where `run` starts inside `tokens`, or -1."""
    for start in range(len(tokens) - len(run) + 1):
        if tokens[start : start + len(run)] == run:
            return start
    return -1


def lookalike_of(host: str) -> str | None:
    """The real domain `host` imitates, or None.

    A host that is a listed domain, or under one, is the real thing. Otherwise it imitates one
    when it (a) repeats the real name inside a longer one (`mom.gov.sg.verify-now.com`,
    `dbs-com-sg.net`), (b) is one letter or look-alike character away from it (`singpas.gov.sg`,
    `d8s.com.sg`), or (c) wraps a distinctive brand in other words (`gcash-promo.xyz`).
    """
    data = load_data()
    if any(_is_or_under(host, p.domain) for p in data.protected):
        return None
    if host.endswith(_GOVERNMENT_SUFFIXES):
        return None
    folded = _fold(host)
    tokens = _tokens(folded)
    for p in data.protected:
        real_tokens = _tokens(_fold(p.domain))
        start = _contains_run(tokens, real_tokens)
        # A short name found in the middle of a host is too often a coincidence ("i-wise.com.au").
        if start == 0 or (start > 0 and len(real_tokens) >= 3):
            return p.domain
        allowed = 2 if len(p.domain) >= 14 else 1 if len(p.domain) >= 8 else 0
        if _distance(folded, _fold(p.domain)) <= allowed:
            return p.domain
        if p.brand and any(p.brand in label for label in re.split(r"[.]", folded)):
            return p.domain
    return None


# Premium-rate numbers: only the ranges a regulator publishes. Singapore's 1900 (IMDA national
# numbering plan: 11 digits), Australia's 190 (ACMA numbering plan: 190X XXX XXX) and the ITU's
# international premium rate range +979. A country not listed is not "safe": it is not covered.
_PREMIUM = (
    re.compile(r"^(?:65)?1900\d{7}$"),
    re.compile(r"^190\d{6,7}$"),
    re.compile(r"^979\d{8,12}$"),
)


def is_premium_rate(digits: str, international: bool) -> bool:
    """`digits`: the number with no `+`, spaces or dashes; `international` if it had a `+`/`00`."""
    candidates = _PREMIUM if international else _PREMIUM[:2]
    return any(pattern.match(digits) for pattern in candidates)


def expected_codes(corridor_id: str | None) -> tuple[str, ...]:
    """Calling codes a message to this worker may reasonably come from: the corridor's own two
    countries, or all of the project's when the route is not known."""
    pair = CORRIDOR_HOST_HOME.get(corridor_id or "")
    if pair is None:
        return tuple(COUNTRY_CODES.values())
    return tuple(COUNTRY_CODES[country] for country in pair)


def is_unexpected_country(digits: str, international: bool, corridor_id: str | None) -> bool:
    """A number with a country code from outside the worker's route. A number written without
    one has no country to judge."""
    return international and not digits.startswith(expected_codes(corridor_id))
