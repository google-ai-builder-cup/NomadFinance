"""The words of a Coach check-in reminder, in the six languages (NF-FC-016).

Fixed here, not written by a model: the text has one moving part (the day), so a model call would
cost money and add a way to fail for nothing. `{days}` is 30, 60 or 90, always in digits 0 to 9.

Short sentences of everyday words, for a worker who reads the language as a second one. Written
by the team, not read by native speakers yet (deferred item D-230). Keyed by plain strings because
the language comes from a stored profile; a test holds the keys to the six app languages.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "en"


def _say(*sentences: str) -> str:
    return " ".join(sentences)


TITLE: dict[str, str] = {
    "en": "Day {days} check-in",
    "hi": "दिन {days} की जाँच",
    "tl": "Check-in sa ika-{days} araw",
    "id": "Cek hari ke-{days}",
    "ne": "दिन {days} को जाँच",
    "bn": "{days} দিনের চেক-ইন",
}

BODY: dict[str, str] = {
    "en": _say(
        "It is {days} days since you left.",
        "Answer 3 short questions on how your money plan is going.",
    ),
    "hi": _say(
        "आपको गए {days} दिन हो गए हैं।",
        "अपनी पैसों की योजना कैसी चल रही है, इस पर 3 छोटे सवालों के जवाब दें।",
    ),
    "tl": _say(
        "{days} araw na mula nang umalis ka.",
        "Sagutin ang 3 maikling tanong kung kumusta ang plano mo sa pera.",
    ),
    "id": _say(
        "Sudah {days} hari sejak Anda berangkat.",
        "Jawab 3 pertanyaan singkat tentang rencana uang Anda.",
    ),
    "ne": _say(
        "तपाईं गएको {days} दिन भयो।",
        "पैसाको योजना कस्तो चल्दैछ भनेर 3 वटा छोटा प्रश्नको जवाफ दिनुहोस्।",
    ),
    "bn": _say(
        "আপনি রওনা হওয়ার পর {days} দিন হয়ে গেছে।",
        "আপনার টাকার পরিকল্পনা কেমন চলছে, সে বিষয়ে 3টি ছোট প্রশ্নের উত্তর দিন।",
    ),
}


def reminder_language(stored: object) -> str:
    """The language a reminder is written in: the profile's, or English if it is missing or odd.

    The reminder matters more than its wording, so an unknown value never stops it.
    """
    return stored if isinstance(stored, str) and stored in TITLE else DEFAULT_LANGUAGE


def checkin_text(language: str, days: int) -> tuple[str, str]:
    """The title and body, in a language from `reminder_language`, for `days` after departure."""
    return TITLE[language].format(days=days), BODY[language].format(days=days)
