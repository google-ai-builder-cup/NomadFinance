"""What counts as the worker having said a number, a money or a period (NF-FC-010).

The extraction model reads a message; these checks decide, with plain rules and no model,
whether what it read was really *stated*. They are deliberately a little strict: when a cue is
not found the coach asks again, which costs the worker one more answer, whereas a guessed
currency or period would put a wrong figure into their plan. Languages: English, Hindi,
Tagalog, Indonesian, Nepali and Bengali, in their own script and in Latin letters.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

# Every digit of another script (Devanagari, Bengali) becomes 0 to 9 first.
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A thousands group is exactly three digits after a separator: 1.700, 1,700, 1,700,000.
_GROUPED = re.compile(r"^\d{1,3}(?:[.,]\d{3})+$")
# What a word in the message multiplies a number by: 50k, 5 thousand, 1.5 lakh, 12 juta, 2 crore.
# A factor counts only when its word is written, so "1 million" does not also read as "10 lakh".
_MAGNITUDES: dict[float, str] = {
    1e3: r"(?<=\d)\s?k\b|thousand|\bribu\b|\brb\b|\blibo\b|हज़ार|हजार|হাজার",
    1e5: r"\blakhs?\b|\blacs?\b|लाख|লাখ",
    1e6: r"million|\bjuta\b|\bjt\b|milyon|मिलियन|মিলিয়ন",
    1e7: r"crore|करोड़|करोड|কোটি",
    1e9: r"billion|miliar|\bmilyar\b|अरब|আরব",
}

_WORD_NUMBERS = {
    **{w: i for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen "
        "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()
    )},
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100,
}  # fmt: skip


# Small number words of the other five languages. Latin-letter Hindi ("do", "ek") is left out: "do"
# is an English word, and a number word that is also a common word would make every message read
# as holding a number.
def _numbered(words: str) -> dict[str, int]:
    """`words` are the names of 1, 2, 3 ... in order."""
    return {word: number for number, word in enumerate(words.split(), start=1)}


_WORD_NUMBERS.update(
    {
        **_numbered("isa dalawa tatlo apat lima anim pito walo siyam sampu"),
        "dalawang": 2,
        "tatlong": 3,
        **_numbered("satu dua tiga empat lima enam tujuh delapan sembilan sepuluh"),
        **_numbered("एक दो तीन चार पाँच छह सात आठ नौ दस"),
        "पांच": 5,
        "छः": 6,
        **_numbered("एक दुई तीन चार पाँच छ सात आठ नौ दश"),
        **_numbered("এক দুই তিন চার পাঁচ ছয় সাত আট নয় দশ"),
    }
)
_TOKENS = re.compile(r"[\s,.;:!?()\-\u2013\u2014\"'\u201c\u201d\u0964/]+")

_CURRENCY_CUES: dict[str, str] = {
    "SGD": r"singapore|singapura|singapur|सिंगापुर|সিঙ্গাপুর|\bsgd\b|\bs\$",
    "AUD": r"australia|ऑस्ट्रेलिया|অস্ট্রেলিয়া|\baud\b|\ba\$",
    "HKD": r"hong\s?kong|हांगकांग|হংকং|\bhkd\b|\bhk\$",
    "MYR": r"ringgit|रिंगिट|রিঙ্গিত|\bmyr\b|\brm\s?\d",
    "JPY": r"\byen\b|\bjpy\b|¥|円|येन|ইয়েন",
    "KRW": r"\bwon\b|\bkrw\b|₩|원|वॉन|ওন",
    "PHP": r"peso|piso\b|\bphp\b|₱|पेसो|পেসো",
    "INR": r"rupee|rupees|rupiya|rupaya|\binr\b|₹|रुपये|रुपया|रुपए|रुपयों|রুপি",
    "NPR": r"rupee|rupees|\bnpr\b|नेपाली रुपैयाँ|रुपैयाँ|रुपैया|रू\b",
    "IDR": r"rupiah|\bidr\b|\brp\.?\s?\d|रुपिया|রুপিয়া",
    "BDT": r"\btaka\b|\bbdt\b|৳|টাকা|टका",
}

_COUNTRY_CUES: dict[str, str] = {
    "SG": (
        r"singapore(?!\s+dollar)|singapura(?!\s+dolar)|singapur(?!\s+dolar)|"
        r"सिंगापुर(?!\s*डॉलर)|सिङ्गापुर(?!\s*डलर)|সিঙ্গাপুর(?!\s*ডলার)|\bsg\b"
    ),
    "KR": r"korea|कोरिया|কোরিয়া|seoul|서울|\bkr\b",
    "MY": r"malaysia|मलेशिया|मलेसिया|মালয়েশিয়া|kuala lumpur|\bmy\b",
    "JP": r"japan|jepang|जापान|জাপান|tokyo|osaka|\bjp\b",
    "HK": r"hong\s?kong|हांगकांग|हॉन्गकॉन्ग|हङकङ|হংকং|\bhk\b",
    "AU": (
        r"australia(?!n\s+dollar)|ऑस्ट्रेलिया(?!ई\s*डॉलर)|अस्ट्रेलिया(?!ली\s*डलर)|"
        r"অস্ট্রেলিয়া(?!ন\s*ডলার)|sydney|melbourne|perth|brisbane|\bau\b"
    ),
}

_PERIOD_CUES: dict[str, str] = {
    "month": (
        r"month|monthly|\bbuwan|buwanan|bulan|sebulan|bulanan|महीने|महीना|माह|महिना|"
        r"महिनामा|मासिक|মাস|মাসে|মাসিক|/mo\b"
    ),
    "week": (
        r"week|weekly|linggo|lingguhan|minggu|seminggu|mingguan|हफ़्ते|हफ्ते|हफ्ता|सप्ताह|"
        r"हप्ता|हप्तामा|সপ্তাহ|সপ্তাহে"
    ),
    "year": (
        r"year|yearly|annual|annum|\bp\.?a\.?\b|\btaon|taunan|tahun|setahun|tahunan|साल|वर्ष|"
        r"सालाना|वार्षिक|बर्ष|वर्षमा|বছর|বছরে|বার্ষিক"
    ),
}


def _each(texts: str | Iterable[str]) -> Iterable[str]:
    return (texts,) if isinstance(texts, str) else texts


def ascii_digits(text: str) -> str:
    """`text` with the digits of any script written as 0 to 9, and the text in normal form."""
    normal = unicodedata.normalize("NFKC", text)
    return "".join(
        str(unicodedata.decimal(ch)) if ch.isdecimal() and not ch.isascii() else ch for ch in normal
    )


def normal(text: str) -> str:
    """For comparing what the model quoted with what was written: case, spacing and form."""
    return " ".join(ascii_digits(text).casefold().split())


def numbers_in(text: str, *, words: bool = True) -> list[float]:
    """Every number written in `text`, each way it could be read.

    "1.700" is 1700 in Indonesian and 1.7 in English, and "1,5" is 1.5 or 15, so both readings
    are kept: the check only asks whether the model's number is one of them.
    """
    found: list[float] = []
    for token in _NUMBER.findall(ascii_digits(text)):
        readings = {token}
        if _GROUPED.match(token):
            readings.add(re.sub(r"[.,]", "", token))
        readings.add(token.replace(",", "."))
        readings.add(token.replace(".", "").replace(",", "."))
        for reading in readings:
            try:
                found.append(float(reading))
            except ValueError:
                continue
    if words:
        found.extend(float(_WORD_NUMBERS[w]) for w in _tokens(text) if w in _WORD_NUMBERS)
    return found


_ZERO_WORDS = re.compile(
    r"\b(?:zero|no|not|none|nothing|nil|never|without|wala|walang|hindi|tidak|tak|belum|nol|"
    r"nahi|nahin)\b|नहीं|नही|शून्य|छैन|नभएको|শূন্য|নেই|কিছু নেই"
)


def zero_stated(text: str) -> bool:
    """Whether `text` says there is nothing: a 0, or a word for none or no in the six languages."""
    return number_stated(0, text) or bool(_ZERO_WORDS.search(normal(text)))


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKENS.split(text.casefold()) if t]


def has_digits(text: str) -> bool:
    return bool(_NUMBER.search(ascii_digits(text))) or any(
        w in _WORD_NUMBERS for w in _tokens(text)
    )


def number_stated(value: float, text: str) -> bool:
    """Whether `value` is a number of `text`, times a magnitude word written beside it, if any."""
    shown = normal(text)
    factors = [1.0] + [f for f, words in _MAGNITUDES.items() if re.search(words, shown)]
    return any(
        abs(value - number * factor) <= 1e-6 * max(1.0, abs(value))
        for number in numbers_in(text)
        for factor in factors
    )


def currency_stated(code: str, texts: str | Iterable[str]) -> bool:
    """Whether the worker named the money `code` in any of `texts` (word, symbol or code)."""
    pattern = _CURRENCY_CUES.get(code)
    return pattern is not None and any(re.search(pattern, normal(t)) for t in _each(texts))


def period_stated(period: str, texts: str | Iterable[str]) -> bool:
    """Whether the worker said `period` (month, week or year) in any of `texts`."""
    pattern = _PERIOD_CUES.get(period)
    return pattern is not None and any(re.search(pattern, normal(t)) for t in _each(texts))


def country_stated(code: str, texts: str | Iterable[str]) -> bool:
    """Whether the worker named the country `code` (by name, city or code) in any of `texts`."""
    pattern = _COUNTRY_CUES.get(code)
    return pattern is not None and any(re.search(pattern, normal(t)) for t in _each(texts))


_PERCENT = re.compile(
    r"%|per\s?cent|percent|persen|porsiyento|prosyento|प्रतिशत|फीसदी|फ़ीसदी|प्रतिसत|शतांश|"
    r"শতাংশ|পার্সেন্ট|\binterest\b|\bbunga\b|\btubo\b|ब्याज|ब्याज|সুদ"
)


def percent_stated(text: str) -> bool:
    """Whether `text` talks of a percent or an interest."""
    return bool(_PERCENT.search(normal(text)))


def money_named(text: str) -> bool:
    """Whether `text` names any money."""
    return any(currency_stated(code, text) for code in _CURRENCY_CUES)
