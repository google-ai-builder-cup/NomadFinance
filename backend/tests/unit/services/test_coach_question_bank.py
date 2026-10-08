"""The Coach's question bank (NF-FC-001): the file, its wording, its skip rules and follow-ups.

Expected ranges: test_coach_question_ranges.py. Edits that must be refused:
test_coach_question_bank_edits.py.
"""

from __future__ import annotations

import re
from typing import get_args

import pytest

from app.schemas.coach_profile import (
    SLOT_NAMES,
    AccountKind,
    CoachProfile,
    Currency,
    SlotName,
)
from app.schemas.coach_questions import STAGES, ChoiceRange, Question, QuestionBank
from app.schemas.contract import HostCountryCode, JobTypeId
from app.services.coach.question_bank import is_applicable, load_question_bank
from tests.fixtures.coach_bank import DATA_FILE, money, question, raw

# The grouping of design 4.3 ("Slot-to-stage grouping"), final in NF-FC-001.
STAGE_OF = {
    "destination_country": "intro",
    "job_type": "intro",
    "departure_date": "intro",
    "monthly_salary": "income",
    "dependents": "obligations",
    "remittance_target": "obligations",
    "recruitment_fee_paid": "debt",
    "debt_outstanding": "debt",
    "debt_interest": "debt",
    "savings": "savings",
    "bank_or_wallet": "savings",
}
# Words a worker who reads English as a second language would not know.
JARGON = {
    "remittance", "remit", "liability", "liabilities", "principal", "apr", "collateral",
    "disposable", "amortisation", "amortization", "obligations", "creditor", "debtor",
}  # fmt: skip


@pytest.fixture(scope="module")
def bank() -> QuestionBank:
    return load_question_bank()


class TestTheFile:
    def test_it_loads_and_is_read_only_once(self, bank: QuestionBank) -> None:
        assert bank.version == 1
        assert load_question_bank() is bank

    def test_every_slot_has_exactly_one_question(self, bank: QuestionBank) -> None:
        assert sorted(item.slot for item in bank.questions) == sorted(SLOT_NAMES)

    def test_the_questions_follow_the_stages_of_the_design(self, bank: QuestionBank) -> None:
        assert {item.slot: item.stage for item in bank.questions} == STAGE_OF
        assert [item.stage for item in bank.questions] == sorted(
            (item.stage for item in bank.questions), key=STAGES.index
        )

    def test_only_the_departure_date_may_be_left_unanswered(self, bank: QuestionBank) -> None:
        assert [item.slot for item in bank.questions if not item.required] == ["departure_date"]

    def test_the_choices_are_exactly_the_values_the_profile_accepts(
        self, bank: QuestionBank
    ) -> None:
        expected = {
            "destination_country": set(get_args(HostCountryCode)),
            "job_type": set(get_args(JobTypeId)),
            "bank_or_wallet": set(get_args(AccountKind)),
        }
        for slot, options in expected.items():
            asked = bank.question(slot).expected
            assert isinstance(asked, ChoiceRange)
            assert len(asked.options) == len(set(asked.options))
            assert set(asked.options) == options

    def test_the_scale_has_every_currency_and_says_what_it_is_not(self, bank: QuestionBank) -> None:
        assert set(bank.monthly_pay_scale) == set(get_args(Currency))
        assert "not" in bank.scale_note.lower()

    def test_the_file_is_utf8_json_with_a_final_newline(self) -> None:
        assert DATA_FILE.read_bytes().endswith(b"}\n")


class TestPlainLanguage:
    def texts(self, bank: QuestionBank) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        for item in bank.questions:
            found += [(f"{item.slot}.prompt", item.prompt_en), (f"{item.slot}.why", item.why_en)]
            found += [(f"{item.slot}.{f.trigger}", f.prompt_en) for f in item.follow_ups]
        for kind, follow_ups in bank.follow_up_defaults.items():
            found += [(f"default.{kind}.{f.trigger}", f.prompt_en) for f in follow_ups]
        return found

    def test_every_sentence_is_short(self, bank: QuestionBank) -> None:
        for where, text in self.texts(bank):
            for sentence in re.split(r"(?<=[.?!])\s+", text):
                assert len(sentence.split()) <= 25, f"{where}: {sentence!r}"

    def test_no_text_is_a_wall(self, bank: QuestionBank) -> None:
        for where, text in self.texts(bank):
            assert len(re.findall(r"[.?!](?:\s|$)", text)) <= 4, where

    def test_no_text_uses_a_word_a_worker_may_not_know(self, bank: QuestionBank) -> None:
        for where, text in self.texts(bank):
            words = set(re.findall(r"[a-z]+", text.lower()))
            assert not words & JARGON, f"{where}: {sorted(words & JARGON)}"

    def test_every_question_says_what_to_answer_and_why_it_is_asked(
        self, bank: QuestionBank
    ) -> None:
        for item in bank.questions:
            assert item.prompt_en.endswith(("?", "."))
            assert item.why_en.endswith(".")
            assert item.prompt_en != item.why_en

    def test_a_question_that_accepts_zero_says_how_to_answer_it(self, bank: QuestionBank) -> None:
        for slot in ("dependents", "recruitment_fee_paid", "debt_outstanding", "savings"):
            assert "0" in bank.question(slot).prompt_en


class TestSkipRules:
    def test_the_interest_is_skipped_only_when_nothing_is_owed(self, bank: QuestionBank) -> None:
        skips = {item.slot: item.skip_if for item in bank.questions if item.skip_if}

        assert list(skips) == ["debt_interest"]
        (rule,) = skips["debt_interest"]
        assert (rule.slot, rule.field, rule.equals) == ("debt_outstanding", "amount", 0)

    @pytest.mark.parametrize(
        ("owed", "asked"),
        [(None, True), (0, False), (0.0, False), (1, True), (2500, True)],
    )
    def test_the_interest_follows_the_amount_owed(
        self, bank: QuestionBank, owed: float | None, asked: bool
    ) -> None:
        profile = CoachProfile.model_validate(
            {}
            if owed is None
            else {"debt_outstanding": {"amount": owed, "currency": "SGD", "period": "once"}}
        )

        assert is_applicable(bank.question("debt_interest"), profile) is asked

    def test_not_having_been_asked_yet_never_skips_a_question(self, bank: QuestionBank) -> None:
        profile = CoachProfile.model_validate({"recruitment_fee_paid": money(0, period="once")})

        assert is_applicable(bank.question("debt_interest"), profile)

    def test_every_other_question_is_always_asked(self, bank: QuestionBank) -> None:
        nothing_owed = CoachProfile.model_validate(
            {"debt_outstanding": {"amount": 0, "currency": "SGD", "period": "once"}}
        )

        for item in bank.questions:
            if item.slot != "debt_interest":
                assert is_applicable(item, CoachProfile())
                assert is_applicable(item, nothing_owed)

    def test_a_skip_rule_on_a_scalar_slot_compares_the_value_itself(self) -> None:
        data = question(raw(), "job_type")
        data["skip_if"] = [{"slot": "destination_country", "equals": "SG"}]
        scalar = Question.model_validate(data)

        assert not is_applicable(scalar, CoachProfile(destination_country="SG"))
        assert is_applicable(scalar, CoachProfile(destination_country="KR"))
        assert is_applicable(scalar, CoachProfile())


class TestFollowUps:
    def test_every_question_has_a_follow_up_for_every_reason_it_may_need(
        self, bank: QuestionBank
    ) -> None:
        for item in bank.questions:
            for trigger in bank.triggers_for(item):
                assert bank.follow_up(item.slot, trigger).prompt_en

    def test_a_question_own_wording_wins_over_the_default(self, bank: QuestionBank) -> None:
        own = bank.follow_up("destination_country", "not_understood").prompt_en
        default = bank.follow_up("dependents", "not_understood").prompt_en

        assert "Singapore" in own
        assert "Singapore" not in default

    def test_the_salary_follow_up_covers_pay_by_the_day(self, bank: QuestionBank) -> None:
        assert "by the day" in bank.follow_up("monthly_salary", "unclear_period").prompt_en

    @pytest.mark.parametrize("slot", ["savings", "recruitment_fee_paid", "debt_outstanding"])
    def test_a_total_is_never_asked_which_period_it_covers(
        self, bank: QuestionBank, slot: SlotName
    ) -> None:
        with pytest.raises(KeyError):
            bank.follow_up(slot, "unclear_period")

    def test_a_reason_that_cannot_happen_is_not_offered(self, bank: QuestionBank) -> None:
        for slot in ("destination_country", "job_type", "bank_or_wallet"):
            with pytest.raises(KeyError):
                bank.follow_up(slot, "out_of_range")
        with pytest.raises(KeyError):
            bank.follow_up("dependents", "missing_currency")

    def test_a_slot_with_no_question_is_an_error(self, bank: QuestionBank) -> None:
        with pytest.raises(KeyError):
            bank.question("favourite_colour")
