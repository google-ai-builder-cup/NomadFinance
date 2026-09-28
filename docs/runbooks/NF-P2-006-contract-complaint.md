# NF-P2-006 — Contract Shield: Complaint Letter

## Summary

Step 6 of Contract Shield. When step 4 finds clauses with `risk == "danger"`, `generate_complaint()` (and `POST /api/v1/contracts/complaint`) writes a formal complaint to the host country's labor authority, filled into a curated letter frame.

The letter comes in two languages: `letter_text` in the language the authority works in (`en`, `ko`, `ms`, `ja`), ready to send, and `worker_copy` in the worker's own language so they can read what they are sending. When both are the same language, `worker_copy` is `null`. The worker's name, contact details and start date are `[bracketed blanks]` in both texts, in the same places.

The authority, its channels and the template type are read from `complaint_templates/{country}/types/general` by code. Gemini only returns the two texts.

The task has two halves: the curated data and its loader (`data-scripts`), and the step itself (`backend`).

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/complaint-templates/{SG,KR,MY,JP,HK,AU}.json` | New: one `general` template per country, with authority, channels, sources, letter language and frame |
| `data-scripts/src/validators/complaint_template.py` | New: `ComplaintTemplateFile` and the checker (`python -m src.validators.complaint_template`) |
| `data-scripts/src/loaders/complaint_templates.py` | New: validates, then writes `complaint_templates/{country}` and `.../types/{type}` in one batch per country |
| `data-scripts/src/config.py` | `COMPLAINT_TEMPLATES_DIR` |
| `data-scripts/tests/test_complaint_template.py`, `test_complaint_template_loader.py` | New: 51 tests |
| `data-scripts/README.md` | Section for the checker and loader |
| `backend/app/prompts/contract/complaint.v2.yaml` | New; **replaces `complaint.v1.yaml`, which is removed** (no stored result used v1) |
| `backend/app/schemas/contract_complaint.py` | New: `ContractComplaintRequest`, `ContractFacts`, `ComplaintTemplate`, `ComplaintAnswer`, `ContractComplaint`, `LetterLanguage` |
| `backend/app/repositories/complaint_template_repo.py` | New: read-only `ComplaintTemplateRepository`, same pattern as `labor_law_repo.py` |
| `backend/app/services/contract/complaint.py` | `generate_complaint()` and its three errors (was an empty stub) |
| `backend/app/api/v1/contracts.py` | `POST /api/v1/contracts/complaint` |
| `backend/app/config.py` | `gemini_complaint_timeout_seconds` (default 60 s) |
| `backend/tests/unit/services/test_contract_complaint.py` | Service: violations, template lookup, two languages, unfilled markers, injection guard |
| `backend/tests/unit/test_complaint_template_files.py` | The shipped templates against the backend's vocabulary |
| `backend/tests/integration/api/test_contracts_complaint.py` | Endpoint: shape, 404, 422, 502, Gemini errors, auth, OpenAPI |
| `backend/tests/integration/api/test_contracts_complaint_live.py` | Opt-in live test, 5 calls (`RUN_LIVE_GEMINI=1`) |
| `backend/tests/unit/test_prompt_loader.py` | Expected prompt list: `contract/complaint.v2` |
| `docs/api/endpoints.md`, `docs/pipelines/contract-shield.md`, `docs/data-model/collections/contracts.md`, `backend/app/prompts/README.md` | Endpoint, step 6, the `complaint` map, the prompt table |

No shared files (`requirements*.txt`, `Dockerfile`, `firestore.rules`, workflows, ...) were touched. `firestore.rules` already lets signed-in users read `complaint_templates/**`.

## Decisions

1. **`general` templates only.** One template per country covers every violation; the clause categories are named inside the letter. The validator still accepts a category id as a template type, and the repository takes a type, so category letters can be added later without a schema change.
2. **Two languages in one call.** A worker who cannot read Korean cannot check a Korean letter before sending it, so the same call also returns a copy in the worker's language. One call, not a call plus a translation, so the two texts say the same thing.
3. **`worker_copy` is dropped by code when the languages match**, whatever Gemini returned, and is required when they differ (a missing copy is a 502).
4. **Authority, channels, `template_type`, `letter_language` and `violation_count` are set by code.** Prompt v1 asked the model to return `authority_name` and `template_type`; v2 does not, so a wrong authority can only come from the curated file.
5. **Blanks, not guesses, for what only the worker knows.** No name, phone number or start date is invented. The endpoint takes no worker name; the report UI can fill blanks later.
6. **Unfilled markers are checked against the template's own `placeholders` list**, so a clause that happens to contain `{{` cannot cause a false 502.
7. **`channels` and `authority_url` are in the response**, beyond the three fields of the stored `complaint` map, because a letter is useless without where to send it. `contracts.md` documents the extended map.
8. **No violation is a 422, not an empty 200**, same as step 4's "no terms". The pipeline (D-53) decides not to call the step and stores `complaint: null`.
9. **A new repository file** rather than reusing `labor_law_repo.py`: one repository per collection is the pattern in `app/repositories/`.
10. **No version number on templates.** Unlike labor laws, a stored report keeps the letter it was made with; a changed template only reaches new letters.
11. **The loader deletes a type removed from a file**, in the same batch, so Firestore always matches the files.
12. **Not added to `scripts/load_bootstrap.sh`.** Loading production data is a separate, deliberate step.

## Flow

```
POST /api/v1/contracts/complaint
  {host_country, clauses, contract_facts?, worker_language}
  auth (401), body checked (422), AI rate limit (429)
  generate_complaint(...)                                   [services/contract/complaint.py]
    └─ violations = clauses with risk == "danger", by index    → none: NoViolationsError (422)
    └─ ComplaintTemplateRepository.get_template(country, "general")
                                                               → none: ComplaintTemplateNotFoundError (404)
    └─ GeminiClient.generate_structured(
         operation="contract.complaint", tier=REASONING, timeout=60s,
         system=complaint.v2 system, contents=complaint.v2 user,
         response_model=ComplaintAnswer)                    3 attempts on timeout/503/429
    └─ checks: letter present, copy present unless same language, no placeholder left
                                                               → ComplaintIncompleteError (502)
  200 {template_type, authority_name, authority_url, channels, letter_language, letter_text,
       worker_language, worker_copy, violation_count}
```

## All commands, in order

### 1. Data: check, dry-run, load

From `data-scripts/` with its virtual environment active.

```bash
python -m src.validators.complaint_template --require-all
python -m src.loaders.complaint_templates --dry-run --require-all
```

Load into Firestore only when the team says so (it writes `complaint_templates/**` in `nomadfinance-prod`):

```bash
python -m src.loaders.complaint_templates
```

### 2. Checks

```bash
# data-scripts/
ruff check . && black --check . && mypy src && python -m pytest -q
# backend/
ruff check . && black --check . && mypy app && mypy app tests && python -m pytest -q
```

### 3. Live test (5 reasoning calls)

```bash
cd backend
RUN_LIVE_GEMINI=1 python -m pytest tests/integration/api/test_contracts_complaint_live.py -v -s
```

Templates are read from the curated files, not Firestore. Needs `GEMINI_API_KEY` in `backend/.env.local` and reasoning-tier quota (D-58).

### 4. Try the endpoint by hand

Start the API (`uvicorn app.main:app --host 127.0.0.1 --port 8080`) with the templates loaded, get a Firebase ID token as in the NF-P2-001 runbook, then use the example in `docs/api/endpoints.md`.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `data-scripts`: `pytest -q` | 117 passed (51 new) |
| `data-scripts`: `ruff check .`, `black --check .`, `mypy src` | Pass |
| `python -m src.validators.complaint_template --require-all` | 6 files OK |
| `python -m src.loaders.complaint_templates --dry-run --require-all` | All six countries validate; nothing written |
| `backend`: `pytest -q` | 367 passed, 22 skipped (the skips include the 5 new live tests) |
| The same without Google credentials (as CI) | 367 passed |
| `backend`: `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass |
| **Live Gemini test** | **Not passed: could not run.** All 5 calls, and a later retry of one, got `429 RESOURCE_EXHAUSTED` (`gemini-3.5-flash`, free tier, limit 20): the quota was already used up today, see D-58. `complaint.v2` has therefore **not** been checked against the real model |
| Production Firestore load | Not run |

## Not verified, and how

- **`complaint.v2` against real Gemini.** Rerun step 3 once the reasoning quota resets, or with `GEMINI_MODEL_REASONING` pointing at another model. The test checks that both letters have no `{{marker}}`, keep the `[blanks]`, name the employer, quote the 40% deduction, leave out the safe clause, and are in the right scripts (Devanagari, Hangul, Kana/Kanji). Read the printed letters too: the checks cannot judge tone or Korean, Malay and Japanese wording. The letters should be read by someone who reads those languages before any real use.
- **The authority details in the six files** were read from the authorities' pages on 2026-09-28 and are marked as drafts (`reviewed_by` is empty). A second person should open each page in `sources` and compare the channels.
- **Emulator round-trip of the loader**: the loader is tested against a fake Firestore client (writes, batching, stale-type deletion), not the emulator or production.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 404 `No complaint letter is available yet for <country>` | The templates are not loaded in that Firestore project: run the loader (step 1) |
| 502 `The AI service returned an unusable answer` | The answer had no letter, no copy, or left a `{{marker}}` unfilled. Retry; if it repeats, check `complaint.v2` |
| 422 `nothing to report` | No clause has `risk` `danger`. The report has no complaint to write |
| 503 with `429 RESOURCE_EXHAUSTED` in the logs | Reasoning-tier free-tier quota (D-58) |
| The loader reports a problem in a file | It names the file and field; nothing is written until all files pass |
| Adding a language for a new authority | Add it to `LETTER_LANGUAGES` in `complaint_template.py` and to `LetterLanguage` and `LETTER_LANGUAGE_NAMES` in the backend; a test compares the lists |
| Changing the prompt | Add `complaint.v3.yaml`, load it in `complaint.py`, update the tests and the prompt README. Never edit a version that has been used |

## Definition of Done

Gemini pipeline step:

- [x] Correct model tier: reasoning (`gemini-3.5-flash`, ADR-002)
- [x] Structured output via Pydantic `response_schema` (`ComplaintAnswer`)
- [x] Retry via tenacity (unchanged client; 3 attempts on timeout, 503, 429)
- [x] Timeout set: 60 s (`GEMINI_COMPLAINT_TIMEOUT_SECONDS`)
- [x] Token usage logged (`gemini_call operation=contract.complaint ...`, automatic in the client)
- [x] Prompt in a versioned file (`contract/complaint.v2.yaml`)
- [ ] Tested with 3+ diverse inputs against real Gemini: the live test is written (5 inputs across 5 countries and languages) but could not run; the unit and API tests cover the logic with a fake client

Backend endpoint:

- [x] Pydantic request and response models
- [x] Firebase token check (401 without it)
- [x] Structured request logging: from NF-P1-028, automatic
- [x] Specific error codes (401, 404, 422, 429, 502, 503, 504)
- [x] AI rate limit applied (`limit_ai_calls`)
- [x] `docs/api/endpoints.md` updated
- [ ] Manual Swagger try-out with a real token: yours (step 4)

Data ingestion script:

- [x] Idempotent, validates before writing, logs counts and errors
- [x] Uses the admin SDK client (`get_firestore_client`)
- [x] Documented in `data-scripts/README.md`
- [ ] Run against Firestore: not run; on your word only

Documentation: written in Markdown, in `docs/`; review by a teammate is still open.

## Commit and PR

Branch: `feature/contract-complaint` (already checked out). Suggested commit message, one line:

```
feat(contracts): generate complaint letters for violations
Refs: NF-P2-006
```

## For teammates

- **Aditya (NF-P2-013, letter preview and download):** `POST /contracts/complaint`. Preview `worker_copy` (or `letter_text` when it is null), download and copy `letter_text`, and list `channels` as where to send it.
- **Devam (NF-P2-007, cache):** the letter depends on the danger clauses, the facts, the template and `complaint.v2`, not on the report language. Store it in the source report and reuse it.
- **Everyone:** `GEMINI_COMPLAINT_TIMEOUT_SECONDS` is optional, default 60. No new packages.
