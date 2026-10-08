"""Each slip a reviewer could make in `question_bank.json` must be refused (NF-FC-001)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from tests.fixtures.coach_bank import build, question


class TestAnEditThatBreaksTheFileIsCaught:
    """Each case is a slip a reviewer could make while editing `question_bank.json`."""

    @pytest.mark.parametrize(
        ("name", "change", "message"),
        [
            (
                "a slot is asked twice",
                lambda d: question(d, "job_type").update(slot="destination_country"),
                "exactly once",
            ),
            ("a slot has no question", lambda d: d["questions"].pop(), "exactly once"),
            (
                "the questions are out of stage order",
                lambda d: d["questions"].reverse(),
                "follow the stages",
            ),
            (
                "a stage is left empty",
                lambda d: [item.update(stage="intro") for item in d["questions"]],
                "follow the stages",
            ),
            (
                "a count is given a money range",
                lambda d: question(d, "dependents").update(
                    expected={
                        "kind": "money",
                        "flow": False,
                        "scale_multiple": {"low": 0, "high": 2},
                    }
                ),
                "expected a `count` range",
            ),
            (
                "a flow is marked as a total",
                lambda d: question(d, "monthly_salary")["expected"].update(flow=False),
                "`flow` is wrong",
            ),
            (
                "a total is marked as a flow",
                lambda d: question(d, "savings")["expected"].update(flow=True),
                "`flow` is wrong",
            ),
            (
                "a choice lists a value the profile refuses",
                lambda d: question(d, "destination_country")["expected"]["options"].append("NZ"),
                "not a value of this slot",
            ),
            (
                "a scale entry is missing",
                lambda d: d["monthly_pay_scale"].pop("NPR"),
                "one entry per currency",
            ),
            (
                "a scale number is zero",
                lambda d: d["monthly_pay_scale"].update(SGD=0),
                "above zero",
            ),
            (
                "the default for a reason is removed",
                lambda d: d["follow_up_defaults"]["money"].pop(3),
                "no follow-up for",
            ),
            (
                "a follow-up is listed twice",
                lambda d: question(d, "job_type")["follow_ups"].append(
                    question(d, "job_type")["follow_ups"][0]
                ),
                "listed twice",
            ),
            (
                "a follow-up is given for a reason that cannot happen",
                lambda d: question(d, "job_type")["follow_ups"].append(
                    {"trigger": "missing_currency", "prompt_en": "Which money is that in, please?"}
                ),
                "do not apply",
            ),
            (
                "a skip rule points at an answer asked later",
                lambda d: question(d, "monthly_salary").update(
                    skip_if=[{"slot": "debt_outstanding", "field": "amount", "equals": 0}]
                ),
                "asked later",
            ),
            (
                "a skip rule on an amount names no part of it",
                lambda d: question(d, "debt_interest")["skip_if"][0].pop("field"),
                "`field` must be one of",
            ),
            (
                "a skip rule names a part that does not exist",
                lambda d: question(d, "debt_interest")["skip_if"][0].update(field="colour"),
                "`field` must be one of",
            ),
            (
                "a skip rule names a part of a slot that has none",
                lambda d: question(d, "job_type").update(
                    skip_if=[{"slot": "destination_country", "field": "amount", "equals": 0}]
                ),
                "no parts to name",
            ),
            (
                "a range is upside down",
                lambda d: question(d, "dependents")["expected"]["bounds"].update(low=5, high=1),
                "`low` must be below `high`",
            ),
            (
                "an amount range starts below zero",
                lambda d: question(d, "savings")["expected"]["scale_multiple"].update(low=-1),
                "below zero",
            ),
            (
                "a key is mistyped",
                lambda d: question(d, "savings").update(promt_en="x"),
                "extra_forbidden",
            ),
            (
                "a prompt is empty",
                lambda d: question(d, "savings").update(prompt_en=" "),
                "at least 10 characters",
            ),
            (
                "a prompt is too long to read on a phone",
                lambda d: question(d, "savings").update(prompt_en="word " * 70),
                "at most 300 characters",
            ),
            ("the version is zero", lambda d: d.update(version=0), "greater than or equal to 1"),
        ],
    )
    def test_the_file_is_refused(
        self, name: str, change: Callable[[dict[str, Any]], object], message: str
    ) -> None:
        with pytest.raises(ValidationError, match=re.escape(message)):
            build(change)

    def test_the_untouched_file_still_passes_this_helper(self) -> None:
        assert build(lambda data: None).version == 1
