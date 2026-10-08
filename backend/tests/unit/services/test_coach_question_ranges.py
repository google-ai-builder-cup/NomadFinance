"""The Coach's expected ranges (NF-FC-001): what `range_issue` calls worth asking again."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

import pytest

from app.schemas.coach_profile import SlotName, parse_slot_value
from app.schemas.coach_questions import QuestionBank
from app.services.coach.question_bank import load_question_bank, range_issue
from tests.fixtures.coach_bank import TODAY, money


@pytest.fixture(scope="module")
def bank() -> QuestionBank:
    return load_question_bank()


class TestExpectedRanges:
    @pytest.mark.parametrize(
        ("amount", "currency", "period", "issue"),
        [
            (4200, "AUD", "month", None),
            (1200, "SGD", "month", None),
            (600, "SGD", "month", None),
            (2_100_000, "KRW", "month", None),
            (160_000, "JPY", "month", None),
            (14_400, "SGD", "year", None),
            (1200, "SGD", "week", None),
            (100, "SGD", "month", "too_low"),
            (120_000, "SGD", "month", "too_high"),
            (10_000, "SGD", "week", "too_high"),
            # A yearly figure marked "per month": the slip the range exists to catch.
            (50_400, "AUD", "month", "too_high"),
            (375, "SGD", "month", None),
            (374, "SGD", "month", "too_low"),
            (7500, "SGD", "month", None),
            (7501, "SGD", "month", "too_high"),
        ],
    )
    def test_the_salary_is_compared_per_month_in_its_own_currency(
        self, bank: QuestionBank, amount: float, currency: str, period: str, issue: str | None
    ) -> None:
        value = money(amount, currency, period)

        assert range_issue(bank, "monthly_salary", value, TODAY) == issue

    @pytest.mark.parametrize(
        ("slot", "amount", "issue"),
        [
            ("remittance_target", 0, None),
            ("remittance_target", 350, None),
            ("remittance_target", 40_000, "too_high"),
            ("savings", 0, None),
            ("savings", 30_000, None),
            ("savings", 1_000_000, "too_high"),
            ("recruitment_fee_paid", 0, None),
            ("recruitment_fee_paid", 6000, None),
            ("recruitment_fee_paid", 500_000, "too_high"),
            ("debt_outstanding", 0, None),
            ("debt_outstanding", 18_000, None),
            ("debt_outstanding", 18_001, "too_high"),
        ],
    )
    def test_other_amounts_use_their_own_multiple_of_the_scale(
        self, bank: QuestionBank, slot: SlotName, amount: float, issue: str | None
    ) -> None:
        period = "month" if slot == "remittance_target" else "once"
        value = parse_slot_value(slot, {"amount": amount, "currency": "SGD", "period": period})

        assert range_issue(bank, slot, value, TODAY) == issue

    def test_a_fee_in_the_home_currency_is_judged_against_that_currency(
        self, bank: QuestionBank
    ) -> None:
        npr = parse_slot_value(
            "recruitment_fee_paid", {"amount": 120_000, "currency": "NPR", "period": "once"}
        )
        sgd = parse_slot_value(
            "recruitment_fee_paid", {"amount": 120_000, "currency": "SGD", "period": "once"}
        )

        assert range_issue(bank, "recruitment_fee_paid", npr, TODAY) is None
        assert range_issue(bank, "recruitment_fee_paid", sgd, TODAY) == "too_high"

    @pytest.mark.parametrize(
        ("count", "issue"), [(0, None), (4, None), (10, None), (11, "too_high")]
    )
    def test_dependents_up_to_ten_are_usual(
        self, bank: QuestionBank, count: int, issue: str | None
    ) -> None:
        assert range_issue(bank, "dependents", count, TODAY) == issue

    @pytest.mark.parametrize(
        ("rate", "period", "issue"),
        [
            (0, "month", None),
            (5, "month", None),
            (20, "month", None),
            (25, "month", "too_high"),
            (60, "year", None),
            (240, "year", None),
            (300, "year", "too_high"),
        ],
    )
    def test_interest_is_compared_for_the_period_it_was_given(
        self, bank: QuestionBank, rate: float, period: str, issue: str | None
    ) -> None:
        value = parse_slot_value("debt_interest", {"rate_percent": rate, "period": period})

        assert range_issue(bank, "debt_interest", value, TODAY) == issue

    @pytest.mark.parametrize(
        ("days", "issue"),
        [
            (-31, "too_low"),
            (-30, None),
            (-7, None),
            (0, None),
            (60, None),
            (730, None),
            (731, "too_high"),
        ],
    )
    def test_the_departure_date_is_compared_with_the_day_given_not_the_clock(
        self, bank: QuestionBank, days: int, issue: str | None
    ) -> None:
        value = (TODAY + timedelta(days=days)).isoformat()

        assert range_issue(bank, "departure_date", value, TODAY) == issue

    def test_a_choice_has_no_range(self, bank: QuestionBank) -> None:
        assert range_issue(bank, "destination_country", "SG", TODAY) is None
        assert range_issue(bank, "bank_or_wallet", "none", TODAY) is None

    @pytest.mark.parametrize(
        ("slot", "value"),
        [
            ("dependents", True),
            ("dependents", "3"),
            ("dependents", 2.5),
            ("monthly_salary", 4200),
            ("debt_interest", 5),
            ("departure_date", 20261201),
        ],
    )
    def test_a_value_of_the_wrong_kind_is_a_programming_error(
        self, bank: QuestionBank, slot: SlotName, value: object
    ) -> None:
        with pytest.raises(TypeError):
            range_issue(bank, slot, value, TODAY)

    def test_a_slot_that_does_not_exist_is_an_error(self, bank: QuestionBank) -> None:
        with pytest.raises(KeyError):
            range_issue(bank, cast(SlotName, "favourite_colour"), 1, TODAY)

    def test_the_hard_limits_of_the_profile_sit_outside_the_expected_ranges(
        self, bank: QuestionBank
    ) -> None:
        # Something the coach asks about again must still be storable once the worker confirms.
        value = parse_slot_value("dependents", 15)

        assert range_issue(bank, "dependents", value, TODAY) == "too_high"
