"""The plan PDF as HTML (NF-FC-014), built from a stored plan in its language.

Every value is escaped here, and the HTML links to nothing, so the renderer has nothing to fetch.
Figures are written as in the JSON plan (digits 0 to 9, a comma for thousands, no more than two
decimals), whatever the language.
"""

from __future__ import annotations

from html import escape

from app.schemas.coach_plan import CoachPlanResponse, PlanMoney
from app.services.coach.plan_pdf_labels import label, named

# Noto covers Latin, Devanagari and Bengali (installed in the image, backend/Dockerfile); the
# last entries are fallbacks for a developer machine without Noto.
CSS = """
@page { size: A4; margin: 14mm 16mm 16mm;
        @bottom-center { content: counter(page) " / " counter(pages); font-size: 8pt;
                         color: #52606d; } }
body { font-family: "Noto Sans", "Noto Sans Devanagari", "Noto Sans Bengali", "Nirmala UI",
       "Segoe UI", sans-serif; font-size: 10pt; line-height: 1.5; color: #1f2933; }
h1 { font-size: 20pt; margin: 0 0 1mm; color: #0b3d62; }
h2 { font-size: 12pt; margin: 5mm 0 2mm; padding-bottom: 1mm; border-bottom: 1px solid #c5ced6;
     color: #0b3d62; break-after: avoid; }
.meta { color: #52606d; margin: 0 0 3mm; }
.score { display: flex; align-items: baseline; gap: 4mm; margin: 0 0 2mm; }
.big { font-size: 30pt; font-weight: 700; color: #0b3d62; }
.band { font-weight: 600; }
table { width: 100%; border-collapse: collapse; }
td { padding: 1.2mm 0; border-bottom: 1px solid #e4e9ee; vertical-align: middle; }
td.num { text-align: right; font-weight: 600; white-space: nowrap; padding: 0 1.2mm 0 4mm; }
td.bar { width: 30%; }
.track { height: 2.6mm; background: #e4e9ee; border-radius: 1.3mm; }
.fill { height: 2.6mm; background: #1f7a8c; border-radius: 1.3mm; }
tr.sub td { padding-top: 2.5mm; color: #52606d; font-size: 8.5pt; font-weight: 700;
            text-transform: uppercase; border-bottom: none; }
tr.total td { border-top: 1.5px solid #1f2933; font-weight: 700; }
.week { break-inside: avoid; margin: 0 0 2.5mm; }
.week b { color: #0b3d62; }
ul { margin: 0.5mm 0 0 5mm; padding: 0; }
.note { break-inside: avoid; margin: 0 0 2mm; padding: 1.5mm 3mm; border-left: 1.5mm solid #7b8794;
        background: #f5f7fa; }
.note.urgent { border-color: #b42318; }
.note.warning { border-color: #b7791f; }
.tag { font-weight: 700; }
.box { display: inline-block; width: 3mm; height: 3mm; border: 1px solid #52606d;
       margin-right: 2mm; vertical-align: middle; }
.disclaimer { margin-top: 6mm; padding-top: 3mm; border-top: 1px solid #c5ced6; font-size: 8.5pt;
              color: #52606d; }
"""


def money(value: PlanMoney) -> str:
    """`4,200 AUD`, `1,473.72 AUD`."""
    text = f"{value.amount:,.2f}".rstrip("0").rstrip(".")
    return f"{text} {value.currency}"


def _row(name: str, value: str, extra: str = "") -> str:
    return f"<tr{extra}><td>{escape(name)}</td><td class='num'>{escape(value)}</td></tr>"


def _sub(name: str) -> str:
    return f"<tr class='sub'><td colspan='2'>{escape(name)}</td></tr>"


def _table(rows: list[str]) -> str:
    return f"<table>{''.join(rows)}</table>"


def _score(r: CoachPlanResponse, lang: str) -> str:
    rows = []
    for factor in r.score.factors:
        width = max(0, min(int(factor.score), 100))
        rows.append(
            f"<tr><td>{escape(named(lang, 'factor', factor.id))}</td>"
            f"<td class='bar'><div class='track'><div class='fill' style='width:{width}%'></div>"
            f"</div></td><td class='num'>{width} {escape(label(lang, 'points'))}</td></tr>"
        )
    return (
        f"<h2>{escape(label(lang, 'score_heading'))}</h2>"
        f"<div class='score'><span class='big'>{r.score.total}</span>"
        f"<span>{escape(label(lang, 'score_of'))}</span>"
        f"<span class='band'>{escape(named(lang, 'band', r.score.band))}</span></div>"
        f"{_table(rows)}"
    )


def _budget(r: CoachPlanResponse, lang: str) -> str:
    budget = r.plan.monthly_budget
    rows = [_row(label(lang, "income"), money(budget.income), " class='total'")]
    rows.append(_sub(label(lang, "costs_heading")))
    rows += [_row(named(lang, "cost", c.id), money(c.amount)) for c in budget.costs]
    rows.append(_sub(label(lang, "goals_heading")))
    rows += [_row(named(lang, "goal", g.id), money(g.amount)) for g in budget.goals]
    rows.append(_row(label(lang, "left_over"), money(budget.left_over), " class='total'"))
    if budget.setup_costs:
        rows.append(_row(label(lang, "setup_costs"), money(budget.setup_costs)))
    return f"<h2>{escape(label(lang, 'budget_heading'))}</h2>{_table(rows)}"


def _remittance(r: CoachPlanResponse, lang: str) -> str:
    plan = r.plan.remittance
    rows = [_row(label(lang, "monthly_amount"), money(plan.monthly_amount))]
    provider = plan.provider
    if provider is not None:
        rows += [
            _row(label(lang, "provider"), provider.name),
            _row(label(lang, "fee"), money(provider.fee)),
            _row(label(lang, "receives"), money(provider.receives)),
            _row(label(lang, "rate"), f"{provider.fx_rate:g}"),
        ]
    if plan.schedule:
        weeks = ", ".join(str(send.week) for send in plan.schedule)
        rows.append(_row(label(lang, "send_weeks"), weeks))
    body = _table(rows)
    if provider is None and plan.monthly_amount.amount > 0:
        body += f"<p class='meta'>{escape(label(lang, 'no_provider'))}</p>"
    return f"<h2>{escape(label(lang, 'remittance_heading'))}</h2>{body}"


def _debt_and_fund(r: CoachPlanResponse, lang: str) -> str:
    out = ""
    debt = r.plan.debt
    if debt is not None:
        rows = [
            _row(label(lang, "outstanding"), money(debt.outstanding)),
            _row(label(lang, "monthly_payment"), money(debt.monthly_payment)),
        ]
        if debt.months_to_clear is None:
            rows.append(_row(label(lang, "months_to_clear"), label(lang, "not_covered")))
        else:
            rows.append(_row(label(lang, "months_to_clear"), str(debt.months_to_clear)))
        out += f"<h2>{escape(label(lang, 'debt_heading'))}</h2>{_table(rows)}"
    fund = r.plan.emergency_fund
    reach = (
        label(lang, "already_met")
        if fund.weeks_to_target == 0
        else "-" if fund.weeks_to_target is None else str(fund.weeks_to_target)
    )
    rows = [
        _row(label(lang, "target"), money(fund.target)),
        _row(label(lang, "months_of_costs"), str(fund.months_of_costs)),
        _row(label(lang, "monthly_saving"), money(fund.monthly_saving)),
        _row(label(lang, "weeks_to_target"), reach),
    ]
    return out + f"<h2>{escape(label(lang, 'fund_heading'))}</h2>{_table(rows)}"


def _weeks(r: CoachPlanResponse, lang: str) -> str:
    blocks = []
    for week in r.plan.weeks:
        actions = "".join(f"<li>{escape(a)}</li>" for a in week.actions)
        blocks.append(
            f"<div class='week'><b>{escape(label(lang, 'week'))} {week.week}: "
            f"{escape(week.title)}</b><ul>{actions}</ul></div>"
        )
    return f"<h2>{escape(label(lang, 'weeks_heading'))}</h2>{''.join(blocks)}"


def _notes(r: CoachPlanResponse, lang: str) -> str:
    warnings = "".join(
        f"<div class='note {w.severity}'><span class='tag'>"
        f"{escape(label(lang, 'severity_' + w.severity))}</span> {escape(w.text)}</div>"
        for w in r.plan.warnings
    )
    items = "".join(
        f"<div class='week'><span class='box'></span>{escape(c.text)}</div>"
        for c in r.plan.checklist
    )
    out = f"<h2>{escape(label(lang, 'checklist_heading'))}</h2>{items}"
    if warnings:
        out = f"<h2>{escape(label(lang, 'warnings_heading'))}</h2>{warnings}" + out
    return out


def build_plan_html(r: CoachPlanResponse) -> str:
    """The plan PDF for one stored plan, in the plan's own language."""
    lang = r.language
    meta = [f"{label(lang, 'created')}: {r.created_at.date().isoformat()}"]
    if r.corridor_id:
        meta.append(f"{label(lang, 'route')}: {r.corridor_id}")
    if r.departure_date:
        meta.append(f"{label(lang, 'departure')}: {r.departure_date}")
    meta.append(f"{label(lang, 'rates_as_of')} {r.rates_as_of.date().isoformat()}")
    return (
        f"<!doctype html><html lang='{escape(lang)}'><head><meta charset='utf-8'>"
        f"<title>{escape(label(lang, 'title'))}</title><style>{CSS}</style></head><body>"
        f"<h1>{escape(label(lang, 'title'))}</h1>"
        f"<p class='meta'>{escape(' · '.join(meta))}</p>"
        f"{_score(r, lang)}"
        f"<h2>{escape(label(lang, 'summary_heading'))}</h2><p>{escape(r.plan.summary)}</p>"
        f"{_budget(r, lang)}{_remittance(r, lang)}{_debt_and_fund(r, lang)}"
        f"{_weeks(r, lang)}{_notes(r, lang)}"
        f"<p class='disclaimer'>{escape(r.plan.disclaimer)}</p></body></html>"
    )
