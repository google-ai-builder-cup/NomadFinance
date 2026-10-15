# fib (Financial Identity Builder)

Shape sources: the paths for transfers, income, bills and the profile are **[D]**; `savings` is added here because NF-P3-010 needs it. The activity types and the profile metrics come from the original design (Financial Identity pillar and pipeline) and NF-P2-017, NF-P3-010 to NF-P3-015, NF-P3-024 **[T]**. Field names and enums are **[P]**.

```
users/{uid}/transfers/{id}               money sent home (also written by Remittance X-Ray)
users/{uid}/income/{id}                  money earned
users/{uid}/bills/{id}                   bills paid
users/{uid}/savings/{id}                 money set aside
users/{uid}/financial_profile/current    computed profile, one document
```

All are owner-scoped: the user's own data, under their own `users/{uid}` document.

## Fields every entry has

| Field | Type | Required | Description |
|---|---|---|---|
| `entry_date` | string (date) | yes | The day it happened, `YYYY-MM-DD`. Timeline charts sort and range on this. |
| `category` | string | no (yes for income) | Filled by Flash-Lite (NF-P3-012) or by the user. Values below. |
| `category_source` | string | when `category` set | `user` or `model` |
| `category_confidence` | number | when `model` | 0 to 1 |
| `notes` | string | no | Free text from the user |
| `source` | string | yes | `manual`, `remittance_log`, `bill_ocr`, `contract` |
| `created_at`, `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

Money on each entry is a number in major units with its own currency field (see the conventions in `firestore-schema.md`). Currency conversion for totals is done when the profile is computed, in one reporting currency, not stored per entry.

**Categories** (`category`):

| Entry type | Values |
|---|---|
| Income | `salary`, `overtime`, `bonus`, `other_income` |
| Bills | `rent`, `utilities`, `phone_internet`, `transport`, `food`, `medical`, `other_expense` |
| Transfers and savings | none needed (the type says what they are) |

## `users/{uid}/transfers/{id}`

Logged from the comparison result (NF-P2-017). It is the entry that links Remittance X-Ray to Financial Identity.

| Field | Type | Required | Description |
|---|---|---|---|
| `corridor_id` | string | yes | For example `SG-IN` |
| `provider_name` | string | yes | Provider used, as named in [corridors](corridors.md) |
| `provider_rpw_id` | number | no | The RPW service id when the user picked one from the comparison |
| `send_amount`, `send_currency` | number, string | yes | What left the user's account |
| `receive_amount`, `receive_currency` | number, string | yes | What arrived |
| `fee` | number | no | Fee paid, in `send_currency` |
| `fx_rate_applied` | number | no | Rate the provider used. **Reserved: nothing writes it.** The comparison result carries the provider's margin (`fx_margin_pct`) and the mid-market rate, not the rate it applied (NF-HR-013 checked the code) |
| `mid_market_rate` | number | no | Mid-market rate at the time, from [rates_cache](rates_cache.md). Lets the profile compute what the transfer really cost. |
| `cost_pct` | number | no | True total cost as a percentage of the amount sent |

**Example** — `users/uid_priya_demo/transfers/t_01`

```json
{
  "entry_date": "2026-09-26",
  "corridor_id": "SG-IN",
  "provider_name": "Wise",
  "send_amount": 400,
  "send_currency": "SGD",
  "receive_amount": 25650,
  "receive_currency": "INR",
  "fee": 3.5,
  "mid_market_rate": 64.9,
  "cost_pct": 1.2,
  "source": "remittance_log",
  "created_at": "2026-09-26T13:00:00Z",
  "updated_at": "2026-09-26T13:00:00Z",
  "schema_version": 1
}
```

Values are illustrative.

## `users/{uid}/income/{id}`

| Field | Type | Required | Description |
|---|---|---|---|
| `amount`, `currency` | number, string | yes | Amount received |
| `category` | string | yes | For income the category is required and says what kind of income it is: `salary`, `overtime`, `bonus`, `other_income` |
| `employer_name` | string | no | Who paid |
| `verified` | boolean | yes | `true` only for income backed by an analysed contract (`source: contract`, NF-P3-024). It feeds the "verified employment" line of the narrative. |
| `salary_period` | string | when `source: contract` and the contract states one | `month`, `week`, `day` or `hour`: what `amount` is stated per. `amount` stays as the contract reads it (the PDF prints it with this period) |
| `monthly_amount` | number or null | when `source: contract` | What the salary comes to in a month: `amount` for a month or no stated period, `amount × 52 / 12` for a week, **null** for an hour or a day (the contract does not say how many). The score reads this instead of `amount`; a null is left out of the money metrics. Entries written before 2026-10-13 lack it and count as written |
| `contract_ref` | string | when `source: contract` | Contract id in `users/{uid}/contracts`. What `verified_employment` is built from. One contract salary per calendar month: a second contract checked in the same month replaces the first (entries written before 2026-10-01 lack the field and are repaired when the profile is recomputed) |

**Example** — `users/uid_priya_demo/income/i_01`

```json
{
  "entry_date": "2026-09-25",
  "amount": 650,
  "currency": "SGD",
  "employer_name": "Example Household",
  "verified": false,
  "category": "salary",
  "category_source": "user",
  "source": "manual",
  "created_at": "2026-09-25T18:00:00Z",
  "updated_at": "2026-09-25T18:00:00Z",
  "schema_version": 1
}
```

## `users/{uid}/bills/{id}`

Created manually, or from a bill photo read by Gemini Vision (NF-P3-011).

| Field | Type | Required | Description |
|---|---|---|---|
| `amount`, `currency` | number, string | yes | Amount of the bill |
| `vendor` | string | no | Who billed |
| `bill_date` | string (date) | no | Date printed on the bill |
| `paid` | boolean | yes | Whether it was paid. Bill-payment reliability counts paid bills. |
| `image_path` | string | no | Cloud Storage path of the photo |
| `extraction` | map | when `bill_ocr` | `{ "confidence": number, "model": string, "prompt_version": number }` |

`entry_date` is the day the bill was paid, or the day it was logged if unpaid.

A bill from `POST /fib/bill/scan` (`source: bill_ocr`) is stored with the category Gemini suggested and `category_source: model`, but without `category_confidence`: the confidence in `extraction` covers amount and currency only. NF-P3-012 sets `category_confidence` when it categorizes.

`POST /fib/categorize` (NF-P3-012) fills `category`, `category_source: model` and `category_confidence` on income and bill entries that have no category, or whose model category has no confidence. It never changes `category_source: user`.

**Example** — `users/uid_priya_demo/bills/b_01`

```json
{
  "entry_date": "2026-09-24",
  "amount": 38.5,
  "currency": "SGD",
  "vendor": "Example Telecom",
  "bill_date": "2026-09-20",
  "paid": true,
  "image_path": "bills/uid_priya_demo/b_01/bill.jpg",
  "extraction": { "confidence": 0.94, "model": "gemini-3.5-flash-lite", "prompt_version": 1 },
  "category": "phone_internet",
  "category_source": "model",
  "category_confidence": 0.97,
  "source": "bill_ocr",
  "created_at": "2026-09-24T17:20:00Z",
  "updated_at": "2026-09-24T17:20:00Z",
  "schema_version": 1
}
```

## `users/{uid}/savings/{id}`

| Field | Type | Required | Description |
|---|---|---|---|
| `amount`, `currency` | number, string | yes | Amount, always positive |
| `direction` | string | yes | `deposit` or `withdrawal` |
| `account_type` | string | no | `cash`, `bank`, `mobile_wallet`, `other` |

**Example** — `users/uid_priya_demo/savings/s_01`

```json
{
  "entry_date": "2026-09-25",
  "amount": 120,
  "currency": "SGD",
  "direction": "deposit",
  "account_type": "bank",
  "source": "manual",
  "created_at": "2026-09-25T18:05:00Z",
  "updated_at": "2026-09-25T18:05:00Z",
  "schema_version": 1
}
```

## `users/{uid}/financial_profile/current`

The result of the weekly recompute (NF-P3-013). There is exactly one document per user, overwritten each time. Do not append.

| Field | Type | Required | Description |
|---|---|---|---|
| `reporting_currency` | string | yes | Currency all totals are expressed in: the user's home currency, converted with the latest `rates_cache` rate. Where no rate exists (only the six corridor pairs are cached) it is the currency the worker uses most, and entries in other currencies are left out and counted in each metric's `detail.excluded_entries`. |
| `period_start`, `period_end` | string (date) | yes | The range the metrics cover: the earliest entry in the window to the day of the recompute. The window is the current month and the 11 before it. |
| `months_of_data` | number | yes | |
| `entry_counts` | map | yes | Entries used: `{ "income": n, "transfers": n, "bills": n, "savings": n }` |
| `metrics` | map | yes | The four original design metrics, each `{ "score": 0 to 100 or null, "detail": {...} }`: `income_stability`, `savings_rate`, `remittance_consistency`, `bill_payment_reliability`. `score` is `null` (with `detail.reason`) when there is no data for it, never 0. Formulas and `detail` fields: `docs/runbooks/NF-P3-013-fib-weekly-recompute.md`. |
| `overall_score` | number | yes | 0 to 100. The plain average of the metrics whose `score` is not `null`. |
| `narrative` | map | yes | `{ "language": "en", "text": "...", "model": "...", "activity_text": "..." }`: the report text from the reasoning tier. `activity_text` (NF-HR-001) is present only when the worker shares Coach or scam activity: a short paragraph in the same language that states the signals, kept only if every number in it is one of theirs. It is a separate field so that it can be left out of a report without rewriting `text`. |
| `verified_employment` | array of map | no | From analysed contracts: `{ "employer_name", "salary_amount", "salary_currency", "salary_period"?, "contract_ref" }` |
| `latest_export` | map | no | The last PDF (NF-P3-014): `{ "storage_path": "...", "created_at": ..., "signals": ["coach", "scam"] }`. `signals` (NF-HR-001) is present only when the PDF printed shared Coach or scam activity; a link to it is refused once the worker stops sharing that activity. Download links are signed URLs made on request, never stored. The recompute carries this field over when it overwrites the document. Written by `POST /fib/report/export`, which also deletes the file the previous `storage_path` pointed to. |
| `goals` | map | no | **Future Scope (NF-FC-015).** Targets from the worker's Coach plan: `{ "plan_id", "savings_rate_target_pct": number, "remittance": { "amount", "currency", "cadence": "weekly", "fortnightly" or "monthly" }, "emergency_fund_target": { "amount", "currency" }, "set_at": timestamp }`. Written when a plan is created (`savings_rate_target_pct` is the plan's emergency saving over its income, the rest is the plan's own figures), and **carried over when the recompute overwrites the document**, like `latest_export`. A profile built after the plan has no goals to carry, so the recompute takes them from the worker's newest plan (NF-FC-015). The metrics are compared against it by NF-HR-001. |
| `coach_signal` | map | no | **Future Scope (NF-HR-001), opt-in.** What the worker's Coach check-in answers say: `{ "plan_id", "checkins_answered": 1 to 3, "remittance_on_track", "savings_on_track", "pay_on_time" (counts of those answers, out of `checkins_answered`), "last_checkin_at": timestamp, "savings_rate_target_pct", "savings_rate_recorded_pct" }`. The last two are the plan's own target (`goals`) and the savings metric's rate over the profile's period, side by side with no verdict; both are left out when either is unknown. Numbers and dates only: the answers are fixed choices, never what a worker typed. **Written only when `users/{uid}.signal_sharing.coach` is `true`, the `coach` flag is on for the worker and at least one check-in is answered.** Not carried over: the recompute replaces the document, so it is gone at the next recompute once sharing is turned off, and **the export reads the choice itself** so it never prints a signal that is no longer shared. |
| `scam_signal` | map | no | **Future Scope (NF-HR-001), opt-in.** `{ "window_days": 90, "checks": n, "scams_found": n, "last_check_at": timestamp }`: how many distinct messages the worker had checked in the last 90 days and how many were flagged as scams. Never message text, indicators or types. Same opt-in, flag and removal rule as `coach_signal`, with `signal_sharing.scam` and the `scam` flag; written only when there is at least one check. |
| `prompt_versions` | map | yes | Prompt versions used |
| `computed_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Example** — `users/uid_priya_demo/financial_profile/current`

```json
{
  "reporting_currency": "INR",
  "period_start": "2026-04-01",
  "period_end": "2026-09-25",
  "months_of_data": 6,
  "entry_counts": { "income": 6, "transfers": 6, "bills": 12, "savings": 4 },
  "metrics": {
    "income_stability": { "score": 82, "detail": {} },
    "savings_rate": { "score": 64, "detail": {} },
    "remittance_consistency": { "score": 90, "detail": {} },
    "bill_payment_reliability": { "score": 95, "detail": {} }
  },
  "overall_score": 83,
  "narrative": { "language": "en", "text": "Example narrative.", "model": "gemini-3.5-flash" },
  "prompt_versions": { "fib.synthesize_narrative": 2 },
  "computed_at": "2026-09-26T02:00:00Z",
  "schema_version": 1
}
```

Scores and text are illustrative.

## Access and indexes

- **Access:** the owner reads all of these; only the backend writes them.
- **Indexes:** none beyond the automatic single-field ones. Timeline queries use a date range on `entry_date` within one user's subcollection, which the automatic index serves.
- **Volume:** a demo user with 6 months of activity (NF-P3-015) is a few dozen entries, so the weekly recompute reads them all in one pass.

## Tasks that use it

NF-P2-017 (transfer log), NF-P3-010 (activity endpoints), NF-P3-011 (bill OCR), NF-P3-012 (categorization), NF-P3-013 (weekly recompute), NF-P3-014 and NF-P3-018 (PDF export), NF-P3-015 and NF-P3-021 (demo users), NF-P3-016 and NF-P3-017 (UI), NF-P3-024 (contract income).
