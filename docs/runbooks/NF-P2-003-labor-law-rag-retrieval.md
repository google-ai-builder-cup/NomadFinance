# NF-P2-003 — Contract Shield: Labor Law RAG Retrieval

## Summary

Step 3 of Contract Shield. Given the `host_country` and `job_type` that step 2 (NF-P2-002) detected, `get_labor_law_context()` (and `GET /api/v1/contracts/labor-law/{host_country}`) reads the country's curated labor law from Firestore and returns it in a structured shape:

- **15 categories** (`minimum_wage`, `working_hours`, ... see [labor_laws.md](../data-model/collections/labor_laws.md)), each with `coverage`, `title`, `summary`, `confidence` and `notes`
- **`applicable_variant`**: the one variant (of possibly several) that applies to the given `job_type`, resolved here rather than left to step 4 — a live-in domestic worker and a construction worker can be under different rules for the same category
- **`law_version`**: `labor_laws/{country}/_meta/current.version`, the number a stored contract report will be cached against (`docs/data-model/versioning.md`)

There is **no Gemini call** in this step — it is a plain Firestore read, which is why it has its own "none (Firestore)" tier in the pipeline table and no prompt file.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/contract.py` | `LawLimit`, `LawReference`, `LaborLawVariant`, `LaborLawRule`, `LaborLawContext`; `LawCoverage`, `LawConfidence`, `LawLimitPeriod` value lists |
| `backend/app/repositories/labor_law_repo.py` | `LaborLawRepository`: `get_version()`, `get_rules()` over `labor_laws/{country}` |
| `backend/app/services/contract/rag.py` | `get_labor_law_context()`, `_applicable_variant()`, `LaborLawNotFoundError` |
| `backend/app/api/v1/contracts.py` | `GET /api/v1/contracts/labor-law/{host_country}` |
| `backend/tests/unit/services/test_contract_rag.py` | Variant resolution, law_version, not-found cases |
| `backend/tests/integration/repositories/test_labor_law_repository.py` | Repository against the Firestore Emulator (opt-in) |
| `backend/tests/integration/api/test_contracts_labor_law.py` | Endpoint: shape, auth, validation, 404, OpenAPI |
| `docs/data-model/collections/labor_laws.md` | Task list line already named NF-P2-003; no field changes needed |
| `docs/api/endpoints.md`, `docs/pipelines/contract-shield.md` | Endpoint section; step 3 in detail |

No shared files (`requirements*.txt`, `Dockerfile`, workflows, ...) were touched.

## Decisions

1. **The applicable variant is resolved here, not in step 4.** `job_type` is already known from step 2, and picking the right law for a worker's group is a retrieval concern, not a reasoning one. The full `variants` array is kept on each rule too, in case a caller ever needs another job type from the same response.
2. **`host_country` is a plain `HostCountryCode`, never accepted as null.** D-55 (what to do when detection found no country) is the pipeline owner's decision, not this step's; this step simply isn't called until a country has been chosen.
3. **A country with nothing loaded yet is a 404, not an empty 200.** `_meta/current` missing or the `rules` subcollection empty both mean NF-P1-018 has not run for that country — treated as "not found" so a silently empty report can't reach a worker.
4. **`GET`, not `POST`.** Unlike extract/detect, this step takes no free-form body — a country code and a job type — and reads without side effects, so it fits a path parameter plus a query parameter.
5. **No AI rate limit.** Nothing here calls Gemini, so only the API-wide budget (60/min) applies; `limit_ai_calls` would be wrong.
6. **Blocking Firestore calls run via `run_in_threadpool`**, matching `services/remittance/rates.py` — the repository itself stays synchronous like every other repository in the codebase (`rate_repo.py`, `base.py`).
7. **An endpoint, not only a function**, same reasoning as NF-P2-002: lets the team try step 3 in Swagger once step 2 has run, ahead of the full pipeline (D-53) existing.

## Flow

```
GET /api/v1/contracts/labor-law/{host_country}?job_type=...
  auth (401), host_country/job_type validated against the enums (422)
  get_labor_law_context(country, job_type, repo)          [services/contract/rag.py]
    └─ repo.get_version(country)     labor_laws/{country}/_meta/current.version
    └─ repo.get_rules(country)       labor_laws/{country}/rules/{category} (15 docs)
    └─ version is None or no rules  → LaborLawNotFoundError → 404
    └─ per rule: pick the variant whose applies_to contains job_type, else the `all` variant
  200 {country, job_type, law_version, rules: [{category, coverage, title, summary,
       applicable_variant, variants, references, confidence, notes}, ...]}
```

## All commands, in order

From `backend/` with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash, `source .venv/bin/activate` on macOS and Linux).

### 1. Checks (the same ones CI runs, plus tests in mypy)

```bash
ruff check app tests
black --check app tests
mypy app
mypy app tests
python -m pytest -q
```

If `mypy` complains about a missing `limits` or `yaml` stub after pulling, install the pinned packages: `pip install -r requirements-dev.txt`.

### 2. Repository test against the Firestore Emulator (opt-in)

```bash
firebase emulators:start --only firestore
```

In another shell:

```bash
FIRESTORE_EMULATOR_HOST=localhost:8080 python -m pytest tests/integration/repositories/test_labor_law_repository.py -v
```

### 3. Try the endpoint by hand

Start the API (`uvicorn app.main:app --host 127.0.0.1 --port 8080`), get a Firebase ID token as in the NF-P2-001 runbook, then either point `FIRESTORE_EMULATOR_HOST` at a running emulator and load a country with `python -m src.loaders.ilo_natlex --only JP` from `data-scripts/`, or just check the validation and 404 paths without any loaded data:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/contracts/labor-law/JP?job_type=domestic_worker"
```

Expected without any data loaded: `404 {"detail": "No labor-law data is available yet for JP."}`. With `JP` loaded: `200` with 15 rules and `law_version: 1`. Or use the Swagger page at http://127.0.0.1:8080/docs.

Whole flow so far, steps 1 to 3: send a file to `/contracts/extract`, its `text` to `/contracts/detect`, then that response's `host_country` and `job_type` to `/contracts/labor-law/{host_country}`.

## Verified results (2026-09-29)

| Check | Result |
|---|---|
| `pytest -q` | 270 passed, 14 skipped (12 pre-existing live/PDF-dependent tests, plus this task's 2 emulator-only repository tests) |
| The same without Google credentials (as CI) | 270 passed |
| `ruff check app tests`, `black --check app tests`, `mypy app`, `mypy app tests` | Pass |
| Firestore Emulator repository test | Not run locally (no emulator running on this machine); covered by unit tests against a fake repository instead |
| Docker image build | Not run locally (Docker is not available on this machine); `Dockerfile` and `.dockerignore` are unchanged |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 404 for a real, curated country | NF-P1-018 has not been run against the Firestore instance you're pointed at (local emulator vs. `nomadfinance-prod`). Run `python -m src.loaders.ilo_natlex` from `data-scripts/` |
| 422 on `host_country` | Only `SG`, `KR`, `MY`, `JP`, `HK`, `AU` are valid; anything else (including `AE`) is rejected before Firestore is touched |
| 422 on `job_type` | Missing from the query string, or not one of the seven onboarding job types |
| `applicable_variant` looks like the general rule when you expected an exception | The curated file has no variant naming that `job_type` for this category; check `data-scripts/data/source/labor-laws/<CC>.json` — a missing job-type variant is a curation gap (NF-P1-017), not a bug here |
| Repository integration test skipped | `FIRESTORE_EMULATOR_HOST` is not set; start the emulator first (see command above) |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification (401 without it)
- [x] Structured logging with request ID, user ID (hashed), timing — from NF-P1-028, automatic
- [x] Error handling with specific HTTP status codes (401, 404, 422, 429)
- [ ] Manual test via Swagger `/docs` successful: yours (step 3 above), once you have a Firestore instance with at least one country loaded
- [x] OpenAPI docs updated (auto-generated; checked by `test_the_endpoint_is_listed_in_openapi`)
- [x] `docs/api-contract.md` updated — this repo keeps it as `docs/api/endpoints.md`; updated there
- [x] Rate limiting applied: the API-wide budget only (no `limit_ai_calls`, nothing calls Gemini)

## Commit and PR for this task

Branch: `feature/contract-law-rag` (already checked out).

```bash
git add backend docs
git status
```

```bash
git commit -m "feat(contracts): fetch labor law rules by host country" -m "Refs: NF-P2-003"
```

PR title: `feat(contracts): labor-law RAG retrieval by host country and job type (NF-P2-003)`

## For teammates

- **Everyone:** no new packages and no new settings; after pulling, nothing to install except what CI already installs (or `pip install -r requirements-dev.txt` if mypy complains about stubs).
- **Devam (NF-P2-004, clause comparison):** call `get_labor_law_context(country, job_type, repo)` and compare each clause against `rules[i].applicable_variant.requirements` — you do not need to re-resolve `job_type` against `variants` yourself. Skip the whole step for `document_kind == "loan_agreement"` (that's on step 2's output, not this one's). Record `law_version` on the report for the cache key (NF-P2-007).
- **Team:** the pipeline as a whole still has no owner (D-53); this step has no data to seed until NF-P1-017/018 finish curating and loading all six countries (currently only whichever files have been curated are loaded).

## Not covered here

- Steps 4 to 6 and the pipeline as a whole (`docs/pipelines/contract-shield.md`, D-53)
- What to do when `host_country` is null (D-55) — still open, still the pipeline owner's call
- Curating or loading the labor-law data itself (NF-P1-017, NF-P1-018) — already built, untouched here
- Response caching (NF-P2-007)
