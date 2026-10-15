# NF-P2-005 — Contract Shield: Translation Step

## Summary

Step 5 of Contract Shield. Given a finished, English report from step 4 (`ContractComparison`) and the contract's `full_text` from step 1, `translate_report()` (and `POST /api/v1/contracts/translate`) translates it into one of the six UI languages: `full_text`, `summary`, and each clause's `text`, `explanation` and `recommendation`.

`category`, `risk`, `law_reference`, `index`, `number`, `page` and `block_ids` are **never sent to, or taken from, the model** — they are carried straight over from the source clauses. `category` and `risk` are the codes the UI keys its 🟢🟡🔴 flags on (NF-P2-011), so a mistranslated word must never be able to change one.

Classification tier (`gemini-3.1-flash-lite`, prompt `contract/translate.v1`, already written for NF-P1-029) — fast per call, but the output is a whole report, so it gets its own 60 s timeout rather than the 30 s default.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/contract.py` | `ReportLanguage` (the six UI languages) |
| `backend/app/schemas/contract_translate.py` | New: `ContractTranslateRequest`, `TranslatedClauseAnswer`, `TranslationAnswer`, `TranslatedClause`, `ContractReportTranslation`, `MAX_CLAUSES` |
| `backend/app/services/contract/translator.py` | `translate_report()`, `_report_json()`, `_merge()`, `TranslationIncompleteError`, `TRANSLATE_PROMPT`, `LANGUAGE_NAMES` |
| `backend/app/api/v1/contracts.py` | `POST /api/v1/contracts/translate` |
| `backend/app/config.py` | `gemini_translate_timeout_seconds` (default 60 s) |
| `backend/tests/unit/services/test_contract_translator.py` | Merge logic, injection guard, incomplete-answer error, prompt/tier |
| `backend/tests/integration/api/test_contracts_translate.py` | Endpoint: shape, auth, validation, Gemini/incomplete-answer error mapping, OpenAPI |
| `docs/api/endpoints.md` | Endpoint section; step 5 in detail |

No shared files (`requirements*.txt`, `Dockerfile`, workflows, ...) were touched. `backend/app/prompts/contract/translate.v1.yaml` already existed (built with NF-P1-029) and was not changed.

## Decisions

1. **Only translatable fields go to the model.** `_report_json()` sends `index`, `category`, `risk`, `text`, `explanation`, `recommendation` per clause — never `law_reference`, `number`, `page` or `block_ids`. Smaller prompt, and one less thing an odd answer could corrupt.
2. **`category` and `risk` are round-tripped but never trusted.** The prompt tells the model to keep them unchanged (they're codes, not text) so it keeps its place in the report, but `_merge()` always takes both from the source clause regardless of what comes back. Same reasoning as step 4's `law_reference`: a field that drives worker-facing risk flags does not get to depend on model output.
3. **A clause the model dropped is a 502, not a partial report.** `_merge()` raises `TranslationIncompleteError` if any source clause's `index` is missing from the answer. A worker silently missing one assessed clause — possibly a danger one — is worse than a retry.
4. **`full_text` is translated too**, not just the report metadata, because `reports/{lang}.full_text` in the data model is "the translation" for a non-source report (`docs/data-model/collections/contracts.md`).
5. **A new `gemini_translate_timeout_seconds` (60 s), not the 30 s default.** The call is classification tier (fast per token) but the output is comparable in size to extraction's — a full contract plus every clause, written out again in another language.
6. **`ReportLanguage` lives in `schemas/contract.py`**, next to the other contract-domain value lists, since it is exactly the six `frontend/src/i18n/*.json` files and will be reused by the language switcher (NF-P2-012) and the complaint letter (NF-P2-006) as-is.
7. **An endpoint, not only a function**, same reasoning as steps 2 to 4: lets the report UI (NF-P2-011/012) and the team try step 5 in Swagger ahead of the full pipeline (D-53) existing.
8. **A closing tag inside a clause's text is neutralised** before it goes into the prompt's `<report>` section, same pattern as step 2's `<contract_text>` and step 4's `<contract_blocks>`.

## Flow

```
POST /api/v1/contracts/translate
  {full_text, summary, clauses, target_language}
  auth (401), body checked: non-empty text, 1 to 200 clauses, char limits (422)
  translate_report(full_text, summary, clauses, target_language, gemini)   [services/contract/translator.py]
    └─ _report_json(): index, category, risk, text, explanation, recommendation only, </report> neutralised
    └─ GeminiClient.generate_structured(
         operation="contract.translate", tier=CLASSIFICATION, timeout=60s,
         system=translate.v1 system, contents=translate.v1 user with the report inside <report>,
         response_model=TranslationAnswer)                3 attempts on timeout/503/429
    └─ _merge(): match by index, reattach law_reference/number/page/block_ids,
                 keep category/risk from the source, strip recommendation when risk == "safe"
                 → missing index → TranslationIncompleteError
  200 {language, full_text, summary, clauses: [{index, number, page, text, category, risk,
       law_reference, explanation, recommendation, block_ids}, ...]}
```

## All commands, in order

From `backend/` with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash, `source .venv/bin/activate` on macOS and Linux).

### 1. Checks (the same ones CI runs, plus tests in mypy)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it (`.github/workflows/backend-ci.yml`):

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
```

If `mypy` complains about a missing `limits` or `yaml` stub after pulling, install the pinned packages: `pip install -r requirements-dev.txt`.

### 2. Try the endpoint by hand

Start the API (`uvicorn app.main:app --host 127.0.0.1 --port 8080`), get a Firebase ID token as in the NF-P2-001 runbook, then:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"full_text": "EMPLOYMENT CONTRACT ...", "summary": "The employer keeps the passport.",
       "target_language": "hi",
       "clauses": [{"index": 1, "number": "2", "page": 1, "text": "The employer keeps the passport.",
         "category": "passport_retention", "risk": "danger", "law_reference": "Passports Act, s. 47",
         "explanation": "The employer keeps your passport; the rule forbids it.",
         "recommendation": "Ask to keep your own passport.", "block_ids": [3]}]}' \
  http://127.0.0.1:8080/api/v1/contracts/translate
```

Expected: `"language": "hi"`, translated `summary`/clause `text`/`explanation`/`recommendation` in Devanagari script, and `"category": "passport_retention"`, `"risk": "danger"`, `"law_reference": "Passports Act, s. 47"` unchanged from the request. Or use the Swagger page at http://127.0.0.1:8080/docs.

Whole flow, steps 1, 4 and 5: send a file to `/contracts/extract`, its `blocks` (plus `host_country`/`job_type`/`document_kind` from `/contracts/detect`) to `/contracts/compare`, then that response's `summary`/`clauses` and the extract step's `text` (as `full_text`) to `/contracts/translate`.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `pytest -q` | 324 passed, 17 skipped (pre-existing live/PDF-dependent and emulator-only tests) |
| The same without Google credentials (as CI) | 324 passed |
| `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass |
| Live Gemini test | Not added; no `RUN_LIVE_GEMINI` opt-in test was written for this step (see Not covered here) |
| Docker image build | Not run locally (Docker is not available on this machine); `Dockerfile` and `.dockerignore` are unchanged |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 502 `The AI service returned an unusable answer` | Either Gemini's JSON did not match `TranslationAnswer` (schema-invalid output) or it left a clause's `index` out of `clauses`. Retry; if it repeats for one report, the clause count may be near `MAX_CLAUSES` (200) — check the input |
| 422 on `target_language` | Only `en`, `hi`, `tl`, `id`, `ne`, `bn` are valid (the six `frontend/src/i18n/*.json` files); not case-normalised, so `"HI"` is rejected too |
| A clause's `category`/`risk` looks wrong after translation | It can't — they're always taken from the request, never from Gemini's answer. Check the `clauses` you sent |
| Translation reads oddly literal or too formal | The prompt asks for "everyday words a worker would use"; if it drifts, that's a `translate.v2` change, not a code bug |
| Changing the prompt | Add `translate.v2.yaml`, load it in `translator.py` and update the tests. Never edit a version that has been used |

## Definition of Done (Gemini Pipeline Step)

- [x] Correct model tier: classification (`gemini-3.1-flash-lite`, ADR-002)
- [x] Structured output via Pydantic `response_schema` (`TranslationAnswer`), no free-text parsing
- [x] Retry logic via tenacity (unchanged; 3 attempts on timeout, 503, 429)
- [x] Timeout set: a dedicated 60 s (`GEMINI_TRANSLATE_TIMEOUT_SECONDS`), not the 30 s default
- [x] Token usage logged (`gemini_call operation=contract.translate ...`, automatic in the client)
- [x] Prompt in a versioned file (`contract/translate.v1.yaml`, already existed)
- [x] Tested with 3+ diverse inputs: a plain translation, category/risk/law_reference/numbers held constant, a safe clause dropping its recommendation, an incomplete answer, a prompt-injection attempt inside clause text

Backend endpoint items:

- [x] Pydantic request and response models
- [x] Firebase token check (401 without it)
- [x] Structured request logging: from NF-P1-028, automatic
- [x] Specific error codes (401, 422, 429, 502, 503, 504)
- [x] AI rate limit applied (`limit_ai_calls`)
- [x] `docs/api/endpoints.md` updated
- [ ] Manual Swagger try-out with a real token: yours (step 2 above)

## Commit and PR for this task

Branch: `feature/contract-translate` (already checked out).

```bash
git add backend docs
git status
```

```bash
git commit -m "feat(contracts): translate contract reports into worker languages" -m "Refs: NF-P2-005"
```

PR title: `feat(contracts): translate the contract report into a worker's language (NF-P2-005)`

## For teammates

- **Everyone:** no new packages; `GEMINI_TRANSLATE_TIMEOUT_SECONDS` is optional, default 60. Nothing else to install beyond what CI already runs.
- **Pranjal (NF-P2-006, complaint letter):** this step doesn't touch the complaint letter. Generate it from the English `ContractComparison` first; if it needs translating for a non-English worker, either reuse `translate_report`'s pattern or extend `ContractTranslateRequest` with a `letter_text` field — whichever fits the complaint template's shape better once you're building it.
- **Aditya (NF-P2-011/012, report UI and language switcher):** call `/contracts/translate` again with a different `target_language` on the same `full_text`/`summary`/`clauses` to switch languages without re-running steps 1 to 4.
- **Team:** the pipeline as a whole still has no owner (D-53); this step is stateless like steps 1 to 4 — storing `reports/{lang}` with `content_hash`, `law_version`, `prompt_versions` and `models` is still unbuilt.

## Not covered here

- Storing `reports/{lang}` or the pipeline as a whole (D-53)
- The complaint letter (NF-P2-006) and whether/how it gets translated
- A live-Gemini opt-in test (`RUN_LIVE_GEMINI=1`), unlike steps 1, 2 and 4 — can be added alongside NF-P2-008's E2E testing if the team wants translation quality checked against the real model before the demo
- The report language switcher UI (NF-P2-012)
