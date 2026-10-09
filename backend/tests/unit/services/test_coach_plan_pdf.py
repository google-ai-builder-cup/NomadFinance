"""The plan PDF: wording in six languages, the HTML and the rendering (NF-FC-014)."""

from __future__ import annotations

import json
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

from app.schemas.coach_plan import CoachPlanResponse
from app.services.coach.plan_pdf import render_plan_pdf
from app.services.coach.plan_pdf_html import build_plan_html, money
from app.services.coach.plan_pdf_labels import LABELS, label, named
from app.services.fib.exporter import render_pdf
from tests.fixtures.coach_mocks import MOCKS

LANGUAGES = ("en", "hi", "tl", "id", "ne", "bn")


def response(name: str = "plan-01-created.json", **changes: object) -> CoachPlanResponse:
    body = json.loads((MOCKS / name).read_text(encoding="utf-8"))["body"]
    language = changes.get("language", "en")
    available = sorted({"en", str(language)})
    return CoachPlanResponse.model_validate({**body, "available_languages": available, **changes})


def _can_render() -> bool:
    try:
        render_pdf("<p>x</p>")
    except OSError:  # the system libraries weasyprint draws with are not installed
        return False
    return True


def test_every_language_has_every_label_in_its_own_script() -> None:
    keys = set(LABELS["en"])

    assert set(LABELS) == set(LANGUAGES)
    for language in LANGUAGES:
        assert set(LABELS[language]) == keys, language
        assert all(text.strip() for text in LABELS[language].values()), language
    assert LABELS["hi"]["title"] != LABELS["en"]["title"]


def test_no_wording_uses_the_digits_of_another_script() -> None:
    for language, labels in LABELS.items():
        for key, text in labels.items():
            assert not any(
                unicodedata.category(c) == "Nd" and c not in "0123456789" for c in text
            ), (language, key)


def test_the_plans_ids_all_have_a_name_in_every_language_and_an_unknown_id_a_fallback() -> None:
    plan = response().plan
    for language in LANGUAGES:
        for cost in plan.monthly_budget.costs:
            assert named(language, "cost", cost.id) == label(language, f"cost_{cost.id}")
        for goal in plan.monthly_budget.goals:
            assert named(language, "goal", goal.id) == label(language, f"goal_{goal.id}")
        for band in ("needs_work", "getting_ready", "well_prepared"):
            assert named(language, "band", band) == label(language, f"band_{band}")
    assert named("hi", "cost", "child_care") == "Child care"
    assert label("xx", "title") == LABELS["en"]["title"]


def test_money_is_written_as_in_the_json() -> None:
    plan = response().plan
    figures = {m.amount for m in plan.host_figures()}

    assert money(plan.monthly_budget.income) == "4,200 AUD"
    assert 4200.0 in figures
    assert money(plan.remittance.provider.receives) == "48,991.2 INR"  # type: ignore[union-attr]
    assert money(plan.debt.outstanding) == "2,177.07 AUD"  # type: ignore[union-attr]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_html_holds_the_figures_the_wording_and_the_disclaimer(language: str) -> None:
    html = build_plan_html(response(language=language))

    assert f"lang='{language}'" in html
    assert label(language, "title") in html and label(language, "score_heading") in html
    for text in ("4,200 AUD", "2,177.07 AUD", "6,465 AUD", "48,991.2 INR", "Example Remit"):
        assert text in html
    assert response().plan.disclaimer in html
    assert "<a " not in html and "src=" not in html and "url(" not in html


def test_what_the_worker_wrote_or_the_model_wrote_is_escaped() -> None:
    plan = response().plan.model_copy(update={"summary": "<script>alert(1)</script> & more"})
    html = build_plan_html(response().model_copy(update={"plan": plan}))

    assert "<script>" not in html and "&lt;script&gt;" in html


def test_a_plan_without_debt_or_provider_has_no_such_sections() -> None:
    html = build_plan_html(response("plan-02-created-no-debt.json"))
    english = LABELS["en"]

    assert f"<h2>{english['debt_heading']}</h2>" not in html
    assert english["no_provider"] in html


@pytest.mark.skipif(not _can_render(), reason="weasyprint's system libraries are missing")
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_renders_to_a_pdf(language: str) -> None:
    pdf = render_plan_pdf(response(language=language))

    assert pdf.startswith(b"%PDF-") and pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 10_000


@pytest.mark.skipif(
    not _can_render() or shutil.which("pdftotext") is None,
    reason="needs weasyprint's libraries and pdftotext",
)
@pytest.mark.parametrize("language", LANGUAGES)
def test_the_text_of_the_pdf_has_the_wording_and_the_figures(language: str, tmp_path: Path) -> None:
    path = tmp_path / "plan.pdf"
    path.write_bytes(render_plan_pdf(response(language=language)))

    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True
    ).stdout

    assert "4,200 AUD" in text and "2,177.07 AUD" in text and "48,991.2 INR" in text
    if language in ("en", "tl", "id"):  # extraction scrambles the order of Indic letters
        assert label(language, "score_heading").split()[0] in text
