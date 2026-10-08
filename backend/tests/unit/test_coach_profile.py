"""The Coach's slot schema (NF-FC-001): what `CoachProfile` accepts and what it refuses."""

from __future__ import annotations

from datetime import date
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from app.schemas.coach_profile import (
    SLOT_NAMES,
    AccountKind,
    CoachProfile,
    Currency,
    Interest,
    Money,
    SlotName,
    SlotRecord,
    parse_slot_value,
)
from app.schemas.contract import HostCountryCode, JobTypeId


def money(amount: object = 1200, currency: str = "SGD", period: str = "month") -> dict[str, Any]:
    return {"amount": amount, "currency": currency, "period": period}


def total(amount: object = 500, currency: str = "SGD") -> dict[str, Any]:
    return money(amount, currency, "once")


WORKER: dict[str, Any] = {
    "destination_country": "SG",
    "job_type": "domestic_worker",
    "departure_date": "2026-12-01",
    "monthly_salary": money(600),
    "dependents": 3,
    "remittance_target": money(350),
    "recruitment_fee_paid": total(2400, "PHP"),
    "debt_outstanding": total(1800),
    "debt_interest": {"rate_percent": 5, "period": "month"},
    "savings": total(200),
    "bank_or_wallet": "mobile_wallet",
}


class TestTheSlots:
    def test_the_slot_names_are_the_fields_of_the_profile(self) -> None:
        assert set(SLOT_NAMES) == set(CoachProfile.model_fields)
        assert SLOT_NAMES == get_args(SlotName)
        assert len(SLOT_NAMES) == 11

    def test_an_empty_profile_is_valid_because_the_interview_fills_it_slowly(self) -> None:
        profile = CoachProfile()

        assert all(getattr(profile, name) is None for name in SLOT_NAMES)

    def test_an_explicit_null_means_not_answered_for_every_slot(self) -> None:
        # A structured answer from the model lists every slot, with null for what was not said.
        profile = CoachProfile.model_validate({name: None for name in SLOT_NAMES})

        assert profile == CoachProfile()

    def test_a_complete_profile_is_valid(self) -> None:
        profile = CoachProfile.model_validate(WORKER)

        assert profile.monthly_salary == Money(amount=600, currency="SGD", period="month")
        assert profile.debt_interest == Interest(rate_percent=5, period="month")

    def test_it_serialises_as_the_shapes_the_data_model_documents(self) -> None:
        stored = CoachProfile.model_validate(WORKER).model_dump(mode="json", exclude_none=True)

        assert stored == WORKER
        assert isinstance(stored["departure_date"], str)

    def test_the_places_and_jobs_are_the_ones_the_rest_of_the_app_uses(self) -> None:
        assert set(get_args(HostCountryCode)) == {"SG", "KR", "MY", "JP", "HK", "AU"}
        assert len(get_args(JobTypeId)) == 7
        assert set(get_args(AccountKind)) == {"bank_account", "mobile_wallet", "both", "none"}

    def test_currencies_cover_the_hosts_and_every_home_country_onboarding_offers(self) -> None:
        assert set(get_args(Currency)) == {
            *("SGD", "KRW", "MYR", "JPY", "HKD", "AUD"),
            *("PHP", "INR", "IDR", "NPR", "BDT"),
        }

    def test_a_slot_the_model_invented_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            CoachProfile.model_validate({"favourite_colour": "blue"})

    def test_a_country_that_is_not_a_host_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            CoachProfile.model_validate({"destination_country": "NZ"})


class TestMoney:
    @pytest.mark.parametrize(
        "bad",
        [
            money(-1),
            money(2_000_000_000),
            money(float("nan")),
            money(float("inf")),
            money(True),
            money("1200"),
            money(None),
            money(1200, "USD"),
            money(1200, "sgd"),
            money(1200, period="day"),
            money(1200, period="hour"),
            {"amount": 1200, "currency": "SGD"},
            {"currency": "SGD", "period": "month"},
            {**money(), "note": "x"},
        ],
    )
    def test_an_impossible_amount_is_refused(self, bad: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            CoachProfile.model_validate({"remittance_target": bad})

    def test_zero_is_allowed_where_nothing_is_a_real_answer(self) -> None:
        profile = CoachProfile.model_validate(
            {
                "remittance_target": money(0),
                "recruitment_fee_paid": total(0),
                "debt_outstanding": total(0),
                "savings": total(0),
            }
        )

        assert profile.debt_outstanding is not None and profile.debt_outstanding.amount == 0

    def test_a_whole_number_of_money_is_fine_and_so_is_a_decimal(self) -> None:
        assert Money.model_validate(money(1200)).amount == 1200
        assert Money.model_validate(money(1200.5)).amount == 1200.5

    @pytest.mark.parametrize("slot", ["monthly_salary", "remittance_target"])
    def test_pay_and_targets_need_a_real_period(self, slot: str) -> None:
        for period in ("month", "week", "year"):
            assert CoachProfile.model_validate({slot: money(period=period)})
        with pytest.raises(ValidationError, match="month, a week or a year"):
            CoachProfile.model_validate({slot: total()})

    @pytest.mark.parametrize("slot", ["savings", "recruitment_fee_paid", "debt_outstanding"])
    def test_a_total_cannot_be_given_per_period(self, slot: str) -> None:
        assert CoachProfile.model_validate({slot: total()})
        with pytest.raises(ValidationError, match="total, not an amount"):
            CoachProfile.model_validate({slot: money()})

    def test_a_salary_is_more_than_zero(self) -> None:
        with pytest.raises(ValidationError, match="more than zero"):
            CoachProfile.model_validate({"monthly_salary": money(0)})

    @pytest.mark.parametrize(
        ("period", "expected"),
        [("month", 1200.0), ("week", 1200 * 52 / 12), ("year", 100.0)],
    )
    def test_per_month_converts_without_guessing(self, period: str, expected: float) -> None:
        assert Money.model_validate(money(1200, period=period)).per_month() == pytest.approx(
            expected
        )

    def test_a_total_has_no_monthly_figure(self) -> None:
        with pytest.raises(ValueError, match="no monthly figure"):
            Money.model_validate(total()).per_month()


class TestInterest:
    @pytest.mark.parametrize("rate", [0, 5, 20.5, 1000])
    def test_a_rate_up_to_1000_percent_is_valid(self, rate: float) -> None:
        assert Interest.model_validate({"rate_percent": rate, "period": "year"})

    @pytest.mark.parametrize(
        "bad",
        [
            {"rate_percent": -1, "period": "month"},
            {"rate_percent": 1001, "period": "month"},
            {"rate_percent": float("nan"), "period": "month"},
            {"rate_percent": "5", "period": "month"},
            {"rate_percent": 5, "period": "week"},
            {"rate_percent": 5, "period": "once"},
            {"rate_percent": 5},
        ],
    )
    def test_an_impossible_rate_is_refused(self, bad: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            Interest.model_validate(bad)


class TestDependents:
    @pytest.mark.parametrize("count", [0, 1, 20])
    def test_a_head_count_from_zero_to_twenty_is_valid(self, count: int) -> None:
        assert CoachProfile.model_validate({"dependents": count}).dependents == count

    @pytest.mark.parametrize("bad", [-1, 21, 2.5, True, "3", [2]])
    def test_anything_else_is_refused(self, bad: object) -> None:
        with pytest.raises(ValidationError):
            CoachProfile.model_validate({"dependents": bad})


class TestDepartureDate:
    @pytest.mark.parametrize("value", ["2026-12-01", "2028-02-29", "2000-01-01", "2100-12-31"])
    def test_a_real_date_in_iso_form_is_valid(self, value: str) -> None:
        assert CoachProfile.model_validate({"departure_date": value}).departure_date == value

    @pytest.mark.parametrize(
        "bad",
        [
            "01-12-2026",
            "2026/12/01",
            "2026-13-01",
            "2026-02-30",
            "2027-02-29",
            "1999-12-31",
            "2101-01-01",
            "2026-12-01T00:00:00",
            " 2026-12-01",
            "",
            20261201,
        ],
    )
    def test_anything_else_is_refused(self, bad: object) -> None:
        with pytest.raises(ValidationError):
            CoachProfile.model_validate({"departure_date": bad})

    def test_a_date_object_is_refused_because_it_is_stored_as_text(self) -> None:
        with pytest.raises(ValidationError):
            CoachProfile.model_validate({"departure_date": date(2026, 12, 1)})


class TestSlotRecord:
    RECORD: dict[str, Any] = {
        "value": money(4200, "AUD"),
        "confidence": 0.9,
        "source": "contract_prefill",
        "confirmed": True,
        "updated_at": "2026-10-20T08:05:02Z",
        "turn": 4,
    }

    def test_it_holds_the_fields_the_data_model_lists(self) -> None:
        record = SlotRecord.model_validate(self.RECORD)

        assert record.source == "contract_prefill"
        assert record.confirmed is True
        assert record.updated_at.tzinfo is not None

    def test_its_value_can_be_checked_as_the_slot_it_belongs_to(self) -> None:
        record = SlotRecord.model_validate(self.RECORD)

        assert parse_slot_value("monthly_salary", record.value) == Money(
            amount=4200, currency="AUD", period="month"
        )

    @pytest.mark.parametrize(
        "change",
        [
            {"confidence": -0.1},
            {"confidence": 1.1},
            {"source": "guess"},
            {"turn": -1},
            {"value": None},
            {"updated_at": "yesterday"},
            {"extra": 1},
        ],
    )
    def test_a_bad_record_is_refused(self, change: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            SlotRecord.model_validate({**self.RECORD, **change})

    @pytest.mark.parametrize("missing", ["value", "confidence", "source", "confirmed", "turn"])
    def test_every_field_is_required(self, missing: str) -> None:
        record = {key: value for key, value in self.RECORD.items() if key != missing}

        with pytest.raises(ValidationError):
            SlotRecord.model_validate(record)


class TestParseSlotValue:
    def test_it_applies_the_rules_of_that_slot_only(self) -> None:
        assert parse_slot_value("dependents", 2) == 2
        assert parse_slot_value("destination_country", "KR") == "KR"
        assert parse_slot_value("debt_outstanding", total(0)) == Money(
            amount=0, currency="SGD", period="once"
        )

    def test_it_refuses_a_value_that_breaks_a_rule_of_the_slot(self) -> None:
        with pytest.raises(ValidationError):
            parse_slot_value("savings", money())

    def test_it_refuses_a_name_that_is_not_a_slot(self) -> None:
        with pytest.raises(KeyError):
            parse_slot_value("model_config", {})
