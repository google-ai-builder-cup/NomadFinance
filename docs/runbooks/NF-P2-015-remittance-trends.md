# NF-P2-015 — Remittance: Historical Trends Endpoint

## Summary

`GET /api/v1/remittance/trends` returns a corridor's mid-market exchange rate over time for the trend chart (NF-P2-020): one value per market day, a summary, and the weekday that is usually best to send on. That's the design doc's "Send on Wednesday, rates are consistently 0.3% better". These are steps 4 and 7 of the Remittance X-Ray pipeline. No Gemini call.

- **One Firestore read per request.** The history lives as a `daily` map on the existing `rates_history/{pair}` header, about 255 entries a year. The cron now adds each day to it, and the header write became a merge. Reading a year of 2-hourly points would have cost about 4,400 reads per request.
- **History from day one (D-36).** `data-scripts/src/loaders/frankfurter_backfill.py` (was a stub) fills the map with the European Central Bank's daily rates from Frankfurter, which is the cron's own first source. It never overwrites a day already stored.
- **A best day only when the data supports one.** Each day is compared with its own week's average over the last 52 weeks. A weekday is named only with at least 8 weeks, a lead of at least 0.05 %, and in more than half of the weeks. Otherwise `best_day` is null with a reason.
  - On real 2025-09 to 2026-09 data that names Wednesday for AU-IN and Thursday for MY-ID.
  - The other four corridors have no clear pattern.
- No new package, no new environment variable, no rule change, no shared file changed.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/remittance_trends.py` (new) | `TrendDays` (30/90/180/365), `RemittanceTrends`, `TrendPoint`, `TrendSummary`, `WeekdayStat` |
| `backend/app/services/remittance/trends.py` (was a stub) | `daily_rates()`, `summarize()`, `weekday_stats()`, `best_day()`, `build_trends()`, `get_trends()` |
| `backend/app/api/v1/remittance.py` | `GET /remittance/trends` |
| `backend/app/repositories/rate_repo.py` | `get_history()`; `save_pair()` merges `daily.{rate_date}` into the header |
| `data-scripts/src/loaders/frankfurter_backfill.py` (was a stub) | The backfill: fetch per base currency, add missing days, `--dry-run`, `--days`, `--end`, `--only` |
| `backend/tests/unit/services/test_remittance_trends.py` (new) | 19 tests: damaged entries, period, summary, too few weeks, a real weekday effect on a falling trend, a trend alone (no false tip), weekends, short weeks, 52-week window, all 6 corridors |
| `backend/tests/integration/api/test_remittance_trends.py` (new) | 14 endpoint tests: answer, each period, 422s before any read, 404, short history, 401, OpenAPI |
| `backend/tests/integration/repositories/test_rate_repository.py` | 2 emulator tests: the map keeps every day across runs, a weekend run rewrites Friday, an undated rate uses the run's day; `get_history` of a missing pair |
| `data-scripts/tests/test_frankfurter_backfill.py` (new) | 10 tests: pairs from the corridors, missing days only, bad rates refused, the cron's days kept, re-run adds nothing, dry run never opens Firestore, bad arguments |
| `docs/api/endpoints.md` | The endpoint, with a real example |
| `docs/data-model/collections/rates_cache.md`, `firestore-schema.md` | The header's `daily` map; the backfill writes the map, not `T00` points |
| `docs/pipelines/remittance-xray.md`, `data-scripts/README.md`, `docs/deferred-items.md` | Steps 4 and 7 done; backfill usage; D-36 done, D-35 note, D-64, D-65 new |

## Decisions

1. **A daily map on the header, not points.**
   - Frankfurter publishes one ECB rate per working day, so the cron's 12 points a day are mostly the same number, and weekends repeat Friday.
   - One entry per market day, keyed by the provider's own `rate_date`, is the real resolution. A year is one read, well under Firestore's document limits (see `rates_cache.md` for when to add an index exemption). No cache is needed.
   - The hourly points are still written, for audit.
2. **The backfill writes the map, not `T00` points** as the data model first proposed. Points would add 1,500 writes that nothing reads.
3. **Never overwrite a stored day.** The cron's value wins over the backfill (it may come from the failover provider), and a re-run changes nothing.
4. **Best day against its own week.** Over the year every pair moved 2 to 16 %. On raw averages, the last weekday of a rising week always looks best.
   - The thresholds (8 weeks, 0.05 %, more than half the weeks) keep a noise-level difference from becoming advice.
   - The unit test "a steady trend alone does not make a best day" checks this.
5. **Market dates, not local time.** The weekday is that of the rate's date (the ECB's day), not the worker's own time zone. The difference is at most a few hours at the edges of a day.
6. **`days` is an `IntEnum`.** A query string arrives as `"90"`, which a `Literal[30, 90, 180, 365]` rejects. The enum accepts it and still lists the four values in OpenAPI.
7. **The best day ignores `days`.** It always uses the last 52 weeks, so switching the chart period never changes the advice.

## Flow

```
GET /api/v1/remittance/trends?corridor_id=AU-IN&days=90
  token (401) → corridor_id, days validated (422)
  pair_for_corridor → rates_history/AUD_INR (one read) → daily map → sorted days   (404 if empty)
  points: days in the last 90 → summary
  last 52 weeks, Mon–Fri, weeks with ≥ 3 days → each day vs its week's average → weekday stats
  best_day if ≥ 8 weeks and top weekday ≥ 0.05 % and beats its week > 50 % → else reason
  → RemittanceTrends

cron (every 2 h): rates_cache/{pair} + rates_history/{pair} (merge daily.{rate_date}) + points/{hour}
backfill (once): Frankfurter /v1/{start}..{end}?base=AUD&symbols=INR,PHP → daily.{day} where missing
```

## All commands, in order

### 1. Backend checks (from `backend/`, virtual environment active)

```bash
ruff check .
black --check .
mypy app tests
python -m pytest -q
```

As on CI, without Google credentials (Git Bash):

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent CLOUDSDK_CONFIG=/tmp/empty APPDATA=/tmp/empty python -m pytest -q
```

### 2. data-scripts checks (from `data-scripts/`, its own virtual environment)

```bash
pip install -r requirements-dev.txt
ruff check .
black --check .
mypy src tests
pytest -q
```

### 3. On the emulator: repository tests, backfill, live endpoint

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

Terminal 2, from `backend/`, the repository tests (Git Bash):

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m pytest tests/integration/repositories -q
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m pytest tests/integration/repositories -q
```

Then the backfill **into the emulator**, from `data-scripts/`. Both variables must be set, so nothing can reach production:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.frankfurter_backfill --dry-run
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.frankfurter_backfill
```

PowerShell (after setting the two variables as above):

```powershell
python -m src.loaders.frankfurter_backfill --dry-run
python -m src.loaders.frankfurter_backfill
```

Expect about 255 days added per pair; run it again and expect 0 added.

Terminal 3, the API against the emulators, from `backend/`:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 FIREBASE_PROJECT_ID=demo-nomadfinance GCLOUD_PROJECT=demo-nomadfinance uvicorn app.main:app --port 8080
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
$env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GCLOUD_PROJECT = "demo-nomadfinance"
uvicorn app.main:app --port 8080
```

Get an emulator test token and call the endpoint (Git Bash):

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-key" -H "Content-Type: application/json" -d '{"returnSecureToken":true}' | python -c "import sys,json;print(json.load(sys.stdin)['idToken'])")
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8080/api/v1/remittance/trends?corridor_id=AU-IN&days=30"
```

PowerShell:

```powershell
$token = (Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:9099/identitytoolkit.googleapis.com/v1/accounts:signUp?key=demo-key" -ContentType "application/json" -Body '{"returnSecureToken":true}').idToken
Invoke-RestMethod -Headers @{ Authorization = "Bearer $token" } -Uri "http://127.0.0.1:8080/api/v1/remittance/trends?corridor_id=AU-IN&days=30"
```

Or open http://127.0.0.1:8080/docs, press **Authorize** with the token and try `GET /api/v1/remittance/trends`.

### 4. Production, after the PR is merged and deployed (D-64)

The backend deploy workflow ships the endpoint and the new cron write. Then fill the history once, from `data-scripts/`, with Application Default Credentials that can write to `nomadfinance-prod`. Check first that `FIRESTORE_EMULATOR_HOST` is **not** set:

```bash
python -m src.loaders.frankfurter_backfill --dry-run
python -m src.loaders.frankfurter_backfill
```

Then, signed in to the live app, or with a real ID token:

```bash
curl -s -H "Authorization: Bearer $TOKEN" "https://nomadfinance-api-azewstzfaa-el.a.run.app/api/v1/remittance/trends?corridor_id=SG-PH&days=365"
```

Expect `200`, about 255 points, `weeks_analysed: 52`. After the next cron run (every 2 hours), `last_date` is today's or the last working day's date.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| Backend `ruff check .`, `black --check .`, `mypy app tests` | Pass (180 files) |
| Backend `pytest -q`, with and without Google credentials | 535 passed, 44 skipped (opt-in live and emulator tests) |
| Repository tests on the Firestore emulator | 15 passed |
| A test can fail | With the header write back to a plain `set` (no merge), exactly the daily-map test failed |
| data-scripts `ruff`, `black --check`, `mypy src tests` | Pass (25 files) |
| data-scripts `pytest -q` | 127 passed (10 new) |

**Live on the emulator, real Frankfurter data:**
- **Backfill.** Dry run: 255 days per pair (2025-09-28 to 2026-09-28). Run: 255 added per pair. Re-run: 0 added, 255 kept.
  - A later run after the repository tests had written cron days kept those 2 days: "253 added, 2 already stored".
- **Endpoint, all 6 corridors, 90 and 365 days:** all `200`.
  - About 30 ms each; the first call after start was 1.5 s.
  - 64 points for 90 days, 255 for 365.
  - `weeks_analysed` 52, `providers` `["frankfurter"]`.

| Corridor | 365-day change | Best day |
|---|---|---|
| SG-PH | +8.48 % | no clear pattern |
| SG-IN | +9.23 % | no clear pattern |
| AU-IN | +15.73 % | Wednesday, +0.085 %, 65 % of weeks |
| MY-ID | +11.32 % | Thursday, +0.079 %, 66 % of weeks |
| JP-PH | +1.85 % | no clear pattern |
| AU-PH | +14.94 % | no clear pattern |

- **Defaults and errors:** default `days` 90; `days=60` → 422; `corridor_id=UAE-IN` → 422; no token → 401.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 404 "No rate history is available yet" | The pair's header has no `daily` map: run the backfill (step 4), or wait for the cron's next run |
| `best_day_reason: not_enough_history` | Fewer than 8 weeks with at least 3 market days in the last 52 weeks: run the backfill |
| `best_day_reason: no_clear_pattern` | Normal for most corridors: no weekday is reliably better. Say so in the app; don't invent a tip |
| `last_date` is days old | The cron has stopped (check the Cloud Scheduler job `refresh-rates`), or a long holiday with no ECB rates |
| `days=60` → 422 | Only 30, 90, 180 and 365 are offered |
| Backfill `HTTPError` / `URLError` | No internet access, or Frankfurter is down; nothing was written for that base currency, run again later |
| Backfill writes to production by mistake | It uses the same Firestore client as every loader: `FIRESTORE_EMULATOR_HOST` and `FIREBASE_PROJECT_ID=demo-nomadfinance` must both be set for the emulator |
| Repository tests fail on a used emulator | Earlier data (a backfill, a live run) is still there. Restart the emulator, or clear it: `curl -X DELETE "http://127.0.0.1:8085/emulator/v1/projects/demo-nomadfinance/databases/(default)/documents"` |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with Pydantic request/response models (`TrendDays`, `RemittanceTrends`)
- [x] Firebase Auth token verification (401 without a token)
- [x] Structured logging with request id, hashed user, timing (middleware). The endpoint logs `remittance_trends corridor=... days=... points=... weeks=... best_day=...`, no personal data
- [x] Error handling with specific HTTP codes: 401, 404, 422, 429; no stack traces
- [x] Manual test: live HTTP calls on the emulator for all 6 corridors (Swagger `/docs` lists the endpoint; same calls)
- [x] OpenAPI documented (checked by a test: responses, required `corridor_id`, default `days`)
- [x] `docs/api/endpoints.md` updated

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Pranjal (NF-P2-020, trend chart):**
  - Call `GET /api/v1/remittance/trends?corridor_id=...&days=...` and plot `points` (`date`, `rate`). Higher is better for the worker.
  - Offer 30/90/180/365.
  - Show the best-day badge only when `best_day` is not null. Otherwise say there is no reliable best day (`best_day_reason`).
  - Show "Rates by Exchange Rate API" when `providers` contains `exchangerate_api` (D-35). The ECB/Frankfurter data needs no attribution.
- **Pranjal (NF-P2-016, recommendation):** pass `best_day` or its reason to the prompt; the prompt must not claim a best day when it is null.
- **Devam (NF-P2-022, savings):** use `RateRepository.get_history()` and `trends.daily_rates()` for the daily series, and `engine._terms()` for the costs.
- **Everyone:** after merge, D-64 fills production's history once. Until the cron runs after the deploy, trends answers 404 in production.

## Commit and PR for this task

Branch: `feature/remittance-trends` (already checked out).

```bash
git add backend/app backend/tests data-scripts docs
git status
```

```bash
git commit -m "feat(remittance): add rate trends with best day and ECB backfill" -m "Refs: NF-P2-015"
```

PR title: `feat(remittance): historical rate trends, best day to send, ECB history backfill (NF-P2-015)`

## Not covered here

- The trend chart and best-day badge (NF-P2-020), the savings calculator (NF-P2-022), the recommendation text (NF-P2-016)
- Running the backfill in production (D-64, after merge)
- Regenerating `docs/api/openapi.json` (D-65)
