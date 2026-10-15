# NF-P2-014 — Remittance X-Ray: Comparison Engine

## Summary

`POST /api/v1/remittance/compare` takes a corridor (`SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH`) and an amount in the sending currency, and returns every surveyed way to send it, with the true cost of each and what the recipient receives, best first.

It is steps 1 to 6 of the Remittance X-Ray pipeline:

1. Verify the caller (existing).
2. Read `corridors/{corridor_id}`, all providers in one document (NF-P1-016).
3. Read `rates_cache/{pair}`, the live mid-market rate (NF-P1-019).
5. Work out each provider's cost at the requested amount.
6. Rank by what the recipient receives.

The prices are the World Bank's Remittance Prices Worldwide survey of early 2025, not live prices. Only the exchange rate is live. The response carries the survey period and the World Bank attribution, which its terms require wherever the prices are shown.

No Gemini call, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/remittance_compare.py` (new) | Request, the stored-document models the engine reads, and the response (`RemittanceComparison`) |
| `backend/app/services/remittance/engine.py` (was a stub) | `calculate_comparison()` (pure, no I/O), `compare_remittance()` (reads, then calls it), `amount_limits()`, the two errors |
| `backend/app/repositories/corridor_repo.py` (was a stub) | Read-only `CorridorRepository.get_corridor()` |
| `backend/app/repositories/rate_repo.py` | `RateRepository.get_rate()` |
| `backend/app/api/v1/remittance.py` (was a stub) | The endpoint |
| `backend/app/api/v1/router.py` | Includes the remittance router |
| `backend/app/constants.py` | `RATE_MAX_AGE` (6 hours), `pair_for_corridor()` |
| `backend/tests/unit/services/test_remittance_engine.py` (new) | 68 tests on the real World Bank file |
| `backend/tests/integration/api/test_remittance_compare.py` (new) | 25 endpoint tests |
| `backend/tests/integration/repositories/test_remittance_repositories.py` (new) | 4 tests on the Firestore emulator |
| `docs/api/endpoints.md` | The endpoint |
| `docs/data-model/collections/corridors.md` | Corrected the "do not recompute" note (see decision 1) |

`requirements*.txt`, `pyproject.toml`, `Dockerfile`, `firestore.rules` and the workflows are unchanged.

## Decisions

1. **The cost is recomputed for any amount.** The data model said not to recompute `total_cost_pct`. But the worker chooses the amount and the survey priced only two, so it has to be. The formula `fee / amount * 100 + fx_margin_pct` was tested on all 442 published quotes and reproduces `total_cost_pct` to within 0.005 percentage points every time. What differs by up to 0.8 points is recomputing from `fx_rate` and `interbank_rate`, which the survey rounds. The engine never does that. A test repeats the check for every provider of every corridor at both survey amounts.
2. **Fee and margin are interpolated between the two survey amounts.** 71 of the 221 services have a fee that differs between them (tiered fees). Outside them the nearest survey point is kept and the row is marked `estimated`.
3. **Amount limits: a quarter of the smaller survey amount to ten times the larger** (about USD 50 to 5,000). Outside them the answer is a `422` that states the limits, instead of a number the survey cannot support.
4. **Ranking is by what the recipient receives, and the live rate never changes the order.** Every provider of a corridor uses the same rate. A test proves the order is identical for very different rates in all six corridors.
5. **Services paying out in USD are listed last, not ranked** (6 of 221: SG-PH 1, SG-IN 1, JP-PH 4). Hiding them would hide their cost. Ranking them would compare dollars with pesos.
6. **A missing or old rate does not break the comparison.** No `rates_cache` document: the survey's median mid-market rate is used, with `source: "survey"` and `stale: true`. An older-than-6-hours rate (`stale: true`) is still used. The app says the rate may be out of date.
7. **`rpw_id` is the key, not the firm.** A firm appears once per service (13 firms repeat in SG-PH). The summary carries both.
8. **Ties are broken by speed, then name, then `rpw_id`**, so identical requests give identical orders.
9. **The maths is a pure function.** `calculate_comparison()` does no I/O, so it is tested against the real data without Firestore, and NF-P2-022 (savings) can reuse the cost function.
10. **Amounts are rounded once, at the end**, to two decimals (the rate to six), after the ranking used the exact values.
11. **The request log never holds the amount**: corridor, counts, rate source and staleness only.
12. **A non-finite amount is guarded locally.** Sending `NaN` or `Infinity` made the API answer 500, because FastAPI echoes the rejected value back and JSON cannot hold it. The request model turns such a value into 0 before the check, so it is a plain 422. The same problem exists for every endpoint: D-63.
13. **No process cache for the corridor.** It is one small read, the data changes quarterly, and a cache would need invalidating on a reload. Revisit if latency shows a need.

## Flow

```
POST /api/v1/remittance/compare  {corridor_id, amount}
  token (401), body (422: unknown corridor, amount missing / not a number / 0 or less / NaN / infinite)
  compare_remittance(corridor_id, amount, corridors, rates, now)            [services/remittance/engine.py]
    └─ corridors/{id}        (threadpool)   none → CorridorNotFoundError → 404
    └─ rates_cache/{pair}    (threadpool)   none → survey median, stale
    └─ calculate_comparison(...)            [no I/O]
         limits: quarter of the lower survey amount .. ten times the upper   → 422 with the limits
         per provider: fee + margin at this amount (interpolated) → cost, recipient receives
         rank the comparable ones; the USD payouts after them
         summary, survey block, rounding
  200 RemittanceComparison
```

## All commands, in order

From `backend/` with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash, `source .venv/bin/activate` on macOS and Linux).

### 1. The checks CI runs (`.github/workflows/backend-ci.yml`)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it, without Google credentials:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
```

```bash
docker build --platform linux/amd64 -t nomadfinance-backend:ci .
```

### 2. The Firestore repository tests (need the emulator)

From `frontend/`, which has `firebase.json`:

```bash
firebase emulators:exec --only firestore --project demo-nomadfinance "cd ../backend && FIREBASE_PROJECT_ID=demo-nomadfinance python -m pytest tests/integration/repositories -q"
```

### 3. Try it by hand

Start the API (`uvicorn app.main:app --host 127.0.0.1 --port 8080`) with the corridors loaded (`python -m src.loaders.corridors` from `data-scripts/`, against the emulator) and a Firebase ID token as in the NF-P2-001 runbook, then use the example in `docs/api/endpoints.md`. Expected for SG-PH and 500: 39 providers, 38 ranked, `DBS` last with `rank: null`, and `summary.extra_vs_worst` of about 2,500 PHP at a rate near 43.

Try the edges: `amount: 10` (422 with the limits), `amount: 100` (`estimated: true` on every row), a corridor with no rate cached yet (`rate.source: "survey"`).

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass |
| `pytest -q`, with and without Google credentials | 502 passed, 42 skipped (opt-in live and emulator tests) |
| New tests | 68 engine, 25 endpoint, 4 repository (emulator) |
| Repository tests on the Firestore emulator | 13 passed (the 4 new, and the existing ones) |
| Cost model against the survey | All 442 published quotes reproduced to within 0.01 after rounding, at both survey amounts, for all six corridors |
| Do the tests catch a wrong engine? | Four deliberate breakages, each caught: fee left out of the cost, ranking reversed, no interpolation, USD payouts ranked. The engine was restored and is unchanged |
| `docker build --platform linux/amd64 -t nomadfinance-backend:ci .` (as CI runs it) | Pass, exit 0; image 400 MB. Inside the image the app starts and `/api/v1/remittance/compare` is in its OpenAPI schema with responses 200, 401, 404, 422 and 429 |
| Live run against Firestore and the cron's real rates | **Not run**: production has not been touched, and the corridors' load state in production is not known to me. The emulator test loads the real World Bank file the same way the loader does |
| Example in the docs | Generated by the engine (SGD 500 to PHP at 43.2: best InstaReM 21,442.17 PHP, worst Maybank 18,874.08 PHP, 2,568.09 PHP apart) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 404 `No prices are available yet for <corridor>` | The corridor is not loaded: run `python -m src.loaders.corridors` (NF-P1-016) against that project |
| `rate.source` is `survey` and `stale` is true | `rates_cache` has no document for the pair: the cron has not run (`docs/runbooks/NF-P1-019-fx-refresh-cron.md`) |
| `rate.stale` is true with `source: live` | The cached rate is older than 6 hours: check the cron's last runs |
| 422 `Enter an amount between ...` | The amount is outside the limits of that corridor; the message gives them in the sending currency |
| Every row has `estimated: true` | The amount is below or above the two survey amounts (about USD 200 and 500); expected |
| A service the worker knows is missing | The survey lists 221 services in 2025 Q1; a newer quarter needs the parser (NF-P1-015) and the loader run again |
| 500 on a corridor | A damaged corridor document (it failed validation); reload it with the loader |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with Pydantic request and response models
- [x] Firebase Auth token verification (401 without it)
- [x] Structured logging with request id, user (hashed) and timing: from NF-P1-028, automatic; the step adds its own line without the amount
- [x] Specific error codes (401, 404, 422, 429)
- [ ] Manual test via Swagger `/docs` with a real token: yours (step 3 above)
- [x] OpenAPI documents the endpoint and its responses (checked by a test)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting: the API-wide budget applies; no Gemini budget, since no Gemini call

## Commit and PR

Branch: `feature/remittance-engine` (already checked out).

Suggested commit message, one line plus the reference:

```
feat(remittance): compare and rank transfer providers by what the recipient receives
Refs: NF-P2-014
```

PR title:

```
feat(remittance): comparison engine that ranks every provider for a corridor and amount (NF-P2-014)
```

## For teammates

- **Devam (NF-P2-015 trends, NF-P2-022 savings):** `constants.pair_for_corridor(corridor_id)` gives the pair for `rates_history`. The cost function is `engine._terms()`; reuse it for savings rather than copying it.- **Pranjal (NF-P2-016 recommendation):** `RemittanceComparison` already holds what `recommend.v1` names. Keep the recommendation a separate call from `/compare`: it is the only step that needs Gemini.
- **Aditya (NF-P2-017 log, NF-P2-019 table):** key a provider by `rpw_id`, not `firm`. Sort the speed column by `speed_order`. Show `survey.attribution`, a note when `estimated` or `rate.stale` is true, and the survey period.
- **Everyone:** no new packages and no new environment variable. The corridors must be loaded in the Firestore project you test against.

## Not covered here

- Trends and best day to send (NF-P2-015), historical savings (NF-P2-022), the recommendation and its translation (NF-P2-016), transfer logging (NF-P2-017)
- The corridor picker and comparison table (NF-P2-018, NF-P2-019), radar warnings on a provider (NF-P3-022)
- Repairing the validation-error echo for every endpoint (D-63)
- A process cache for the corridor document (decision 13)
