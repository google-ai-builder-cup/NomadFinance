# NF-P2-007 — Contract Shield: Pipeline + Response Caching

## Summary

By team decision, this task gained the missing piece of Contract Shield (D-53): the pipeline that runs steps 1 to 6 in order and stores the result. Before it, each step had only its own test endpoint, and nothing let a worker upload a contract and get a saved report.

**Three endpoints:**
- **`POST /api/v1/contracts`**: the worker's file is read (step 1) and stored as `users/{uid}/contracts/{id}`. The file itself is **not kept**, only the blocks and text read from it, in a backend-only document.
- **`POST /api/v1/contracts/{id}/analyze`**: runs detection, law, comparison, complaint letter and translation.
  - It updates the contract's `status` and `step` as it goes, so the app can show live progress by watching the document in Firestore.
  - It stores the English report and the worker's language report.
  - Any failure is stored with its step and a code the app can act on.
- **`POST .../reports/{language}`**: switches the report language without uploading again.

**Caching.** It is per user and follows `versioning.md`: the file hash, the labor-law version and the prompt versions must all match.
- The same file uploaded twice is read once.
- A current analysis is returned without calling Gemini.
- A missing language is translated once.
- A new law version or prompt version runs the analysis again.

**Fallbacks (D-55).**
- **Country:** the worker's choice on the upload form wins, then what the contract shows, then the worker's profile. With none of them, the analysis asks the worker (`country_unknown`).
- **Job type and report language** fall back the same way.

**The complaint letter.** A letter that fails for a passing reason, such as Gemini overloaded, is marked `complaint_pending`, and the next analyze writes only the letter. A live run found this gap: the first version cached "no letter" after a 503.

**Other changes:**
- The Cloud Run request timeout goes from 300 to 900 s, because the whole analysis runs inside one request.
- No shared files and no security rules were changed; one rules test was added.

## Files

| File | Change |
|---|---|
| `backend/app/api/v1/contract_analysis.py` (new) | The three endpoints; `read_contract_upload()` (shared file checks); error messages per stop code |
| `backend/app/api/v1/contracts.py` | The extract endpoint uses `read_contract_upload()` (same checks, one place) |
| `backend/app/api/v1/router.py` | Includes the new router |
| `backend/app/services/contract/upload.py` (new) | Upload: hash, reuse, step 1, store contract + extraction |
| `backend/app/services/contract/pipeline.py` (was a stub) | Analyze: fallbacks, claim, steps 2 to 6, progress, stored failures |
| `backend/app/services/contract/report_store.py` (new) | Cache rule, reports, translation on demand, reuse of a current analysis |
| `backend/app/services/contract/letter.py` (new) | The complaint letter with "pending" for passing failures, and writing it later |
| `backend/app/repositories/contract_repo.py`, `user_repo.py` (were stubs) | Contracts, extraction, reports (batched writes, transaction for the claim); the worker's profile |
| `backend/app/schemas/contract_pipeline.py` (new) | Upload, analyze request/response, stored report; step and error codes |
| `backend/scripts/deploy_manual.sh` | `--timeout 900` (the backend deploy workflow runs this script) |
| `backend/tests/unit/services/test_contract_pipeline.py` (new) | 28 tests: upload reuse, every step and stop, cache hits and misses, fallbacks, failures, letter retry, language switch |
| `backend/tests/integration/api/test_contract_analysis.py` (new) | 14 endpoint tests |
| `backend/tests/integration/repositories/test_contract_repository.py` (new) | 5 tests against the Firestore emulator (transaction, deletes, report list) |
| `backend/tests/integration/api/test_contract_analysis_live.py` (new) | Opt-in: real Gemini + real repositories on the emulator |
| `backend/tests/fixtures/pipeline_fakes.py` (new) | In-memory repositories and step stand-ins |
| `frontend/tests/rules/firestore.rules.test.ts` | `extraction/current` is backend-only, even for the owner |
| `docs/data-model/collections/contracts.md` | `step`, `title`, `legibility`, `host_country`, `job_type`, `models`, `complaint_pending`, error codes, `extraction/current`, `is_source` meaning, clause `number`/`page`/`block_ids`, the cache as built |
| `docs/api/endpoints.md` | Endpoints; pipeline flow; D-16, D-53, D-55 closed, D-59 new |

## Decisions

1. **Two calls plus a language switch, not one call.**
   - The app needs the contract id **before** the long part, to watch progress.
   - Cloud Run gives CPU only to open requests, so "answer now, work in the background" would need Cloud Tasks.
   - All work stays inside requests: the upload (step 1, 3 to 40 s), then analyze (30 s to 2 min).
2. **The file is not kept.** Step 1 runs during the upload, and `extraction/current` holds its blocks and text. This is better for workers' privacy (D-16), and no Cloud Storage code is needed.
3. **Progress through Firestore:** `status` plus `step`. The owner can already read the contract, so no security rule changed.
4. **The cache as `versioning.md` defines it,** plus two practical rules:
   - The same file is reused only while it was read with the current extraction prompt.
   - A different country or job chosen by the worker runs the analysis again.
5. **Order inside analyze:** detect → law → compare → complaint → store `reports/en` and the analysis → translate. The analysis is stored before translating, so a failed translation only needs the translation again.
6. **Stops with codes the app can show:** `poor_legibility`, `country_unknown`, `not_employment_contract`, `no_law_data`, `no_terms`, and the Gemini codes.
7. *(2026-10-01, NF-P4-001-production-bug-fixes.md: a missing template is now pending too: all six countries have one, so it means "not loaded yet", which is what happened in production.)* **Letter pending instead of lost** (added after the live run, see Verified results). A country without a template is final: no letter.
8. **One analysis at a time per contract.** A Firestore transaction claims it (409 for a second request); after 16 minutes an abandoned claim is taken over.
9. **Worker's copy of the letter:** written once, in the analysis language, and carried unchanged into other languages. Its `worker_language` field says which language that is. A copy per language would cost a reasoning call per switch. `contracts.md` is updated to match.
10. **`is_source` now means "the English report the analysis wrote",** because the comparison writes in English. The data model said "the contract's own language".

## Flow

```
App                                    Backend                                     Firestore users/{uid}/contracts/{id}
 │ POST /contracts (file) ──────────▶ same file? → reuse                            
 │                                    else step 1 (extract) ───────────────────────▶ {status: uploaded, legibility, ...}
 │ ◀── {contract_id, legibility}                                                    + extraction/current {blocks, text}
 │ onSnapshot(contract) ◀─────────────────────────────────────────────────────────── status / step changes
 │ POST /contracts/{id}/analyze ────▶ current? → cached (translate only / letter only)
 │                                    claim (transaction) ─────────────────────────▶ {status: processing, step: detect}
 │                                    step 2 detect → fallbacks ───────────────────▶ step: law, detected, extracted, host_country, job_type
 │                                    step 3 law ──────────────────────────────────▶ step: compare
 │                                    step 4 compare → score
 │                                    step 6 letter (if danger) ───────────────────▶ step: complaint
 │                                    reports/en + analysis fields ────────────────▶ reports/en, health_score, ...
 │                                    step 5 translate (if not en) ────────────────▶ step: translate, reports/{lang}
 │ ◀── {scores, report_languages}     status completed ────────────────────────────▶ {status: completed}
 │ read reports/{lang} from Firestore;  switch: POST /contracts/{id}/reports/{lang}
```

## All commands, in order

From `backend/` with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash).

### 1. Checks

```bash
python -m pytest -q
ruff check .
black --check .
mypy app tests
```

As on CI, without Google credentials (Git Bash):

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent CLOUDSDK_CONFIG=/tmp/empty APPDATA=/tmp/empty python -m pytest -q
```

Security rules (from `frontend/`):

```bash
pnpm test:rules
```

### 2. Repository tests on the Firestore emulator

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

Terminal 2, from `backend/`, in Git Bash:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m pytest tests/integration/repositories -q
```

In PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m pytest tests/integration/repositories -q
```

### 3. Live end-to-end on the emulator (real Gemini, about 6 calls; never production)

Keep the emulator running. Load the curated data **into the emulator** from `data-scripts/`, with both variables set so nothing can reach production:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.ilo_natlex --only SG MY
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.complaint_templates --only SG MY
```

Expect "new" for both countries; "unchanged" would mean you are not on an empty emulator. Then, from `backend/`:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance RUN_LIVE_GEMINI=1 python -m pytest tests/integration/api/test_contract_analysis_live.py -v -s
```

A 503 "temporarily unavailable" or "busy" is Gemini overloaded or the daily quota (D-58), not a failure of the pipeline. The contract then shows `status: failed` with the Gemini code; run again later.

### 4. After merge

The backend deploy workflow runs `deploy_manual.sh`, which now sets the request timeout. Check it:

```bash
gcloud run services describe nomadfinance-api --project nomadfinance-prod --region asia-south1 --format="value(spec.template.spec.timeoutSeconds)"
```

Expect `900`.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `pytest -q`, with and without Google credentials | 409 passed, 28 skipped (opt-in live and emulator tests) |
| `ruff check .`, `black --check .`, `mypy app tests` | Pass (170 files) |
| Repository tests on the Firestore emulator | 9 passed. They cover the claim transaction (busy, then taken over when stale), `None` deleting fields, one entry per language in `report_languages`, and `find_by_hash` only seeing the same user's files |
| `pnpm test:rules` | 100 passed, including `extraction/current` denied to its owner (read and write) |
| A test can fail | Removing the prompt-version check from the cache rule made exactly the matching test fail |

**Live, real Gemini, real repositories on the emulator:**
- **First full run.**
  - Upload of `sample_contract_sg.pdf`: **201 in 17.1 s**.
  - Analyze: **200 in 74.6 s**, with two 503 retries along the way. Score 31, **danger** (2 danger, 4 caution, 2 safe), and `reports/en` plus `reports/hi` stored.
  - The complaint step got 503 on all 3 attempts and the report was saved without a letter. That run showed that the letter would then stay missing, because the analysis was cached. Fixed with `complaint_pending` (decision 7), and tested in unit tests: pending after a passing failure, written alone on the next analyze into every stored report, still pending if it fails again.
- **Later runs** (upload about 3.3 s each). The reasoning model answered 503 (`gemini_unavailable`) and then 429 (`gemini_busy`) at the comparison. Each time the failure was stored on the contract (`status: failed`, `error: {step: compare, code: ...}`) and the API answered a clean 503. That is the failure path working live.

**Not yet run live:** the full test after the letter fix, so the letter retry, cached analyze and language switch against real Gemini. They are covered by the unit, endpoint and emulator tests. **Run step 3 once after the quota resets** (07:00 UTC) and record it here.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Analyze 409 "already being analysed" | Another request holds the claim. If that request died, the claim is taken over after 16 minutes |
| Contract `status: failed`, `error.code: gemini_*` | Gemini overloaded or out of quota (D-58); analyze again later. Everything already stored is reused |
| `error.code: poor_legibility` | The photo was unreadable at upload; take a new photo (a new upload) |
| `error.code: country_unknown` | Neither the form, the contract nor the profile gave one of the six countries; send `host_country` in the analyze body |
| `complaint_pending: true` | The letter failed for a passing reason; analyze again writes only the letter |
| Analyze always re-runs | Different `host_country`/`job_type` sent than the stored analysis used, or a prompt or law version changed; that is the cache rule |
| Request cut at 300 s in production | The service still has the old timeout: check step 4; redeploy |
| Upload 422 "No readable document" | Step 1 found no document (selfie, blank page) |

## Definition of Done (Backend Endpoint)

- [x] Endpoints defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification (all three need a token; a user reaches only their own `users/{uid}`)
- [x] Structured logging: request id, hashed user, timing. Step failures are logged as `pipeline_failed step=... code=...` with no contract text
- [x] Error handling with specific HTTP codes (400/404/409/413/415/422, Gemini 502/503/504), no stack traces to clients
- [x] Manual test: the endpoint tests and the live run above. Swagger `/docs` lists all three
- [x] OpenAPI documented (checked by a test)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting: all three use the Gemini budget (10/min) on top of the API-wide 60/min

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Aditya (NF-P2-009, upload UI):**
  - `POST /api/v1/contracts` with the file.
  - If `legibility` is `poor`, show "take a clearer photo" and don't analyse.
  - Then call analyze with the form's `host_country`, `job_type` and `report_language`.
  - Keep the request open (up to about 2 minutes, 15 at worst).
- **Devam (NF-P2-010, progress):**
  - Listen to `users/{uid}/contracts/{id}` with `onSnapshot`.
  - Map `step` to your steps: detect, law, compare, complaint, translate.
  - `status: failed` plus `error.code` gives the message.
- **Aditya (NF-P2-011, report card):** read `reports/{lang}` from Firestore. The clauses carry `number`, `page` and `block_ids`.
- **Pranjal (NF-P2-012, language switch):** `POST /api/v1/contracts/{id}/reports/{lang}`, then read it or use the response.
- **Aditya (NF-P2-013, complaint letter):**
  - `report.complaint`, when present.
  - If the analyze response or the contract says `complaint_pending`, offer "try again", which calls analyze.
- **NF-P2-008 (E2E, all):** use these three endpoints. Mind the Gemini quota (D-58).
- **NF-P3-019 (dashboard) and NF-P3-024 (contract income):** the contract list is `users/{uid}/contracts`. After analysis, `extracted` holds the employer and salary.

## Commit and PR for this task

Branch: `feature/contract-cache` (already checked out).

```bash
git add backend docs frontend/tests/rules/firestore.rules.test.ts
git status
```

```bash
git commit -m "feat(contracts): add analysis pipeline with stored reports and caching" -m "Refs: NF-P2-007"
```

PR title: `feat(contracts): Contract Shield pipeline — upload, analyze, stored reports, caching (NF-P2-007)`

## Not covered here

- Upload screen, progress screen, report card, language switch, letter download: NF-P2-009 to NF-P2-013
- Splitting `contracts.py` (D-59)
- A paid Gemini key (D-58); background processing with Cloud Tasks (only if 900 s ever proves too short)
