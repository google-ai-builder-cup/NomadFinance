# NF-HR-003 — Demo data seed for the two new features

Assigned to Aditya.

## Summary

The three demo workers of NF-P3-021 (Priya, Rajesh, Miguel) now also have what the two new modules need to be shown from one account: **a completed Coach session with its 90-day plan** (translated, with check-in answers where the story has them) and **five stored scam checks** (three scams and two benign messages, in three message languages each). One command reseeds them, and a read-only **preflight** says what a cold account still lacks.

| Part | What it does |
|---|---|
| **Plan files** `data/seed/coach/<name>.json` | The session, plan and translation exactly as the backend stores them, built by the backend's real plan flow (score, figures, the checks on the sentences, the translation check) with the team's sentences standing in for the model. Dates are relative |
| **Scam files** `data/seed/scam-checks/<name>.json` | Five checks each, built through the real analyzer (masking, indicators, verdict trimming, stored document), from rows of the reviewed golden sets, explained in the worker's language |
| **Loaders** `demo_coach`, `demo_scam` | Idempotent, one atomic batch per worker; they replace only what carries `demo_seed` |
| **Preflight** `demo_preflight` | Read-only; lists corridors, labor laws, cost baselines, complaint templates, rates, taxonomy, patterns, the two flags and each worker's data, with the fix for each gap |
| **`seed_demo.sh`** | Loads cost baselines and the scam taxonomy first (they were not in any script), then the existing seed, then the two new loaders, then the preflight |

## The three workers

| | Priya | Rajesh | Miguel |
|---|---|---|---|
| Route, language | SG to India, `hi` | Korea to India, `hi` | JP to Philippines, `tl` |
| Plan score | 65 getting ready | 58 getting ready | 94 well prepared |
| Provider quoted | InstaReM | none (no corridor of the six) | Wise |
| Warnings | high-interest debt, thin emergency fund | agent fee over the usual limit (urgent), high-interest debt, thin fund, no quote | none |
| Left | 40 days ago | in 21 days | 40 days ago |
| Check-ins | day 30 answered | none due | day 30 answered |
| Scam checks (message languages) | hi, bn, hi, hi, en | ne, hi, en, hi, hi | tl, tl, en, id, tl |
| Explanations in | Hindi | Hindi | Tagalog |

Priya's and Miguel's plans come from the Coach personas p03 and p10 (`tests/fixtures/coach_personas.json`, marked `demo`); Rajesh has no persona, so his answers were written for the story (all in won: there is no rate between won and rupees to convert with).

## Files

| File | Change |
|---|---|
| `backend/tests/fixtures/demo_seed.py`, `demo_seed_plan_text.py`, `demo_seed_scam_text.py` (new) | The builders and the CLI (`--write`); the plan sentences in English, Hindi and Tagalog; the scam explanations in Hindi and Tagalog and the picks |
| `backend/tests/unit/test_demo_seed_drift.py` (new) | 25 tests: the files are what the backend builds now; the loaders' output is read back through the backend's models |
| `data-scripts/data/seed/coach/*.json`, `scam-checks/*.json` (new) | The six files |
| `data-scripts/src/validators/demo_coach.py`, `demo_scam.py`; `src/loaders/demo_coach.py`, `demo_scam.py`, `demo_preflight.py` (new); `src/utils.py`, `src/config.py` | Checkers and loaders |
| `data-scripts/scripts/seed_demo.sh`, `README.md` | The order, and the documentation |
| `data-scripts/tests/test_demo_coach.py`, `test_demo_scam.py`, `test_demo_preflight.py`, `fake_firestore.py` (new) | 73 tests |
| `docs/data-model/collections/coach.md`, `scam.md` | The `demo_seed` marker; D-270 to D-272 |

No shared file (`package.json`, `Dockerfile`, workflows, rules, `firebase.json`) was touched and no dependency was added.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where the plan's words come from | Written by the team and run through the real checks, so the finale does not depend on Gemini quota; the translation is stored too |
| 2 | Files built by code, not by hand | A backend test rebuilds them and fails on a difference, so a rule change cannot leave the demo wrong |
| 3 | Relative dates, and a plan id that moves | The departure day is one of the answers; a run on another day replaces the plan (only `demo_seed` documents are removed) |
| 4 | Check-ins | Priya and Miguel left 40 days ago and answered day 30, so NF-HR-001's report section and the dashboard have data; Rajesh leaves in 21 days |
| 5 | Opt-in | `signal_sharing` is set for the three fictional workers, merged into the user document |
| 6 | The scam messages | Rows of the reviewed golden sets (invented, on reserved names); only the explanations are new |
| 7 | The stored key | The 64-character cache key is not in the files (a secret scanner looks for exactly that): the loader works it out from the masked text and the language |
| 8 | Prerequisites | `seed_demo.sh` loads the offline ones; the patterns (embedding key) and the flags (operator) are only reported |

## Results

**Backend (2026-10-10):** 3,725 tests pass (175 skipped, the live ones); `black`, `ruff`, `mypy app` and `mypy --strict app/services` clean. **Data scripts:** 628 pass (1 skipped); `ruff`, `black --check`, `mypy src tests` clean; the CI dry-runs (labor laws, corridors) pass.

| Check | Result |
|---|---|
| Files are what the backend builds | Rebuilt in a test; a changed file fails it |
| The plans | `CoachPlan`, `CoachScore`, `CoachProfile` and `to_response` accept the loader's output; the plan id is the backend's `slot_hash[:20]`; the translation passes the backend's figures check; the session reads as completed at the plan stage |
| The checks | `from_document` reads each; id and key are the backend's; the indicators are what the rules find in the message; the verdict is the golden row's; every trigger phrase is in the masked text; the prompt versions are the current ones |
| The finale pre-warm | Each seeded message, sent to `analyze_text` with a model that raises if called, is answered `cached: true` |
| Loaders | Same-day rerun changes nothing; another day replaces the plan and its translation; a real plan or check is never removed; a missing user document is a clear error; `--dry-run` touches nothing |
| Preflight | Each missing collection, too few patterns, stale rates (a warning), each flag variant, a worker missing a loader's data, and the exit code |

**In the emulators (Auth, Firestore, Storage; the backend running against them):**
- `scripts/seed_demo.sh` ran end to end after `load_bootstrap.sh` and the complaint templates: three histories, six sample contracts, three plans, 15 checks.
- The preflight then listed exactly what the emulator lacked (exchange rates, the 480 patterns, the two flags); after setting rates and flags only the patterns remained, as expected without an embedding key.
- As each worker (custom-token sign-in): `GET /coach/overview` showed the plan; the plan came back in English and in the worker's language with `available_languages: ["en", "hi"]` and **no model call**; the scam history listed five checks; **each seeded message sent to `/scam/analyze` came back `cached: true`**; the plan PDF was made from the seeded plan (Hindi 35 KB, Tagalog 21 KB, Hindi 33 KB).
- A Financial Identity recompute (NF-HR-001) on the three workers gave scores 85, 64 and 94, `scam_signal` 5 checks and 3 flagged for each, and `coach_signal` for Priya and Miguel (one answered check-in, savings target beside the recorded rate) and none for Rajesh.

**Not verified:** the whole run against `nomadfinance-prod` (D-271: the loaders default to it; it is for you to run); the pattern load (needs the key); the wording in Hindi and Tagalog by native speakers (D-270); the screens on a phone with this data.

## Manual test

```bash
cd backend && pytest tests/unit/test_demo_seed_drift.py
cd ../data-scripts && pytest tests/test_demo_coach.py tests/test_demo_scam.py tests/test_demo_preflight.py
python -m src.validators.demo_coach && python -m src.validators.demo_scam
```

Against the emulators (from `frontend/`: `firebase emulators:start --only auth,firestore,storage --project demo-nomadfinance`), with `FIRESTORE_EMULATOR_HOST=127.0.0.1:8085`, `FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099`, `STORAGE_EMULATOR_HOST=http://127.0.0.1:9199` and `FIREBASE_PROJECT_ID=demo-nomadfinance` set, from `data-scripts/`:

```bash
bash scripts/load_bootstrap.sh && python -m src.loaders.complaint_templates
bash scripts/seed_demo.sh
```

**Windows PowerShell:** set the four variables with `$env:NAME = "value"` first, and run each `python -m ...` line of the two scripts one by one (or use Git Bash for `bash scripts/...`).

Then sign in as a demo worker and open the Coach page and the Scam Check history, or call the API with a token for `uid_priya_demo`.

## Definition of Done (Data)

- [x] A completed Coach session and plan for each of Priya, Rajesh and Miguel
- [x] Five scam checks each, a mix of scams and benign, in three message languages
- [x] One command reseeds (`seed_demo.sh`), ending with a preflight of what a cold account needs
- [x] Idempotent; only demo documents are replaced; relative dates
- [x] Built and checked by the backend's own code; a test fails on drift
- [x] No shared file touched; no key-like value stored
- [ ] Run against production, patterns loaded and flags on (D-271)
- [ ] Wording read by native speakers (D-270)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-HR-003-data-demo-seed-v2` (already checked out).

```bash
git commit -m "feat(data): seed demo coach plans and scam checks for the finale" -m "Refs: NF-HR-003"
```

The header is 64 characters (the limit is 72). PR title: `feat(data): demo Coach plans and scam checks for the finale (NF-HR-003)`
