from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.services.fib.exporter import _language, render_pdf
from app.services.fib.report_html import build_report_html
from app.services.fib.report_labels import LABEL_KEYS, LABELS

COMPUTED = datetime(2026, 10, 1, 2, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 2, 9, 30, tzinfo=UTC)


def _profile(**overrides: Any) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "reporting_currency": "INR",
        "period_start": "2026-05-01",
        "period_end": "2026-10-01",
        "months_of_data": 6,
        "entry_counts": {"income": 6, "transfers": 5, "bills": 6, "savings": 3},
        "metrics": {
            "income_stability": {"score": 94, "detail": {}},
            "savings_rate": {"score": 45, "detail": {}},
            "remittance_consistency": {"score": 83, "detail": {}},
            "bill_payment_reliability": {"score": None, "detail": {"reason": "no_bills"}},
        },
        "overall_score": 74,
        "narrative": {"language": "en", "text": "First paragraph.\n\nSecond one.", "model": "m"},
        "computed_at": COMPUTED,
    }
    return profile | overrides


def test_every_language_has_every_label() -> None:
    assert set(LABELS) == {"en", "hi", "tl", "id", "ne", "bn"}
    for language, labels in LABELS.items():
        assert set(labels) == set(LABEL_KEYS), language
        assert all(text.strip() for text in labels.values()), language


def test_the_report_is_in_the_narratives_language() -> None:
    html = build_report_html(_profile(narrative={"language": "hi", "text": "पाठ"}), None, NOW)

    assert '<html lang="hi">' in html
    assert LABELS["hi"]["title"] in html
    assert LABELS["hi"]["income_stability"] in html
    assert LABELS["hi"]["disclaimer"] in html
    assert LABELS["en"]["title"] not in html


@pytest.mark.parametrize("narrative", [{"language": "xx", "text": "t"}, {"text": "t"}, {}])
def test_an_unknown_or_missing_language_falls_back_to_english(narrative: dict[str, Any]) -> None:
    html = build_report_html(_profile(narrative=narrative), None, NOW)

    assert '<html lang="en">' in html
    assert LABELS["en"]["title"] in html
    assert _language(_profile(narrative=narrative)) == "en"


def test_scores_and_missing_scores_are_shown() -> None:
    html = build_report_html(_profile(), None, NOW)

    assert 'style="width:94%"' in html
    assert "94 <span" in html
    assert LABELS["en"]["no_data"] in html
    # A metric with no score gets no bar.
    assert html.count('class="fill"') == 3


def test_the_overall_score_is_not_printed() -> None:
    html = build_report_html(_profile(overall_score=74), None, NOW)

    assert ">74<" not in html
    assert "74 " not in html.split("<body>")[1]


def test_the_facts_and_dates_are_shown() -> None:
    html = build_report_html(_profile(), None, NOW)

    assert "2026-05-01 – 2026-10-01" in html
    assert "<dd>6</dd>" in html
    assert "<dd>INR</dd>" in html
    assert "<dd>2026-10-01</dd>" in html  # when the profile was computed
    assert "<dd>2026-10-02</dd>" in html  # when the report was made


def test_a_computed_date_stored_as_text_is_shown_too() -> None:
    html = build_report_html(_profile(computed_at="2026-09-28T02:00:00+00:00"), None, NOW)

    assert "<dd>2026-09-28</dd>" in html


def test_the_narrative_keeps_its_paragraphs_and_line_breaks() -> None:
    text = "One.\n\nTwo\nsame paragraph.\n\n\nThree."

    html = build_report_html(_profile(narrative={"language": "en", "text": text}), None, NOW)

    assert "<p>One.</p><p>Two<br>same paragraph.</p><p>Three.</p>" in html


def test_the_holder_name_is_printed_only_when_given() -> None:
    assert "Prepared for" not in build_report_html(_profile(), None, NOW)

    html = build_report_html(_profile(), "Priya Sharma", NOW)

    assert "Prepared for: <b>Priya Sharma</b>" in html


def test_everything_from_the_worker_or_the_profile_is_escaped() -> None:
    nasty = "<script>alert(1)</script>"
    profile = _profile(
        narrative={"language": "en", "text": f"{nasty}\n\n<img src=http://x/y.png>"},
        verified_employment=[
            {"employer_name": nasty, "salary_amount": "<b>1</b>", "salary_currency": "S&D"}
        ],
        reporting_currency=nasty,
    )

    html = build_report_html(profile, nasty, NOW)

    assert "<script>" not in html
    assert "<img" not in html
    assert "<b>1</b>" not in html
    assert "&lt;script&gt;" in html
    assert "S&amp;D" in html


def test_verified_employment_is_listed_with_its_salary() -> None:
    profile = _profile(
        verified_employment=[
            {
                "employer_name": "Example Household",
                "salary_amount": 650,
                "salary_currency": "SGD",
                "contract_ref": "c1",
            },
            {"employer_name": None, "salary_amount": 700, "salary_currency": "SGD"},
        ]
    )

    html = build_report_html(profile, None, NOW)

    assert LABELS["en"]["verified_heading"] in html
    assert "<dd>Example Household</dd>" in html
    assert "<dd>650 SGD</dd>" in html
    assert "<dd>-</dd>" in html
    assert "c1" not in html


def test_without_verified_employment_the_section_is_left_out() -> None:
    assert LABELS["en"]["verified_heading"] not in build_report_html(_profile(), None, NOW)


def test_the_disclaimer_says_it_is_not_a_credit_score() -> None:
    assert "not a credit score" in build_report_html(_profile(), None, NOW)


def _can_render() -> bool:
    try:
        render_pdf("<p>x</p>")
    except OSError:  # the system libraries weasyprint draws with are not installed
        return False
    return True


@pytest.mark.skipif(not _can_render(), reason="weasyprint's system libraries are missing")
@pytest.mark.parametrize("language", sorted(LABELS))
def test_every_language_renders_to_a_pdf(language: str) -> None:
    profile = _profile(
        narrative={"language": language, "text": LABELS[language]["summary"]},
        verified_employment=[
            {"employer_name": "Example", "salary_amount": 650, "salary_currency": "SGD"}
        ],
    )

    pdf = render_pdf(build_report_html(profile, "Priya", NOW))

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 5_000
