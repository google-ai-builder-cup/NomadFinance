from __future__ import annotations

import pytest

from app.services.scam.amounts import MAX_AMOUNTS, find_amounts, parse_number


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("800", 800.0),
        ("1,800", 1800.0),  # a comma and three digits: thousands
        ("1.800", 1800.0),  # Indonesian writing
        ("5 000", 5000.0),
        ("50,000.00", 50000.0),
        ("1.234,56", 1234.56),
        ("12.5", 12.5),
        ("12,50", 12.5),
        ("1,234,567", 1234567.0),
        ("1.234.567", 1234567.0),
        ("1 800,50", 1800.5),
    ],
)
def test_numbers_as_written_in_the_corridors(raw: str, value: float) -> None:
    assert parse_number(raw) == value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Pay SGD 800 today", [(800.0, "SGD")]),
        ("Pay 800 SGD today", [(800.0, "SGD")]),
        ("Pay sgd800 today", [(800.0, "SGD")]),
        ("Send S$1,200 now", [(1200.0, "SGD")]),
        ("Bayar RM 1,500 sekarang", [(1500.0, "MYR")]),
        ("Transfer Rp 5.000.000 hari ini", [(5000000.0, "IDR")]),
        ("Bayad ₱ 2,500 ngayon", [(2500.0, "PHP")]),
        ("Pay 4 500 yen", [(4500.0, "JPY")]),
        ("手数料は 3000円 です", [(3000.0, "JPY")]),
        ("Send ₹ 15,000 to the agent", [(15000.0, "INR")]),
        ("Pay A$ 900 and HK$ 300", [(900.0, "AUD"), (300.0, "HKD")]),
        ("5.000 rupiah sekarang", [(5000.0, "IDR")]),
        ("भेजें INR ५,००० अभी", [(5000.0, "INR")]),
        ("Pay SGD 800 and 800 SGD", [(800.0, "SGD")]),  # the same amount twice is one
        ("Pay SGD 800 or MYR 800", [(800.0, "SGD"), (800.0, "MYR")]),
    ],
)
def test_an_amount_next_to_a_known_currency(text: str, expected: list[tuple[float, str]]) -> None:
    assert [(a.amount, a.currency) for a in find_amounts(text)] == expected


@pytest.mark.parametrize(
    "text",
    [
        "Call 800 now",  # no currency
        "In 2026 at 9 am, room 800",  # a year, a time and a number
        "Pay $800 now",  # "$" alone is several currencies
        "Pay Rs 500 now",  # "Rs" is rupees of more than one country
        "Pay SGD 0 now",  # zero is not an amount
        "XYZ 800",  # not a currency the project works with
        "",
    ],
)
def test_what_is_not_an_amount_is_left_out(text: str) -> None:
    assert find_amounts(text) == []


def test_at_most_five_amounts_in_the_order_they_appear() -> None:
    text = " ".join(f"SGD {n}00" for n in range(1, 9))

    found = find_amounts(text)

    assert len(found) == MAX_AMOUNTS == 5
    assert [a.amount for a in found] == [100.0, 200.0, 300.0, 400.0, 500.0]


def test_the_amounts_are_read_from_the_masked_text_so_an_account_number_is_not_one() -> None:
    from app.core.redact import redact_text
    from app.services.scam.indicators import extract_signals

    text = "Pay SGD 800 to account 123456789012 or IDR 5000000000000"
    redacted = redact_text(text)

    amounts = extract_signals(text, redacted, corridor_id=None).amounts

    assert [(a.amount, a.currency) for a in amounts][0] == (800.0, "SGD")
