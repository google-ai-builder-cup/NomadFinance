from __future__ import annotations

import json
import logging
import random
import re
import time

import pytest

from app.core.logging import JsonFormatter
from app.core.redact import ACCOUNT, EMAIL, ID_NUMBER, PHONE, URL, redact, redact_text
from tests.fixtures.pii_redaction_cases import CLEAN_CASES, PII_CASES

TOKENS = (PHONE, EMAIL, ID_NUMBER, ACCOUNT, URL)


def _leaked(value: str, redacted: str) -> bool:
    """Whether a personal value, or the last four digits of a long number, is still visible."""
    if value in redacted:
        return True
    digits = re.sub(r"\D", "", value)
    return len(digits) >= 6 and digits[-4:] in re.sub(r"[ -]", "", redacted)


def test_fixture_has_sixty_cases() -> None:
    assert len(PII_CASES) == 60


def test_recall_on_the_fixture_is_at_least_95_percent() -> None:
    values = [(text, value) for text, found in PII_CASES for value in found]
    missed = [(text, value) for text, value in values if _leaked(value, redact_text(text))]

    recall = 1 - len(missed) / len(values)

    assert recall >= 0.95, f"recall {recall:.1%}, missed: {missed}"


@pytest.mark.parametrize("text", [text for text, _ in PII_CASES])
def test_every_fixture_case_is_idempotent(text: str) -> None:
    once = redact_text(text)

    assert redact_text(once) == once


def test_idempotent_on_messages_stitched_together_at_random() -> None:
    rng = random.Random(8)
    texts = [text for text, _ in PII_CASES] + CLEAN_CASES
    for _ in range(300):
        joined = rng.choice([" ", "\n", " - ", ", ", ""]).join(rng.sample(texts, 3))
        once = redact_text(joined)
        assert redact_text(once) == once


@pytest.mark.parametrize("text", CLEAN_CASES)
def test_amounts_dates_and_plain_numbers_are_left_alone(text: str) -> None:
    result = redact(text)

    assert result.text == text
    assert not result.found


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("call +65 9123 4567", f"call {PHONE}"),
        ("call 0917 123 4567", f"call {PHONE}"),
        ("call 98765 43210", f"call {PHONE}"),
        ("mail a.b@example.com now", f"mail {EMAIL} now"),
        ("mail a [at] example [dot] com", f"mail {EMAIL}"),
        ("NRIC S1234567D", f"NRIC {ID_NUMBER}"),
        ("PAN ABCDE1234F", f"PAN {ID_NUMBER}"),
        ("Aadhaar 2345 6789 0123", f"Aadhaar {ID_NUMBER}"),
        ("passport number: 12345678", f"passport number: {ID_NUMBER}"),
        ("account 012-345-678-9", f"account {ACCOUNT}"),
        ("pay 123-456-789-0 now", f"pay {ACCOUNT} now"),
        ("card 4111 1111 1111 1111", f"card {ACCOUNT}"),
        ("UPI rahul@okaxis", f"UPI {ACCOUNT}"),
        ("open https://evil.top/a?b=1.", f"open {URL}."),
        ("open (https://evil.top/a)", f"open ({URL})"),
        ("open bit.ly/abc", f"open {URL}"),
        ("open www.evil.com", f"open {URL}"),
    ],
)
def test_each_kind_gets_its_own_token_and_keeps_the_surrounding_text(
    text: str, expected: str
) -> None:
    assert redact_text(text) == expected


def test_devanagari_and_bengali_digits_are_recognised() -> None:
    assert redact_text("फोन ९८७६५ ४३२१०") == f"फोन {PHONE}"
    assert redact_text("নম্বর ০১৭১২৩৪৫৬৭৮") == f"নম্বর {PHONE}"


def test_email_inside_a_url_does_not_leave_a_stray_bracket() -> None:
    assert redact_text("go to https://x.com/?e=a@b.com.") == f"go to {URL}."


def test_counts_hold_kinds_and_numbers_never_values() -> None:
    result = redact("Call +65 9123 4567 or +65 8123 4567, mail a@b.com, see https://x.top")

    assert result.counts == {PHONE: 2, EMAIL: 1, URL: 1}
    assert result.found
    assert "9123" not in json.dumps(dict(result.counts))


def test_text_without_personal_data_is_returned_unchanged() -> None:
    result = redact("Nothing to see here.")

    assert result.text == "Nothing to see here."
    assert result.counts == {}
    assert redact_text("") == ""


def test_masks_survive_into_a_json_log_line() -> None:
    # What a caller does before logging a submitted message: redact, then log the result.
    message = "Scam text: WhatsApp +65 9123 4567, pay 012-345-678-9, mail a@b.com"
    record = logging.LogRecord(
        "t", logging.INFO, "f.py", 1, "check %s", (redact_text(message),), None
    )

    line = JsonFormatter("proj").format(record)

    for raw in ("9123 4567", "012-345-678-9", "a@b.com"):
        assert raw not in line
    assert PHONE in line


@pytest.mark.parametrize(
    "text",
    ["a" * 50_000, "1 " * 20_000, "a." * 20_000, "0" * 30_000, "call 12 " * 8_000],
    ids=["letters", "spaced-digits", "dotted-letters", "zeros", "call-groups"],
)
def test_long_inputs_are_not_quadratic(text: str) -> None:
    # A regression here turned a 50 KB run of letters into 40 seconds; healthy is ~0.05 s.
    started = time.perf_counter()

    redact_text(text)

    assert time.perf_counter() - started < 3
