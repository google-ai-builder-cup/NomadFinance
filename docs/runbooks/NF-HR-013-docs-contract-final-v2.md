# NF-HR-013 — API contract and data model, final for v2.0

## Summary

The API contract (`docs/api/`) and the data model (`docs/data-model/`) now describe what is deployed, and two checks keep them that way. Production runs commit `5d895ab` (Cloud Run revision `nomadfinance-api-00083-fpv`, read on 2026-10-11), the same commit this branch started from, so the OpenAPI document built from this code is the live contract.

The tracker names `docs/api-contract.md` and `docs/data-model.md`. The real files are `docs/api/` (`endpoints.md` for `/api/v1`, `v2-*.md` for `/api/v2`) and `docs/data-model/` (D-04).

| File | What changed |
|---|---|
| [`docs/api/openapi.json`](../api/openapi.json) | **New content** (it was empty): the OpenAPI 3.1 document of the app, 40 paths and 41 operations, version `2.0.0`, written by the script below |
| [`backend/scripts/export_openapi.py`](../../backend/scripts/export_openapi.py), [`generate_openapi.sh`](../../backend/scripts/generate_openapi.sh) | **New.** Builds the document from `create_app()` with the title and version pinned and `.env.local` shadowed, so two machines write the same file. `--check` only compares. The `.sh` was an empty stub; it is now a wrapper that prefers the backend's virtualenv |
| [`backend/tests/unit/test_api_contract_docs.py`](../../backend/tests/unit/test_api_contract_docs.py) | **New.** Fails when `openapi.json` is out of date, when a route (the 41 plus the 5 Cloud Scheduler routes) has no heading or table row in `docs/api/`, or when `docs/api/` names a route the app does not serve |
| [`backend/tests/unit/test_data_model_docs.py`](../../backend/tests/unit/test_data_model_docs.py) | **New.** Fails when a collection the backend or the data scripts use, or the rules name, is missing from the collection map; a top-level collection is missing from the access matrix; an entry of `firestore.indexes.json` has no table row; or a Storage folder the backend writes is not in the Storage table |
| [`docs/api/endpoints.md`](../api/endpoints.md) | `POST /api/v1/internal/aggregate-scam-stats` documented (it was in no doc); the contract-in-machine-form note; CORS headers (`Idempotency-Key` and the three exposed v2 headers) and the staging origins; the daily-quota 503; the scam-analyze hourly limit; the 128 KB JSON cap on `/api/v2`; labor-law reference fields; radar entity reports with `scam_check` and the `scam` map; the check-in answer values; `schema_version`; a measured translate time |
| [`docs/api/v2-coach.md`](../api/v2-coach.md), [`v2-scam.md`](../api/v2-scam.md), [`v2-conventions.md`](../api/v2-conventions.md) | Status text brought to "everything is built"; mock counts and wording; the eleven currencies; two unstated limits; open points that are done or still open say so; a changelog row |
| [`docs/data-model/firestore-schema.md`](../data-model/firestore-schema.md) | `scam_stats` and the contract `extraction` document added to the map and the access matrix; the live state of indexes, single-field settings and TTL; the `scam_checks.created_at` group-scope index; the deploy path stated as it is; the Storage table corrected (no `contracts/`); bucket and protection settings |
| [`docs/data-model/collections/fib.md`](../data-model/collections/fib.md), [`scam.md`](../data-model/collections/scam.md) | `fx_rate_applied` marked reserved (nothing writes it); the `scam_stats` index is no longer "to create" |
| [`docs/mocks/README.md`](../mocks/README.md) and five scam samples | The mocks are fixtures, not a promise of an API to come; five similarity scores below the server's cutoff corrected; `test_scam_mocks.py` guards it |
| [`docs/mermaid/*-pipeline.mmd`](../mermaid/) (six) | Gemini models named by tier; "Future scope" notes and the dashed "planned" style removed; contract diagram without the Cloud Storage upload and with the real step order; one recommendation step in the remittance diagram; the `scam-stats` job in the scam diagram (D-303) |
| [`docs/README.md`](../README.md), [`infra/README.md`](../../infra/README.md), [`backend/README.md`](../../backend/README.md), [`NF-P1-001`](NF-P1-001-local-dev-setup.md) | Stale statements fixed (D-304) |
| [`docs/future-scope/design.md`](../future-scope/design.md) | A status line and "as built" notes in sections 7 and 11 (D-101); the proposal text is kept |
| `backend/.env.example` | The line `APP_VERSION=0.1.0` removed (D-298) |
| Deleted | `infra/cloud-run/backend-service.yaml`, `infra/cloud-run/env.yaml`, `infra/cloud-scheduler/labor-law-check.yaml`, `infra/firebase/firestore.indexes.json`, `docs/architecture/overview.md`, `docs/architecture/stack-decisions.md`, `docs/pipelines/financial-identity.md`: all 0 bytes (D-302) |
| [`docs/deferred-items.md`](../deferred-items.md) | Closed: D-65, D-101, D-298, D-302, D-303, D-304. Updated: D-33, D-141, D-263, D-281. Added: D-308 to D-313 |

## Flow: where each fact comes from

```text
code (create_app) ──► scripts/export_openapi.py ──► docs/api/openapi.json ──► test: file is current
        │                                                   │
        └─ routes + the hidden internal router ─────────────┴──► test: every route is in docs/api/*.md and back

backend/app + data-scripts + frontend/firestore.rules + firestore.indexes.json
        └──► test: every collection, index and Storage folder is in docs/data-model/firestore-schema.md

gcloud (read-only config): indexes, single-field settings, TTL, database, Scheduler, Cloud Run
        └──► "What production holds" in firestore-schema.md
```

## What the docs said that was not true

| Said | Reality (source) |
|---|---|
| Four internal cron routes | Five: `POST /api/v1/internal/aggregate-scam-stats` (job `scam-stats`, daily 01:30 UTC, live) existed in no doc |
| `docs/api/openapi.json` | 0 bytes; `generate_openapi.sh` 0 bytes |
| CORS: request headers `Authorization`, `Content-Type`, `X-Request-ID` | Also `Idempotency-Key`; exposed `Idempotency-Replayed`, `Deprecation`, `Sunset` (`app/main.py`) |
| 503 `Retry-After: 30` for every Gemini quota case | A spent daily quota sends the seconds to the reset (`app/core/errors.py`, NF-HR-010) |
| Rate limits: API-wide and Gemini only | A third: 20 an hour for scam checks (`rate_limit_scam_analyze`) |
| Radar entity reports have no scam fields; `source` has three values | `source: scam_check` and a `scam` map, `violation_type: scam_message` (`RadarReportSummary`) |
| Labor-law references: `law`, `section`, `url` | Also `year`, `in_force_since`, `natlex_isn` |
| Coach: "The rest is specified only"; mocks "34 JSON files" | Every route is built; 38 JSON files |
| Scam: `scam_indicators` "nothing writes until NF-SA-013" | The report route writes it |
| "State on 2026-09-25: Empty" | In use; 6 composite indexes, 2 single-field settings, 3 TTL policies, all read live |
| `scam_stats` and `contracts/{id}/extraction/current` | Written by the code, absent from the collection map and the access matrix |
| Indexes and TTL "not deployed", "needs a person" | All present and `READY` / `ACTIVE` in production (created by hand, D-114) |
| `contracts/{uid}/...` in Storage | Never written: the file is read in memory, only text blocks are kept (D-303) |
| Mocks: "written before the endpoint exists"; scam samples with similarity 0.83 and 0.74 | Every endpoint exists; the server drops anything under 0.85 |
| Remittance diagram: a separate "translate" step; contract diagram: translation before comparison, upload to Cloud Storage | One call writes the recommendation in the worker's language; translation runs last; no file is stored |
| `mypy app tests` | CI runs `mypy app`; adding `tests` reports 150 errors |

## Commands

Regenerate the contract file after any route or model change (from `backend/`, venv active; the script also runs from anywhere):

```bash
python scripts/export_openapi.py
```

Only compare (what the test does):

```bash
python scripts/export_openapi.py --check
```

PowerShell:

```powershell
.\.venv\Scripts\python scripts\export_openapi.py --check
```

The two new tests and the mock tests:

```bash
python -m pytest tests/unit/test_api_contract_docs.py tests/unit/test_data_model_docs.py tests/unit/test_scam_mocks.py -q
```

Read-only commands used against `nomadfinance-prod` (configuration only):

```bash
gcloud firestore indexes composite list --project nomadfinance-prod --format=json
gcloud firestore indexes fields list --project nomadfinance-prod --format=json
gcloud firestore fields ttls list --project nomadfinance-prod
gcloud firestore databases list --project nomadfinance-prod
gcloud scheduler jobs list --location asia-south1 --project nomadfinance-prod
gcloud run services describe nomadfinance-api --region asia-south1 --project nomadfinance-prod --format=json
```

## Decisions that were not in the task text

| # | Decision | Why |
|---|---|---|
| 1 | The export pins the title and version to the setting defaults and sets placeholder values for the three required settings, then puts the environment back | A developer's `.env.local` with `APP_VERSION=0.1.0` (the old example file) made the first export say `0.1.0`; the file must be the same on every machine and in CI |
| 2 | The route test reads the OpenAPI paths plus the one hidden router (`internal`), not `app.routes` | The installed FastAPI wraps included routers in a private class; a test must not depend on it |
| 3 | The freshness test compares parsed JSON, not bytes | A Windows checkout may hold the file with CRLF line ends |
| 4 | No mock file was deleted | The audit of all 82 found 0 unused (each is read by a drift test or loaded as a handler) and 0 for a route the app lacks (the two `conventions/` files that name `/example/items` do it on purpose). What was stale was wording, counts and five scores |
| 5 | The five scam scores were raised to meet the cutoff instead of waiting for the calibration of D-141 | The samples described an answer the server cannot send; nothing in the screens or tests reads the number (checked in the code and by running the 14 related frontend test files) |
| 6 | The three bare-object schemas were documented, not fixed | The fix is a change to response models and their serializers (a behaviour risk): D-308. Two quick schema-only attempts did not work and were dropped |
| 7 | D-298 (one line of `.env.example`) was fixed here | It is the cause of a wrong version in `/health` and in the export |
| 8 | The seven empty placeholder files were deleted, not filled | Empty files read as missing work; the real content is elsewhere and the READMEs now say where |
| 9 | `docs/future-scope/design.md` got notes, its proposal text kept | It is the record of what was proposed; the contract is in `docs/api/` and `docs/data-model/` |
| 10 | `firestore.rules`, `storage.rules`, `firebase.json`, workflows and `pyproject.toml` were not touched | Shared files: they change only after the diff is shown and agreed. Findings about them are D-313 and D-33 |

## Checks run (2026-10-11)

| Check | Result |
|---|---|
| `python scripts/export_openapi.py --check`, also with `APP_VERSION=0.1.0` set | up to date |
| `ruff check .`, `black --check .` | pass (522 files) |
| `mypy app` | pass (244 source files). `mypy` on the new script and the two new tests: pass |
| `pytest tests/unit` | 3,193 passed, 22 skipped (the skips need the emulator) |
| Integration tests about `/health`, docs exposure and the scam-stats cron route | 19 passed |
| The two new tests, before the docs were fixed | failed on exactly the gaps found: `aggregate-scam-stats`; `extraction`, `scam_stats`, `weeks`; the `scam_checks.created_at` index |
| Freshness test with `openapi.json` altered by hand | fails, with the command to run; restored |
| Frontend: `vitest run src/mocks src/pages/scam src/components/scam` with placeholder Firebase variables | 14 files, 272 tests pass |
| Mermaid 11.4.1 in the browser pane: the six rewritten diagrams and the two architecture diagrams | 8 of 8 parse and render |
| Page-level and request-limit comparison of the OpenAPI file with `docs/api/*.md`; example JSON keys; error codes (25 raised in code, all in the v2 docs) | gaps found and fixed as listed above; none left |
| The three bare-object models checked field by field against the v2 docs | all fields documented |
| Documented collection fields against the code | all found, except `fx_rate_applied` (marked reserved) |
| Relative links and backticked paths in the touched Markdown | all resolve except names of deleted files and old tracker names, which the log mentions on purpose |
| Read-only `gcloud` against `nomadfinance-prod` (list above) | 6 composite and vector indexes `READY` (the 3 the file lists, and the 3 unused ones of D-69); 2 single-field settings as in the file; 3 TTL policies `ACTIVE`; database `(default)` native, `asia-south1`, delete protection and point-in-time recovery off; 5 Scheduler jobs enabled; Cloud Run image tag `5d895ab` |

## Not done, and why

- **The live list of root collections.** The tool refused a script that read production documents, and I did not look for another way. So "every collection in Firestore is documented" is shown against the code, the data scripts, the rules, the index file and the production index and TTL settings. To close it, run this (it lists collection ids only, no documents) and compare with the collection map (D-309):

```powershell
Invoke-RestMethod -Method Post -Uri "https://firestore.googleapis.com/v1/projects/nomadfinance-prod/databases/(default)/documents:listCollectionIds" -Headers @{ Authorization = "Bearer $(gcloud auth print-access-token)"; "x-goog-user-project" = "nomadfinance-prod" } -ContentType "application/json" -Body "{}" | ConvertTo-Json
```

- **The deployed security rules** were not read back from production; `gcloud` has no command for it. The workflow deploys `frontend/firestore.rules` from `main` after its tests pass (D-313).
- **Three empty folders** are still on disk (`infra/cloud-run/`, `infra/firebase/`, `docs/architecture/`): the delete was refused in the session. Remove them by hand; git does not track empty folders.
- **The PowerShell variant** of the commands was not run in PowerShell; everything ran in Git Bash.
- **Integration tests that need the emulators** were not run: no application code changed. The 19 that do not need them were.
- **Review by a teammate**, which the Documentation checklist asks for.

## Definition of Done (Documentation, and the two lines of the tracker)

- [x] Written in Markdown
- [x] Consistent headings, lists and code blocks
- [ ] Reviewed by at least one other teammate (the tracker lists Aditya as owner and Devam as reviewer)
- [x] Committed to `/docs` or updated at the file's own source
- [x] No attribution to a tool, and no chat-style opener
- [x] **Contract diff vs live OpenAPI is empty.** `openapi.json` equals the document built from the code, every route is in `docs/api/`, and the field, limit, enum and error-code comparisons are clean. The three bare-object responses are the exception the file cannot show; their fields were checked against the models (D-308)
- [~] **Every collection in Firestore is documented.** True for every collection the code, the data scripts and the rules name, and every index and TTL production holds. The list of collections that exist in production is the one check not done (D-309)

## Noticed, not fixed

D-308 to D-313 in [`docs/deferred-items.md`](../deferred-items.md): **D-308** (three response objects are bare `object` in the OpenAPI file), **D-309** (list the live root collections), **D-310** (Firestore delete protection and point-in-time recovery are off), **D-311** (three places where the model is looser than the behaviour), **D-312** (tracker rows NF-P4-017 and NF-P4-020 are the same work), **D-313** (two shared rules files to tidy).

## Commit

Branch: `docs/NF-HR-013-docs-contract-final-v2` (already created; the edits are unstaged).

```text
docs(api): export OpenAPI and reconcile API and data model docs
Refs: NF-HR-013
```
