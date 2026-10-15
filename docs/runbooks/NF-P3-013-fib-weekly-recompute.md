# NF-P3-013 — FIB: Weekly Profile Recompute

Assigned to Devam; built by Aditya.

## Summary

A Cloud Scheduler job (`fib-recompute`, Sundays 02:00 UTC) calls `POST /api/v1/internal/recompute-fib-profiles`. For each user with activity in the last 12 months the backend reads income, transfers, bills and savings, computes the four metrics, has the reasoning tier write the report text (prompt `fib/synthesize_narrative.v1`, v2 since NF-HR-001) in the worker's language, and overwrites `users/{uid}/financial_profile/current`. It is the "Financial Score Recompute" subgraph of `docs/mermaid/financial-identity-pipeline.mmd`.

PDF export (NF-P3-014), contract income writes (NF-P3-024), demo seed data (NF-P3-015, -021), a user-triggered recompute and the frontend are separate.

## Files

| File | Change |
|---|---|
| `backend/app/services/fib/profile_metrics.py` (new) | Pure functions: the four metrics, the overall score, the 12-month window |
| `backend/app/services/fib/narrative.py` (new) | The reasoning-tier call; turns a literal backslash-n into a line break (D-50) |
| `backend/app/services/fib/profile_builder.py` (was an empty stub) | `recompute_profile` (one user) and `recompute_all` (every user, 3 at a time) |
| `backend/app/schemas/fib_profile.py` (new) | `NarrativeAnswer` (the Gemini schema), `RecomputeResponse` |
| `backend/app/repositories/fib_repo.py` | `save_profile`, `get_profile` |
| `backend/app/repositories/user_repo.py` | `list_user_ids` (ids only) |
| `backend/app/api/v1/internal.py` | The endpoint |
| `backend/app/config.py`, `backend/.env.example` | `GEMINI_NARRATIVE_TIMEOUT_SECONDS` (default 90) |
| `infra/cloud-scheduler/fib-recompute.yaml` (was empty) | The weekly job |
| `docs/api/endpoints.md`, `docs/data-model/collections/fib.md` | Endpoint section; data-model notes; D-08 and D-50 |
| 5 new test files | Metrics, builder, repository, endpoint, and an opt-in live Gemini test |

No shared files touched. `firestore.rules` already lets the owner read `financial_profile`, and only the backend writes it.

## How each value is computed

Window: the current month and the 11 before it, entries dated up to today. `period_start` is the earliest entry in it, `months_of_data` the calendar months from there to today. A metric with no data has `score: null` and `detail.reason`, never 0, so an unlogged month does not read as bad behaviour. `overall_score` is the plain average of the scores that are not null.

| Metric | Score | `detail` |
|---|---|---|
| `income_stability` | 100 × (months with income ÷ months in period) × (1 − monthly variation, capped at 1). Variation is the standard deviation of monthly income over its mean. | `months_with_income`, `months_in_period`, `mean_monthly_income`, `monthly_variation`, `excluded_entries` |
| `savings_rate` | Net savings (deposits − withdrawals) ÷ income, against a 20% target: 20% or more saved scores 100, a negative net scores 0. | `income_total`, `net_savings`, `savings_rate`, `target_rate`, `excluded_entries` |
| `remittance_consistency` | 100 × (months with at least one transfer ÷ months from the first transfer to today) | `months_with_transfer`, `months_in_period`, `transfer_count`, `total_received`, `average_cost_pct`, `excluded_entries` |
| `bill_payment_reliability` | 100 × (paid bills ÷ all bills) | `bills_total`, `bills_paid`, `bills_unpaid` |

Each metric counts months from its own first entry, so starting to log late is not held against the worker. The running month is not counted as a miss until it has an entry (on the 5th, no salary yet means nothing). Savings rate has no score without savings entries (`no_savings_entries`): not logging savings is not the same as saving nothing.

Money is converted to `reporting_currency`: the home currency, with the latest `rates_cache` rate (not the rate of each entry's date). Only the six corridor pairs are cached, so if the worker's entries cannot be converted to their home currency (for example a home country of NP, or a host currency with no pair) the currency they use most is the reporting currency, and entries in other currencies are left out and counted in `excluded_entries`.

## Decisions

1. **Formulas and the 20% savings target are this project's own** (the original design names the four metrics, not how to compute them). Nothing is calibrated against lending outcomes. The constants are `SAVINGS_TARGET_RATE` and `WINDOW_MONTHS` in `profile_metrics.py`.
2. **The categorizer is not called here.** None of the four metrics uses a category.
3. **One user's failure is isolated.** If the narrative call fails (or an entry is corrupt), that user keeps last week's profile, is counted under `failed`, and the others still run. The endpoint always returns 200, like `aggregate-radar`: a scheduler retry would re-run, and re-pay for, every other user.
4. **What the narrative prompt sees:** period, metrics, entry counts, reporting currency and `income_verified_by_contract`. No overall score (the prompt forbids giving one) and no employer names or amounts of verified contracts.
5. **Verified employment** comes from income entries with `verified: true` and a `contract_ref` (NF-P3-024 is not merged, so none exist yet). It is stored as `verified_employment` and only flags the narrative.
6. **`latest_export` is carried over.** The profile is overwritten as a whole, but the PDF export (NF-P3-014) stores `latest_export` in the same document, so `save_profile` keeps it.
7. **Concurrency:** 3 users at a time, because the free tier's quota per model is small and a call takes 15 to 25 s. At that rate about 100 users fit in Cloud Run's 900 s request timeout (`deploy_manual.sh`). A larger user base needs the run split into batches.
8. **The recompute does not skip unchanged users.** It costs one reasoning call per active user per week.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (41 files) |
| `mypy app/` | Clean (129 files) |
| `pytest` (full suite) | 865 passed, 60 skipped (live-Gemini tests) |
| New: `test_fib_profile_metrics.py` (23) | The window; each formula with worked numbers, gaps, variation, conversion and exclusion, no-data reasons; the overall average |
| New: `test_fib_profile_builder.py` (12) | A stored profile as the data model describes; what the prompt sees; language and fallback; verified employment; currency fallback; bills-only user; no-activity and no-usable-metric users; a failed narrative keeps the old profile; D-50; a run where one user times out and one is corrupt |
| New: `test_fib_repo_profile.py` (4) | Path of the profile document; `latest_export` kept while the rest is replaced; `list_user_ids` reads ids only |
| New: `test_internal_recompute_fib.py` (3) | The endpoint, scheduler-only auth, hidden from `/docs` |
| New: `test_internal_recompute_fib_live.py` (3), `RUN_LIVE_GEMINI=1` | Real `gemini-3.5-flash` through the endpoint, two users at once. A 6-month history (one missed transfer month, one unpaid bill, savings every other month) in Hindi, 23.6 s; a 1-month history in English, 15.6 s; 24 s for both together. Both reports came back with the four metric paragraphs and a summary, only the given numbers (258,800 INR income, 9% savings rate, 5 of 6 bills paid), the small sample stated, no employer name, no literal backslash-n |

Not verified: a real Firestore read and write (the repository is tested with a mock client; the scheduler job itself, which exists only after merge), conversion against a real `rates_cache` document, and a run with more than a handful of users.

## Before merging

Merging a change under `infra/cloud-scheduler/` runs `.github/workflows/scheduler-deploy.yml`, which creates the real `fib-recompute` job. The backend with this endpoint must already be deployed, or the first Sunday run fails with 404. Run it by hand to fill the demo users' profiles (NF-P3-015, -021):

```bash
gcloud scheduler jobs run fib-recompute --project nomadfinance-prod --location asia-south1
```

## Manual test steps

The endpoint accepts only a Google OIDC token for the scheduler service account, so it is easiest to test through the scheduler job above, or locally with the live test (needs `GEMINI_API_KEY` in `.env.local`):

```bash
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_internal_recompute_fib_live.py -v -s
```

PowerShell: set `$env:RUN_LIVE_GEMINI = "1"` first, and `$env:PYTHONUTF8 = "1"` to print the Hindi report.

After a real run, `users/{uid}/financial_profile/current` in the Firestore console shows the four metrics, `overall_score`, `narrative` (in the user's `preferred_language`), `prompt_versions` and `computed_at`.
