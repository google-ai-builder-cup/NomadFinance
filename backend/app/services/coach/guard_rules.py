"""The rule layer of the Coach guard: no model, no I/O (NF-FC-013).

`screen` reads one worker message and either decides (refer, redirect, or let an ordinary answer
through) or says it cannot (`None`), and then the classifier in `guard.py` decides. Distress is
checked first, then orders to the coach, then requests for a financial product, then the shape of
an answer. Messages are folded first (`views`), so a fullwidth letter, a zero-width mark, a digit
standing for a letter or a word spelled with dots does not hide a cue.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from app.services.coach.extraction_cues import ascii_digits, has_digits
from app.services.coach.guard_answers import (
    ACK_PHRASES,
    ACK_WORDS,
    ANSWER_WORDS,
    COUNTRY_WORDS,
    WEAK_SIGNALS,
)
from app.services.coach.guard_cues import (
    DISTRESS,
    INJECTION,
    PRODUCT_REQUEST,
    REPLY_ADVICE,
    SQUEEZED_ORDERS,
)
from app.services.coach.guard_types import GuardDecision

# Longer than this is not the short answer the shortcut is for; it goes to the classifier.
MAX_ANSWER_CHARS = 200
# What a message with a hidden order may look like after the model sees it in the history.
MASKED_MESSAGE = "(a message removed by the safety check)"

_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_WORDS = re.compile(r"[\s,.;:!?()\[\]{}<>\-–—\"“”'/।|]+")
# A long run of letters and digits with no space is an encoded payload, not an answer.
_BLOB = re.compile(r"[A-Za-z0-9+/_=-]{40,}")
_CLOSING_TAG = re.compile(r"<\s*/\s*(worker_message|summary_of_earlier_talk|recent_talk)", re.I)
# A web link or an e-mail address. The coach never gives one (the screens link where a worker
# should go), so one in a reply came from an attack, and a worker would follow it.
_LINK = re.compile(r"\b(?:https?|ftp)://|\bwww\.|[\w.+-]+@[\w-]+\.[\w.-]+", re.I)


def _compile(patterns: Iterable[str]) -> re.Pattern[str]:
    # The text is folded to NFKC, so the patterns are too (a nukta is one letter either way).
    return re.compile("|".join(f"(?:{unicodedata.normalize('NFKC', p)})" for p in patterns))


_INJECTION = _compile(INJECTION)
_DISTRESS = _compile(DISTRESS)
_PRODUCT_REQUEST = _compile(PRODUCT_REQUEST)
_REPLY_ADVICE = _compile(REPLY_ADVICE)


@dataclass(frozen=True)
class Views:
    """One message folded three ways: as written, with look-alike digits read as letters, and with
    everything but letters and digits taken out."""

    plain: str
    leet: str
    squeezed: str


def views(text: str) -> Views:
    visible = "".join(
        ch for ch in unicodedata.normalize("NFKC", text) if unicodedata.category(ch) != "Cf"
    )
    plain = " ".join(ascii_digits(visible).replace("’", "'").casefold().split())
    leet = plain.translate(_LEET)
    return Views(plain, leet, re.sub(r"[^a-z0-9]+", "", leet))


def _gives_orders(seen: Views) -> bool:
    return bool(
        _INJECTION.search(seen.plain)
        or _INJECTION.search(seen.leet)
        or any(order in seen.squeezed for order in SQUEEZED_ORDERS)
    )


def is_attack(text: str) -> bool:
    """Whether the message gives the coach orders, by the rules alone."""
    return _gives_orders(views(text))


def visible_to_model(role: str, text: str) -> str:
    """A stored message as a later prompt may show it: a worker message that gave orders is
    replaced, so an attack made once cannot keep working from the history."""
    return MASKED_MESSAGE if role == "user" and is_attack(text) else text


def fence(text: str) -> str:
    """`text` with any closing tag of a data section broken, so it cannot end the section early."""
    return _CLOSING_TAG.sub(lambda match: f"< /{match.group(1).lower()}", text)


def contains_link(reply: str) -> bool:
    """Whether a coach reply holds a web link or an e-mail address."""
    return bool(_LINK.search(unicodedata.normalize("NFKC", reply)))


def recommends_product(reply: str) -> bool:
    """Whether a coach reply recommends a loan, an investment or an app."""
    return bool(_REPLY_ADVICE.search(views(reply).plain))


def _answer_shaped(seen: Views, original: str) -> bool:
    plain = seen.plain
    if len(plain) > MAX_ANSWER_CHARS or _BLOB.search(original) or WEAK_SIGNALS.search(plain):
        return False
    words = [word for word in _WORDS.split(plain) if word]
    if (
        has_digits(plain)
        or COUNTRY_WORDS.search(plain)
        or any(word in ANSWER_WORDS for word in words)
    ):
        return True
    return len(words) <= 4 and (
        any(word in ACK_WORDS for word in words) or any(phrase in plain for phrase in ACK_PHRASES)
    )


def screen(text: str) -> GuardDecision | None:
    """The decision the rules can make for `text`, or `None` when they cannot."""
    seen = views(text)
    if _DISTRESS.search(seen.plain):
        return GuardDecision("refer", "distress_cue")
    if _gives_orders(seen):
        return GuardDecision("redirect", "injection_cue")
    if _PRODUCT_REQUEST.search(seen.plain):
        return GuardDecision("redirect", "product_request_cue")
    if _answer_shaped(seen, text):
        return GuardDecision("allow", "answer_shaped")
    return None
