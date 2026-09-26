from __future__ import annotations

# English names for the six app languages. Prompts name the language in words ("Nepali"),
# which models follow more reliably than a bare code ("ne").
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "tl": "Tagalog (Filipino)",
    "id": "Indonesian (Bahasa Indonesia)",
    "ne": "Nepali",
    "bn": "Bengali (Bangla)",
}


def language_name(code: str) -> str:
    """English name of an app language code, for prompt templates.

    Raises:
        KeyError: The code is not one of the six app languages.
    """
    return LANGUAGE_NAMES[code]
