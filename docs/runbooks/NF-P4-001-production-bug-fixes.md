# NF-P4-001 — Production bug fixes (2026-10-01)

## Summary

A test with a new user on the production site found four bugs, and a review listed six more gaps. All ten are fixed here, except where production is missing data, which needs one-time commands after the merge (step 4).

| # | What the team saw | Root cause (evidence) | Fix |
|---|---|---|---|
| 1 | Radar alerts never show, even after forcing the scheduler and adding indexes | The alert job's per-corridor query (`corridor_id ==` + `created_at >=`) needs `created_at` **ascending**; our docs said descending, so the index created by hand never matched. Cloud Run logs: `radar_surge_detection_failed` on all 6 corridors, every run since at least 2026-09-30, including the forced runs, `created=0` | The job reads two weeks of reports with **one** `created_at` range (the automatic index serves it) and splits them per corridor itself |
| 1b | (same) | The Alerts page showed only the worker's notifications, which are written **once, when an alert is created**, to the workers subscribed at that moment. A new user never sees an alert that already exists | The page also reads the **active alerts on the worker's routes** (`radar_alerts/{corridor}/current`) |
| 1c / review 5 | Employer and contract-based reports never alert | Those reports carry a host country, not a route; the job counted reports by route only (NF-P3-004 decision 8) | A report with only a `host_country` counts on **every corridor from that country** |
| 2 | Rate history chart is the same for 1M, 3M, 1Y | Not the chart: production has 3–4 days of history (logs: `remittance_trends ... days=365 points=4`). The one-time ECB backfill (D-64) was never run there | Run the backfill (step 4). The chart now says when the history starts after the chosen period |
| 3 | Complaint letter never shows | `complaint_templates` is **empty in production** (only ever loaded into the emulator). Logs: `pipeline_letter_skipped reason=no_template` for SG, HK, JP. A missing template was treated as final, so the letter was never retried | Load the templates (step 4). A missing template is now "pending"; a report with an unlawful clause and no letter shows **"Write the letter"**, which writes only the letter |
| 4 / review 1 | "Verified employment" never appears | The contract income entry was saved without `contract_ref`; the profile builder only lists entries that have it | The entry stores `contract_ref`; older entries are repaired when the profile is recomputed |
| review 6 | Two contracts add two salaries in one month (income stability 64, not ~95) | Each analysed contract logged its own salary, dated today | One contract salary per calendar month: the newest replaces the others (on write, and on read for old data) |
| review 4 | The "best" provider can be a flagged one | `radar_to_remittance.py` was empty; the recommender always named the top-ranked provider | `/compare` marks `flagged` providers (rank unchanged); the recommendation names the best **unflagged** one (prompt `recommend.v2`) |
| review 2 | Recommendation and bill categorize have no screen | Endpoints only | **"Get advice"** card on the remittance page; **"Sort my bills"** card on the Financial Identity dashboard |
| review 3 | No contract history | `ContractList.tsx`, `ContractReport.tsx` were empty and unrouted | `/contract/history` lists every check; `/contract/:id` reopens a report. Links from the upload page and the dashboard widget |

No new package, no new environment variable, no security-rule change. One shared-file change is proposed, not made (D-68).

### Follow-up the same day: why a letter is pending

In production, pressing **Write the letter** answered "could not be written yet. Please try again in a few minutes." The logs showed `pipeline_letter_pending reason=GeminiRateLimitError` after `429 RESOURCE_EXHAUSTED ... exceeded your current quota` on `gemini-3.5-flash`: the free tier's **daily** quota was used up, so "a few minutes" was wrong.

- `GeminiRateLimitError.daily` is read from the quota id in the 429's details (`...PerDay...`); only the quota ids are read, never the rest of the response.
- The letter step returns a reason (`ai_daily_limit`, `ai_busy`, `ai_failed`, `no_template`), stored on the contract as `complaint_pending_reason` and returned by analyze.
- The report's letter box words each reason ("used up today's limit … try again tomorrow", "busy … a few minutes", …) in the six languages.

Fix for the quota itself: wait for the reset (midnight Pacific, 07:00 UTC) or enable billing on the Gemini key (D-58, D-13).

## Files

| File | Change |
|---|---|
| `backend/app/repositories/radar_repo.py` | `reports_since(since)`: one range on `created_at`; `flagged_entities(type)` |
| `backend/app/services/radar/alerts.py` | One read for all corridors; `_on_corridor` (route, or host country); a failed read still expires alerts |
| `backend/app/services/contract/letter.py`, `pipeline.py`, `report_store.py`, `schemas/contract_pipeline.py` | Missing template → pending; `letter_missing` catches letters lost under the old rule; `complaint_pending_reason` |
| `backend/app/integrations/gemini/errors.py`, `client.py` | `GeminiRateLimitError.daily` from the 429's quota id |
| `backend/app/services/cross_pillar/contract_to_fib.py`, `repositories/fib_repo.py` | `contract_ref`; one contract salary per month; `delete_entry` |
| `backend/app/services/fib/profile_builder.py` | `_contract_income_once_a_month`: repairs old contract income when read |
| `backend/app/services/cross_pillar/radar_to_remittance.py` (was empty) | Flags providers from `radar_entities` (slug and aliases) |
| `backend/app/api/v1/remittance.py`, `schemas/remittance_compare.py` | `/compare` returns `flagged`, `flag_report_count` |
| `backend/app/services/remittance/recommender.py`, `prompts/remittance/recommend.v2.yaml` (v1 removed), `schemas/remittance_recommend.py`, `prompts/README.md` | `recommended_provider`: best-ranked unflagged |
| `backend/tests/...` | Alert job (country-only reports, one read, failed read), letter pending and recovery, contract income (ref, one per month, legacy repair), flags, recommender with flags, compare endpoint |
| `frontend/src/pages/radar/RadarAlerts.tsx`, `components/radar/RouteAlertItem.tsx` (new), `utils/alertRoutes.ts` (new) | Active alerts on the worker's routes, then the notification feed |
| `frontend/src/components/remittance/TrendChart.tsx`, `utils/trendHistory.ts` (new) | Short-history note |
| `frontend/src/components/remittance/RecommendationCard.tsx` (new), `pages/remittance/RemittanceCompare.tsx` | "Get advice" |
| `frontend/src/components/fib/CategorizeEntriesCard.tsx` (new), `utils/pendingCategories.ts` (new), `pages/fib/FIBDashboard.tsx` | "Sort my bills" |
| `frontend/src/pages/contract/ContractList.tsx`, `ContractReport.tsx` (were empty), `router.tsx`, `ContractUpload.tsx`, `components/dashboard/RecentContractsWidget.tsx` | Contract history |
| `frontend/src/components/contract/ReportCard.tsx`, `utils/letterPending.ts` (new) | "Write the letter" when a letter is missing, with the reason it is still pending |
| `frontend/src/services/*`, `hooks/*`, `types/*` | Reads and calls for the above |
| `frontend/src/i18n/{6 languages}.json` | 39 strings |
| `frontend/firestore.indexes.json` | The two composite indexes the code needs |
| `docs/...` | `firestore-schema.md` (indexes), `radar.md`, `contracts.md`, `fib.md`, `endpoints.md`, `contract-shield.md`, `remittance-xray.md`, NF-P3-004 and NF-P2-007 runbooks (superseded decisions), `deferred-items.md` (D-67 to D-71) |

## Decisions

1. **Remove the index dependency instead of creating the right index.** Two weeks of reports is a small read, and a query with no composite index cannot fail this way again. The two indexes still needed are now listed in `firestore.indexes.json` (D-68 to deploy them automatically).
2. **Employer reports alert on every route from their host country** (supersedes NF-P3-004 decision 8). A worker in Singapore needs the warning whichever country they send to. The cost: one employer surge makes one alert per route from that country (SG-PH and SG-IN).
3. **The Alerts page reads active alerts directly.** It shows the routes chosen in the profile, else the worker's own route, else every route from their host country (a worker from Nepal or Bangladesh has no surveyed route). Signed-in users could already read `radar_alerts`; no rule change. Alerts are worded in the app's language from the alert's own fields, not by Gemini.
4. **Missing template = pending.** All six host countries have a curated template, so "missing" can only mean "not loaded". A cached re-check also writes a letter for an analysis that has an unlawful clause but no letter, which is how contracts checked in production before this fix recover.
5. **One contract salary per month, newest wins.** A worker on a work permit has one employer. Old data is repaired when the weekly profile is built, so no migration script touches production.
6. **Flags change the advice, not the ranking.** The table stays a factual price ranking with the "Community flagged" badge; the recommendation names the best unflagged service and says why it passed over a flagged one.
7. **"Get advice" is on request,** not automatic. It is the page's one Gemini call, and the free tier's quota has run out during testing before (D-58).

## Flow (alerts after the fix)

```
every 6 h (or forced): POST /internal/aggregate-radar
  radar_reports where created_at >= now-14d           ← one query, automatic index
  for each of the 6 corridors:
    reports on the route, + reports with only host_country == the route's host
    window (7 d) vs baseline (7 d) per business → surge? → radar_alerts/{corridor}/current/{id} (active)
    notify workers subscribed now → users/{uid}/notifications
  expire alerts past expires_at
Alerts page
  routes = profile's chosen routes | own route | every route from the host country
  radar_alerts/{route}/current where status == active   ← shown to everyone on that route
  users/{uid}/notifications                             ← their own feed
```

## All commands, in order

### 1. Checks

From `backend/` (virtual environment active):

```bash
pip install -r requirements-dev.txt
ruff check .
black --check .
mypy app
python -m pytest -q
```

From `frontend/`:

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

On Windows: `pnpm.cmd`, and `prettier --check --end-of-line auto src`.

### 2. Repository tests on a clean emulator

Terminal 1, from `frontend/`: `firebase emulators:start --only auth,firestore --project demo-nomadfinance`. Then from `backend/` (Git Bash):

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m pytest tests/integration/repositories -q
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m pytest tests/integration/repositories -q
```

### 3. Try the fixes on the emulators

Keep the emulators running. From `data-scripts/`, with `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085` and `FIREBASE_PROJECT_ID=demo-nomadfinance` set (as in step 2):

```bash
python -m src.loaders.corridors
python -m src.loaders.ilo_natlex
python -m src.loaders.complaint_templates
python -m src.loaders.frankfurter_backfill --only SGD_PHP
```

Start the backend against the emulators (`uvicorn app.main:app --port 8080` with `FIRESTORE_EMULATOR_HOST`, `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`, `FIREBASE_PROJECT_ID`, `GCLOUD_PROJECT` = `demo-nomadfinance`) and the app (`pnpm dev --mode emulator`); open http://localhost:5173 and onboard as Singapore → Philippines.

- **Alerts:** report one business twice on Singapore → Philippines (Radar → Report), then run the job once from `backend/`:

  ```bash
  FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GCLOUD_PROJECT=demo-nomadfinance python -c "import asyncio; from datetime import UTC, datetime; from app.integrations.gemini import get_gemini_client; from app.repositories.base import get_firestore_client as c; from app.repositories.radar_repo import RadarRepository; from app.repositories.user_repo import UserRepository; from app.services.radar.alerts import run_aggregation; print(asyncio.run(run_aggregation(RadarRepository(c()), UserRepository(c()), get_gemini_client(), datetime.now(UTC))))"
  ```

  Radar → Alerts shows it under "Active on your routes", even after deleting the worker's notification in the Emulator UI.
- **Chart:** Remittance, Singapore → Philippines: 1M / 3M / 6M / 1Y show different days and axes. Singapore → India (no backfill) shows the "Rate history starts on …" note.
- **Letter:** delete `complaint_templates/SG` in the Emulator UI, check a Singapore contract, load the templates again, open it from **Past checks**, press **Write the letter**.
- **Advice:** in the Emulator UI, set `flagged: true` on the `radar_entities` document of the top-ranked provider, compare again, press **Get advice**: it recommends the next one and says why.

### 4. Production, after the PR is merged and deployed (D-67, D-64)

From `data-scripts/`, signed in with `gcloud auth application-default login` as an account that can write to `nomadfinance-prod`. First make sure the emulator variables are **not** set (PowerShell: `Remove-Item Env:FIRESTORE_EMULATOR_HOST -ErrorAction SilentlyContinue`; bash: `unset FIRESTORE_EMULATOR_HOST FIREBASE_PROJECT_ID`):

```bash
python -m src.loaders.complaint_templates --dry-run
python -m src.loaders.complaint_templates
python -m src.loaders.frankfurter_backfill --dry-run
python -m src.loaders.frankfurter_backfill
```

Expect 6 countries of templates, and about 255 days per pair. Then run the jobs once instead of waiting:

```bash
gcloud scheduler jobs run radar-aggregation --project nomadfinance-prod --location asia-south1
gcloud scheduler jobs run fib-recompute --project nomadfinance-prod --location asia-south1
```

And check the alert job's log line:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api" AND (jsonPayload.message:"radar_aggregation corridors" OR jsonPayload.message:"radar_surge_detection_failed" OR jsonPayload.message:"radar_reports_read_failed")' --project nomadfinance-prod --freshness=1h --limit 10 --format="value(timestamp,jsonPayload.message)"
```

Expect `radar_aggregation corridors=6 reports=N created=M ...` and **no** `radar_surge_detection_failed`. An alert appears only when one business has at least 2 reports on a route in the last 7 days, more than in the 7 days before.

Old contracts: open each from **Contracts → Past checks** and press **Write the letter** where it shows.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| Backend `ruff check .`, `black --check .`, `mypy app` | Pass |
| Backend `pytest -q` (with and without Google credentials) | 955 passed, 66 skipped (8 added for the pending reasons) |
| Repository tests on a cleared emulator | 19 passed (they fail on an emulator still holding live test data, which they read) |
| Frontend `tsc -b`, `pnpm lint`, `prettier --check` | Pass |
| Frontend `vitest run src`, `pnpm build` | 196 passed (21 files); build passes |
| A test can fail | With the host-country rule removed from `_on_corridor`, exactly `test_reports_naming_only_a_host_country_count_on_each_of_its_corridors` failed; the old letter test ("missing template is final") failed against the new rule before it was rewritten |

**Production evidence before the fix** (read-only: Cloud Run logs and one Firestore listing): every alert run since 2026-09-30 logged `radar_surge_detection_failed` on all six corridors and `created=0`; the decoded index request in the error asks for `corridor_id` ASC, `created_at` ASC, `__name__` ASC; trends returned 3–4 points for every period; `complaint_templates` had no documents while `labor_laws` had all six countries; letters logged `reason=no_template`.

**Live on the emulators, real Gemini:**
- **Alerts.** Seeded 3 Contract Shield reports about an SG employer (no route) and 2 worker reports about an SG-PH operator, ran the real job:
  - `corridors_scanned=6, alerts_created=3, notifications_sent=2`.
  - SG-PH: the operator ("Watch") and the employer ("Warning"). SG-IN: the employer.
  - The Alerts page showed both under "Active on your routes" plus the two Gemini notifications. After deleting the employer's notification it still showed the employer's alert (the new-user case).
- **Remittance.** SG-PH 645 SGD:
  - The flagged InstaReM stayed first with its badge.
  - **Get advice** answered in 4.2 s: "Send with Wise … Although InstaReM offers a slightly higher payout, it has been flagged by other users".
  - Chart with a year of history: 1M / 3M / 6M / 1Y gave 22 / 64 / 127 / 255 days and different Y axes. SG-IN with one stored day: the "Rate history starts on Oct 1, 2026" note on every period.
- **Contract.** With the SG template removed, a real check of `sample_contract_sg.pdf` completed:
  - The first attempt got Gemini 503 at the comparison; one retry succeeded.
  - Logs: `pipeline_letter_pending reason=no_template` and `contract_income_logged`. The income entry had `contract_ref`.
  - Template reloaded; **Past checks** listed the contract (Danger). It reopened with score 33 and the "Complaint letter … Write the letter" box.
  - One click: the letter to the Ministry of Manpower with "Download as PDF" and "Copy letter".
- **Verified employment.** The FIB recompute gave `verified_employment: [{employer_name: "Tan Wei Ming", salary_amount: 650, salary_currency: "SGD", contract_ref: …}]`.
- **Sort my bills.** One uncategorized bill seeded; the card showed it; one click → `fib_categorized categorized=1`, "Sorted: 1. Still to sort: 0."

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Alerts page still empty after the deploy | No business has 2+ reports on one route in 7 days, or the job has not run yet: force it (step 4) and read its log line. `radar_reports_read_failed` means Firestore was unreachable for that run |
| `radar_surge_detection_failed` after the deploy | The old revision is still serving: check the backend deploy workflow finished |
| Chart note "Rate history starts on …" in production | The backfill has not run (step 4) |
| "Write the letter" says "used up today's limit" | Gemini free-tier daily quota (429). Wait for 07:00 UTC or enable billing on the key |
| "Write the letter" says "busy" or "not available yet" | Gemini overloaded, or the templates not loaded (logs: `pipeline_letter_pending reason=...`) |
| No verified employment after a contract check | The profile is rebuilt weekly; force `fib-recompute` (step 4). Only an employment contract with a stated salary counts |
| "Get advice" says the AI service is busy | Gemini 503/429 (D-58); try again in a minute |

## Definition of Done

**Backend:**
- [x] Pydantic models (`flagged`, `flag_report_count` on `ProviderResult`)
- [x] Auth unchanged
- [x] Structured logs: `radar_aggregation ... reports=`, `radar_reports_read_failed`, `pipeline_letter_pending reason=no_template`, `contract_income_replaced`, `remittance_flagged`
- [x] Error handling: a failed Radar read leaves the comparison unflagged; a failed report read still expires alerts
- [x] Manual test: live on the emulators
- [x] `docs/api/endpoints.md` updated

**Frontend:**
- [x] shadcn/ui and Tailwind
- [x] Mobile: the reopened report and letter were checked at phone width
- [x] Loading and error states on every new card and page
- [x] i18n: 39 strings in 6 languages
- [x] Accessibility: headings, `aria-live` on new results, `role="alert"` errors
- [ ] Screenshots in the PR: yours to add
- [ ] Slow 3G: not run

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Everyone:** production needs step 4 once after the merge, or bugs 2 and 3 stay visible.
- **Pranjal:** `/recommend` now passes over flagged providers (`recommend.v2`, v1 removed). D-68 waits on your OK for the indexes deploy; D-71 is a test fake in your NF-P2-021 area.
- **Aditya:** the comparison table can use `provider.flagged` directly instead of a second Radar read (the badge still works as it is).
- **NF-P3-004 decision 8 is superseded:** employer and contract reports now alert on every route from their host country.

## Commit and PR

Branch: create it from this working tree **before** committing; the changes carry over:

```bash
git switch -c fix/production-bugs-alerts-letters-trends
```

```bash
git add backend docs frontend/src frontend/firestore.indexes.json
git status
```

```bash
git commit -m "fix(platform): fix radar alerts, letters, verified income, add screens" -m "Refs: NF-P4-001"
```

PR title: `fix(platform): production bugs — radar alerts, complaint letters, verified income, trends; missing screens (NF-P4-001)`

## Not covered here

- Deploying `firestore.indexes.json` automatically (D-68, shared files)
- Deleting the three unused production indexes (D-69)
- The 18 pre-existing test type errors (D-70) and the noisy test fake (D-71)
