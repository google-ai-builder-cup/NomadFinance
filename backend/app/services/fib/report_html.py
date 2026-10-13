"""The Financial Identity PDF as HTML (NF-P3-014): built from a stored profile, in its language.

Every value that came from the profile or the worker is escaped here, and the HTML links to
nothing, so the renderer has nothing to fetch.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from app.services.fib.report_labels import LABELS

_METRICS = (
    "income_stability",
    "savings_rate",
    "remittance_consistency",
    "bill_payment_reliability",
)

# Noto covers Latin, Devanagari and Bengali (installed in the image, backend/Dockerfile); the
# last entries are fallbacks for a developer machine without Noto.
_CSS = """
@page { size: A4; margin: 14mm 16mm 14mm; }
body { font-family: "Noto Sans", "Noto Sans Devanagari", "Noto Sans Bengali", "Nirmala UI",
       "Segoe UI", sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1f2933; }
h1 { font-size: 20pt; margin: 0 0 2mm; color: #0b3d62; }
h2 { font-size: 12pt; margin: 5mm 0 2mm; padding-bottom: 1mm; border-bottom: 1px solid #c5ced6;
     color: #0b3d62; }
.holder { font-size: 12pt; margin: 0 0 3mm; }
dl { margin: 0 0 2mm; }
/* A row is one unit: laid out as a grid of its own, a label and its value could land on two
   pages (the value at the foot of one, the label at the top of the next). */
.row { display: grid; grid-template-columns: 55mm 1fr; gap: 0 4mm; margin: 0 0 0.5mm;
       break-inside: avoid; }
dt { color: #52606d; }
dd { margin: 0; font-weight: 600; }
table { width: 100%; border-collapse: collapse; }
td { padding: 1.5mm 0; border-bottom: 1px solid #e4e9ee; vertical-align: middle; }
td.name { width: 38%; }
td.bar { width: 36%; }
td.score { width: 26%; text-align: right; font-weight: 600; }
.track { height: 3mm; background: #e4e9ee; border-radius: 1.5mm; }
.fill { height: 3mm; background: #1f7a8c; border-radius: 1.5mm; }
.none { color: #7b8794; font-weight: 400; }
.summary p { margin: 0 0 3mm; }
.note { margin: 0 0 3mm; font-size: 9pt; color: #52606d; }
.disclaimer { margin-top: 6mm; padding-top: 3mm; border-top: 1px solid #c5ced6;
              font-size: 8.5pt; color: #52606d; }
"""


def _day(value: Any) -> str:
    """A Firestore timestamp or an ISO string as YYYY-MM-DD."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return escape(str(value)[:10])


def _paragraphs(text: str) -> str:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    return "".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _facts(rows: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div class="row"><dt>{escape(k)}</dt><dd>{v}</dd></div>' for k, v in rows)
    return f"<dl>{cells}</dl>"


def _indicator_row(name: str, metric: dict[str, Any], labels: dict[str, str]) -> str:
    score = metric.get("score")
    if score is None:
        bar = ""
        text = f'<span class="none">{escape(labels["no_data"])}</span>'
    else:
        width = max(0, min(int(score), 100))
        bar = f'<div class="track"><div class="fill" style="width:{width}%"></div></div>'
        text = f'{width} <span class="none">{escape(labels["score_of"])}</span>'
    return (
        f'<tr><td class="name">{escape(name)}</td><td class="bar">{bar}</td>'
        f'<td class="score">{text}</td></tr>'
    )


def _per_period(period: Any, labels: dict[str, str]) -> str:
    """` per month`, ` per hour`...: the period a contract salary is stated for, or nothing."""
    label = labels.get(f"period_{period}") if isinstance(period, str) else None
    return f" {escape(label)}" if label else ""


def _number(value: Any) -> str:
    """A count or percentage as digits 0-9, without a trailing ".0"."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return escape(str(value))


def _shared_section(profile: dict[str, Any], labels: dict[str, str]) -> str:
    """What the worker shared from the Coach and the Scam Analyzer (NF-HR-001), or "".

    The exporter has already removed what the worker no longer shares, so what is in `profile`
    is printed as it is. Counts and dates only, each with the fixed wording of the report.
    """
    rows: list[tuple[str, str]] = []
    coach = profile.get("coach_signal")
    if isinstance(coach, dict):
        answered = int(coach.get("checkins_answered", 0))
        rows += [
            (labels["coach_checkins"], _number(answered)),
            (
                labels["coach_remittance"],
                f'{_number(coach.get("remittance_on_track", 0))} / {answered}',
            ),
            (labels["coach_savings"], f'{_number(coach.get("savings_on_track", 0))} / {answered}'),
            (labels["coach_pay"], f'{_number(coach.get("pay_on_time", 0))} / {answered}'),
            (labels["coach_last"], _day(coach.get("last_checkin_at", ""))),
        ]
        if "savings_rate_target_pct" in coach and "savings_rate_recorded_pct" in coach:
            rows += [
                (labels["coach_target"], f'{_number(coach["savings_rate_target_pct"])} %'),
                (labels["coach_recorded"], f'{_number(coach["savings_rate_recorded_pct"])} %'),
            ]
    scam = profile.get("scam_signal")
    if isinstance(scam, dict):
        rows += [
            (labels["scam_checks"], _number(scam.get("checks", 0))),
            (labels["scam_found"], _number(scam.get("scams_found", 0))),
            (labels["scam_last"], _day(scam.get("last_check_at", ""))),
        ]
    if not rows:
        return ""
    paragraph = _paragraphs(str(profile.get("narrative", {}).get("activity_text", "")))
    return (
        f'<h2>{escape(labels["shared_heading"])}</h2>{_facts(rows)}'
        f'<div class="summary">{paragraph}</div>'
        f'<p class="note">{escape(labels["shared_note"])}</p>'
    )


def build_report_html(
    profile: dict[str, Any], holder_name: str | None, generated_at: datetime
) -> str:
    """The report for one `financial_profile/current` document.

    The language is the narrative's own, so the text and the wording around it match. The
    overall score is left out on purpose: it is an average of this project's own formulas and
    could be read as a credit score.
    """
    narrative = profile.get("narrative", {})
    language = narrative.get("language")
    labels = LABELS[language if language in LABELS else "en"]
    counts = profile.get("entry_counts", {})

    header_facts = _facts(
        [
            (labels["period"], f'{_day(profile["period_start"])} – {_day(profile["period_end"])}'),
            (labels["months"], escape(str(profile["months_of_data"]))),
            (labels["currency"], escape(str(profile["reporting_currency"]))),
            (labels["computed"], _day(profile.get("computed_at", ""))),
            (labels["created"], _day(generated_at)),
        ]
    )
    records = _facts(
        [
            (labels["income_entries"], escape(str(counts.get("income", 0)))),
            (labels["transfer_entries"], escape(str(counts.get("transfers", 0)))),
            (labels["bill_entries"], escape(str(counts.get("bills", 0)))),
            (labels["savings_entries"], escape(str(counts.get("savings", 0)))),
        ]
    )
    metrics = profile.get("metrics", {})
    rows = "".join(
        _indicator_row(labels[name], metrics[name], labels) for name in _METRICS if name in metrics
    )

    verified = ""
    employment = profile.get("verified_employment") or []
    if employment:
        jobs = "".join(
            _facts(
                [
                    (labels["verified_employer"], escape(str(job.get("employer_name") or "-"))),
                    (
                        labels["verified_salary"],
                        f'{escape(str(job.get("salary_amount", "")))} '
                        f'{escape(str(job.get("salary_currency", "")))}'
                        f"{_per_period(job.get('salary_period'), labels)}",
                    ),
                ]
            )
            for job in employment
        )
        verified = f'<h2>{escape(labels["verified_heading"])}</h2>{jobs}'

    holder = ""
    if holder_name:
        holder = (
            f'<p class="holder">{escape(labels["prepared_for"])}: <b>{escape(holder_name)}</b></p>'
        )

    return (
        f'<!doctype html><html lang="{escape(language if language in LABELS else "en")}">'
        f'<head><meta charset="utf-8"><title>{escape(labels["title"])}</title>'
        f"<style>{_CSS}</style></head><body>"
        f'<h1>{escape(labels["title"])}</h1>{holder}{header_facts}'
        f'<h2>{escape(labels["records"])}</h2>{records}'
        f'<h2>{escape(labels["indicators"])}</h2><table>{rows}</table>'
        f'<h2>{escape(labels["summary"])}</h2>'
        f'<div class="summary">{_paragraphs(str(narrative.get("text", "")))}</div>'
        f"{verified}"
        f"{_shared_section(profile, labels)}"
        f'<p class="disclaimer">{escape(labels["disclaimer"])}</p>'
        "</body></html>"
    )
