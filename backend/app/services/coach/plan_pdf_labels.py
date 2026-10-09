"""Fixed wording of the plan PDF, by language (NF-FC-014)."""

from __future__ import annotations

from typing import Final

from app.services.coach.plan_pdf_labels_indic import INDIC
from app.services.coach.plan_pdf_labels_latin import LATIN

LABELS: Final[dict[str, dict[str, str]]] = {**LATIN, **INDIC}


def label(language: str, key: str) -> str:
    """The wording of `key` in `language`; English if the language has no such entry."""
    return LABELS.get(language, LABELS["en"]).get(key) or LABELS["en"][key]


def named(language: str, prefix: str, ident: str) -> str:
    """The name of a cost, goal or factor by id (`cost_food`); an id the PDF does not know is
    shown as its words, so a new id in a plan never breaks the page."""
    key = f"{prefix}_{ident}"
    if key in LABELS["en"]:
        return label(language, key)
    return ident.replace("_", " ").capitalize()
