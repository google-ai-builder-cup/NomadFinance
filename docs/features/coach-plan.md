# Financial Coach: the 90-day plan

How the plan of `POST /api/v2/coach/sessions/{id}/plan` is made (NF-FC-012). The contract (fields, errors) is [`docs/api/v2-coach.md`](../api/v2-coach.md); the score it carries is [`coach-scoring.md`](coach-scoring.md). Rules version **1** (`PLAN_RULES_VERSION` in `backend/app/services/coach/plan_figures.py`): changing a rule below means changing this page and that number.

## Who writes what

| Part of the plan | Written by | Checked by |
|---|---|---|
| Every figure: budget, goals, remittance amounts and schedule, debt, emergency fund, the provider quote | **Code** (`plan_figures.py`), from the answers, the cost baselines, the stored rates and Remittance X-Ray | The schema (the budget adds up), and `check_figures` (the plan equals the worked-out figures) |
| Which warnings and checklist items a worker gets, and their severity | Code (`plan_facts.py`) | Tests |
| The summary, the title and actions of weeks 1 to 13, the words of each warning and checklist item | **Gemini** (`coach/plan.v1`, reasoning tier) | `plan_validator.check_text` |
| The "not professional advice" note | Fixed text (`DISCLAIMER`) | |

The model is given the figures as facts and returns sentences only. It cannot put a figure in the plan; the worst it can do is write a wrong number in a sentence, and the validator rejects that.

## The figures

All in the host country's currency, from the answers converted with the stored host-to-home rate (the same conversion as the score).

| Figure | Rule |
|---|---|
| Income | The monthly pay |
| Costs | The baseline's typical accommodation, food, transport and phone (the job type's own figure where there is one), plus deductions: the baseline's typical share of pay (`mandatory_deductions`, percent of wage) times the pay |
| Remittance | The worker's own monthly target |
| Available | Income − costs − remittance |
| Debt payment | Only with a debt. 50% of what is available; **70% when the debt costs 24% a year or more**; never more than the debt with one month's interest; whole units; 0 if nothing is available |
| Emergency saving | 40% of what is available (25% when the debt is costly; **80% with no debt**); whole units |
| Left over | Income − costs − every goal, exactly. Negative means the costs and the remittance are more than the pay: no other goal is funded and the plan says so |
| Emergency-fund target | **3 months** of costs |
| Weeks to target | (target − savings now) ÷ monthly saving × 52/12, rounded up; 0 when already met; none when the saving is 0 |
| Months to clear | Months of the payment until the debt (growing at its monthly interest) is gone; none when the payment does not cover the interest. A yearly rate is divided by 12 |
| First-month setup costs | The baseline's typical one-off costs, summed; shown apart from the monthly lines |
| Send weeks | **5, 9 and 13**: pay arrives at the end of the first month, then every four weeks. No sends when the target is 0 |
| Provider | The highest-ranked provider that workers have not flagged on the Exploitation Radar, from Remittance X-Ray for the monthly amount; the fee is its fee, `receives` is what arrives at home, `fx_rate` is `receives ÷ (amount − fee)`, the rate the worker effectively gets. No provider (and a `no_provider_quote` note) when the route is not one of the six corridors, when the amount is outside what the survey can be stretched to, or when the fee is not less than the amount |

The corridor is the destination slot and the worker's home country from their profile (`users/{uid}.home_country`). A worker from Nepal or Bangladesh, or with no home country set, has no corridor.

## Warnings and checklist

| Warning | When | Severity |
|---|---|---|
| `fee_above_legal_limit` | The fee paid is more than the cap (cap months × pay, from `labor_laws`) | urgent |
| `high_interest_debt` | A debt at 24% a year or more | warning; urgent from 48% |
| `debt_not_covered` | The debt's payment does not cover its interest | urgent |
| `budget_shortfall` | Costs and the remittance are more than the pay | urgent |
| `thin_emergency_fund` | Savings are under the target | warning if under one month of costs, else info |
| `no_pay_account` | No bank account or wallet | warning |
| `no_provider_quote` | A remittance is planned and no price could be worked out | info |

Most serious first. Checklist: `keep_documents`, `compare_transfer_providers`, `save_helpline_numbers` and `track_spending` always; `open_pay_account` without a bank account; `keep_agent_receipts` after a fee; `pay_costly_debt_first` for a costly debt.

## What the validator accepts

Every number the model writes must be one it was given, to the precision it wrote it (an amount may be rounded or cut: 2,721.43 may be written 2,721 or 2,721.4). A number beside a currency must be a money fact; beside a percent sign or the word "percent", a percent fact; any other must be a count it was given, a week from 1 to 13, or 30, 60 or 90. Rejected too: "thousand", "million" or "lakh" (digits only), links and addresses, and advice to borrow, take a loan, change lender, invest or buy insurance. The ids of the warnings and checklist items must be exactly those asked for, and the weeks exactly 1 to 13 with one to four actions.

A rejected answer is asked for again once, with the reasons. A second rejection is `502 ai_bad_response` and nothing is stored.

## Translation and the PDF (NF-FC-014)

The plan is written in English once. Another language is made on the first request (`language` on `POST /plan`, `GET /plans/{id}` or the `.pdf`) and kept as `coach_plans/{id}/translations/{lang}`.

- **Only sentences are translated.** `plan_translator.py` sends the narrative (the summary, the title and actions of the 13 weeks, the text of the warnings and checklist items, the disclaimer) to Flash-Lite and nothing else. No figure, id or severity is sent.
- **Checked before saving** (`plan_translation_check.py`): the same entries in the same order; in every text the same numbers and currency codes, character for character (digits 0 to 9 only, no other script's digits, nothing added or dropped); no links; no runaway length. Then the translated plan with its sentences taken out must equal the English one, byte for byte (`same_figures`). One retry with the reasons, then `502 ai_bad_response`; nothing is saved.
- **The PDF** (`plan_pdf_html.py`, weasyprint, Noto fonts in the image): the score and its five factors, the budget, the remittance with the provider, the debt, the emergency fund, the 13 weeks, the warnings by severity (a word, not only a colour), the checklist, the dates and the disclaimer. The fixed wording is in six languages (`plan_pdf_labels*.py`); figures are written as in the JSON plan. It is made on first request in a language, stored at `exports/{uid}/coach-plan-{id}-{lang}.pdf` (account deletion removes it with the other exports) and returned through the API, not as a signed link.

## Limits

- A number written as a word ("three months") is not checked; the prompt asks for digits.
- The advice check catches the common ways to suggest a loan, not all. The wider guardrails are NF-FC-013's.
- The plan id is the hash of the answers only, so a worker whose home country changes in their profile still gets the stored plan.
- The shares (50/70/40/25/80), the 3 months and the send weeks are product choices, not financial planning advice; they are written here so the owner can review them.
