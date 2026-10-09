"""The sentences the Coach screen's helpers send are ones the server's word lists can read
(NF-FC-023, closes the check D-236 left to be run by hand).

A worker taps a currency, types an amount and presses Send; the screen writes "4200 AUD per
month" in the language of the app, and the server reads it again (`extraction_cues.py`). If a
translation of `input.compose.*`, `input.none` or `input.country.*` loses a word the readers look
for, the coach would ask the question again and the worker would lose a turn. This reads the six
real files of the frontend, so a change to a translation is checked the day it is made.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.schemas.coach_profile import Currency
from app.services.coach import extraction_cues as cues
from app.services.coach.guard_answers import COUNTRY_WORDS

LANGUAGES = ["en", "hi", "tl", "id", "ne", "bn"]
COACH_STRINGS = Path(__file__).resolve().parents[4] / "frontend" / "src" / "i18n" / "coach"
CURRENCIES = list(Currency.__args__)  # type: ignore[attr-defined]


def _input(language: str) -> dict[str, Any]:
    strings: dict[str, Any] = json.loads(
        (COACH_STRINGS / f"{language}.json").read_text(encoding="utf-8")
    )
    section: dict[str, Any] = strings["input"]
    return section


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("period", ["month", "week", "year"])
def test_an_amount_with_its_currency_and_period_is_read_in_every_language(
    language: str, period: str
) -> None:
    template = _input(language)["compose"][period]
    unread = []
    for currency in CURRENCIES:
        text = template.replace("{{amount}}", "4200").replace("{{currency}}", currency)
        if not (
            cues.number_stated(4200, text)
            and cues.currency_stated(currency, text)
            and cues.period_stated(period, text)
        ):
            unread.append(text)

    assert unread == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_total_with_no_period_still_names_the_amount_and_the_currency(language: str) -> None:
    template = _input(language)["compose"]["once"]
    unread = []
    for currency in CURRENCIES:
        text = template.replace("{{amount}}", "120000").replace("{{currency}}", currency)
        if not (cues.number_stated(120000, text) and cues.currency_stated(currency, text)):
            unread.append(text)

    assert unread == []


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("period", ["month", "year"])
def test_an_interest_rate_is_read_as_a_number_a_percent_and_a_period(
    language: str, period: str
) -> None:
    text = _input(language)["compose"]["interest"][period].replace("{{rate}}", "3")

    assert cues.number_stated(3, text), text
    assert cues.percent_stated(text), text
    assert cues.period_stated(period, text), text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_none_answer_is_read_as_a_zero(language: str) -> None:
    assert cues.zero_stated(_input(language)["none"])


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_country_chip_names_its_own_country(language: str) -> None:
    countries: dict[str, str] = _input(language)["country"]

    assert set(countries) == {"SG", "KR", "MY", "JP", "HK", "AU"}
    for code, label in countries.items():
        assert cues.country_stated(code, label), (code, label)
        assert COUNTRY_WORDS.search(label.casefold()), (code, label)


def test_the_check_can_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """A template that lost its currency is caught, so a passing run means something."""
    template = "{{amount}} per month"

    text = template.replace("{{amount}}", "4200").replace("{{currency}}", "AUD")

    assert not cues.currency_stated("AUD", text)
