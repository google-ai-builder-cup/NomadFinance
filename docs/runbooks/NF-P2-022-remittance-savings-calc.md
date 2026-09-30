# NF-P2-022 — Remittance X-Ray: Historical Savings Calculator

Owner in the tracker is Devam; built by Aditya (backend rotation swap).

## Summary

`GET /api/v1/remittance/savings` answers the design doc's "you would have saved $X" hero moment: what sending `amount` with the best comparable service, instead of the worst, would have been worth over real history. Step 8 of the Remittance X-Ray pipeline (`docs/pipelines/remittance-xray.md`), no Gemini call. Nothing is stored.

**What "savings" means here, and why.** The tracker (`.claude/tasks.md`) describes this as "vs mid-market"; the design doc (§2.1: *"If you'd used [best option] for the last 12 months, you'd have saved $X"*) and the pipeline doc's own step 8 (*"Historical savings against the worker's choice"*) describe a different comparison — best service against another one, not against the zero-cost mid-market rate. The two are genuinely different numbers (best-vs-mid-market is always a loss, since nothing beats a zero-cost benchmark; best-vs-worst is a real, positive, demo-friendly figure), so this was a stop-and-ask per the standing instructions rather than a judgment call. Resolved with the user: **best vs worst comparable service**, matching the design doc.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/remittance_savings.py` (new) | `MonthlySavings`, `RemittanceSavings` |
| `backend/app/services/remittance/savings.py` (new — the pipeline doc listed this step "not yet named") | `get_savings()`, `target_months()`, `monthly_averages()` |
| `backend/app/api/v1/remittance.py` | `GET /api/v1/remittance/savings` |
| `backend/tests/unit/services/test_remittance_savings.py` (new) | 12 tests |
| `backend/tests/integration/api/test_remittance_savings.py` (new) | 9 tests |
| `docs/api/endpoints.md`, `docs/pipelines/remittance-xray.md` | Endpoint; step 8 marked built |

`requirements*.txt`, `pyproject.toml`, `Dockerfile`, the workflows and `firestore.rules` are unchanged.

## Decisions

1. **Best vs worst, not best vs mid-market.** See "What savings means here" above. `total_savings = total_best_receives - total_worst_receives`, always ≥ 0.
2. **No live-rate read.** `calculate_comparison` needs a rate only to compute `recipient_receives`; a fixed `amount`'s total-cost percentage per service does not depend on which rate is used, so the ranking (which service is best/worst) and their `total_cost_pct` are identical whatever rate goes in. Passing `cached_rate=None` uses the survey's own median rate and skips a Firestore read `/compare` and `/trends` each still need for their own purposes. Reuses `calculate_comparison` (and, inside it, `engine._terms`) exactly as the pipeline doc asks, rather than recomputing costs a second way.
3. **Each full calendar month is priced at its own average rate**, not a single day. `trends.daily_rates()` (already built by NF-P2-015) is read as-is, not copied; `monthly_averages()` buckets it by `(year, month)` and takes `statistics.fmean`, the same aggregation `trends.summarize()` uses for its own `average`.
4. **The current, in-progress month is never included.** `target_months()` always starts from the month before `now`'s. A partial month (a handful of days averaged against full months elsewhere) would silently under- or over-state that one month for no good reason. Documented, the same as every other place this codebase declines to fake a precision it does not have (`stale`, `estimated`, `best_day_reason`).
5. **`months_used` can be less than `months_requested`**, reported rather than padded or silently truncated — the same transparency pattern as `RemittanceTrends.weeks_analysed`. `404` only when it would be zero (no month in range has any history), reusing `trends.HistoryNotFoundError` rather than a second exception class for the same condition.
6. **Rounding happens once, at the end of each month's raw math**, and the totals are summed from the *unrounded* per-month figures, not from the rounded display values — the same reasoning as `engine._rounded()` (round after the sums are done, not before), so a 12-month total is never off by a few cents from rounding twice.
7. **`months` bounded 1 to 12** (`MIN_MONTHS`/`MAX_MONTHS` in `savings.py`), enforced by the query parameter itself (`Query(ge=1, le=12)`), a plain 422 before any Firestore read. 12 matches the design doc's own "last 12 months" example and is also about as far back as the backfilled history reasonably reaches.
8. **`survey` is echoed from the comparison** so the World Bank attribution can be shown wherever `total_savings` is, the same requirement `/compare` and `/trends` already carry.

## Flow

```
GET /api/v1/remittance/savings?corridor_id=&amount=&months=
  auth (401), months bounded 1..12, amount > 0 (422)
  get_savings(corridor_id, amount, months, corridors, rates, now)      [services/remittance/savings.py]
    └─ corridors.get_corridor(corridor_id)                              404 if not loaded
    └─ calculate_comparison(corridor_id, corridor, amount, None, now)   [engine.py, reused as-is]
         → best/worst comparable service + total_cost_pct              422 if amount out of range
    └─ rates.get_history(pair_id) → trends.daily_rates()                404 if nothing stored
    └─ target_months(now, months)                                      last N full months, oldest first
    └─ monthly_averages(history, target_months)                        fmean per month              404 if none of them has data
    └─ per month: best_receives / worst_receives / savings, from the fixed pcts × that month's rate
  200 {..., months_requested, months_used, best_firm, worst_firm,
       total_best_receives, total_worst_receives, total_savings, months[], survey}
```

## All commands, in order

From `backend/` with the virtual environment active.

### 1. Checks (the same ones CI runs, plus tests in mypy)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
docker build --platform linux/amd64 -t nomadfinance-backend:ci .
```

### 2. Try the endpoint by hand

Start the API, get a Firebase ID token as in the NF-P2-001 runbook, then call it directly (no prior `/compare` call needed — unlike `/recommend` and `/log`, this endpoint takes only `corridor_id`, `amount` and `months`).

```powershell
# Windows PowerShell
Invoke-RestMethod -Headers @{ Authorization = "Bearer $Token" } `
  "http://127.0.0.1:8080/api/v1/remittance/savings?corridor_id=SG-PH&amount=500&months=6"
```

```bash
# bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/remittance/savings?corridor_id=SG-PH&amount=500&months=6"
```

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Pass (192 files unchanged plus the new ones) |
| `mypy app`, `mypy app tests` | Pass (118 / 191 source files) |
| `pytest -q`, with and without Google credentials | 599 passed, 47 skipped (opt-in live and emulator tests) |
| New tests | 12 service (including hand-computed month-by-month savings), 9 endpoint |
| `docker build --platform linux/amd64 -t nomadfinance-backend:ci .` | **Not run**: Docker daemon not running on this machine this time. `Dockerfile` and `requirements.txt` are unchanged; NF-P2-014 already built and smoke-tested an image from the same `Dockerfile` |
| Manual Swagger try-out with a real token | Not run this session — do before merging |

Whether real backfilled `rates_history` in the dev/prod Firestore actually reaches back a full 12 months was not checked here (no emulator or live Firestore access this session); the NF-P2-015 runbook's verified results show data from about 2025-09 onward, so `months=12` should mostly succeed but `months_used` may come back lower for a corridor whose backfill started later. Worth a quick real check before the demo.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `months_used` is less than `months_requested` | The history does not reach back that far; not an error, just fewer months priced. Check `/trends`'s `last_date` for the same corridor |
| 404 `No rate history is available yet` | No month in the requested window has data — either the corridor's backfill never ran, or `months` reaches further back than the history goes |
| `total_savings` is `0` | The corridor has only one comparable service (best == worst): expected, not a bug |
| Numbers do not match a manual `/compare` calculation | `/savings` uses each historical month's **average** rate, not `/compare`'s live rate — the two are expected to differ |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with a Pydantic response model (no request body: a `GET`)
- [x] Firebase Auth token verification (`Depends(get_current_user)`)
- [x] Structured logging with request ID, user ID (hashed), timing — from NF-P1-028, automatic; `logger.info` in `savings.py` adds corridor/months/savings
- [x] Error handling with specific HTTP status codes (401, 404 ×2, 422, 429)
- [ ] Manual test via Swagger `/docs` successful — yours, needs a real token
- [x] OpenAPI docs updated (auto-generated; sanity-checked in `test_endpoint_is_documented_in_openapi`)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied via slowapi if user-facing — API-wide only (no Gemini call), same as `/compare`, `/trends` and `/log`

## Commit and PR for this task

Branch: `feature/remittance-savings-calc` (already checked out).

```bash
git commit -m "feat(remittance): add historical savings calculator" -m "Refs: NF-P2-022"
```

PR title: `feat(remittance): best-vs-worst savings over history (NF-P2-022)`

## For teammates

- **NF-P2-016 owner (recommendation):** `_comparison_json()` doesn't use a savings figure yet; its own runbook already noted a savings field could be added to the prompt payload without a version bump if the wording doesn't need to change. `RemittanceSavings.total_savings` (and the per-month detail) is now available to pass in.
- **Whoever builds a savings UI (no task ID currently owns this — `SavingsCallout.tsx` is still an empty stub):** call `/savings` with the same `corridor_id`/`amount` the worker is comparing, default `months=12`; show `total_savings` as the headline and `best_firm`/`worst_firm` for context, and don't over-claim precision when `months_used < months_requested`.
- **Anyone touching `engine.py`'s cost model:** this endpoint depends on `total_cost_pct` staying rate-independent for a fixed `amount` (decision 2). If that assumption ever changes (e.g., a future per-provider time-varying rate), `get_savings` needs a real live-rate read too.

## Not covered here

- Any frontend savings callout/UI — no task currently owns wiring `SavingsCallout.tsx` up to this endpoint
- Feeding the savings figure into the Gemini recommendation prompt (NF-P2-016's future work, not assigned)
- `docker build`: not run this time (daemon not running); see NF-P2-014's runbook for the last successful run
- Verifying real backfilled history reaches back the full 12 months in the actual dev/prod Firestore (see "Verified results")
