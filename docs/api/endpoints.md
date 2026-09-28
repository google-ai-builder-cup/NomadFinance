# API Endpoints

Base URL: the Cloud Run service URL (local: `http://127.0.0.1:8080`).

All endpoints live under `/api/v1/` except `/health`. Interactive docs are served at `/docs` (Swagger) and the schema at `/openapi.json`.

## Authentication

Protected endpoints require a Firebase Auth ID token as a bearer token:

```
Authorization: Bearer <firebase-id-token>
```

Add `user: AuthenticatedUser = Depends(get_current_user)` (`app/dependencies.py`) to any
endpoint that isn't public. It verifies the token via the Firebase Admin SDK
(`app/core/security.py`) and returns the caller's `uid`/`email`/etc.; a missing, invalid,
expired or revoked token gets a `401`. Endpoints that skip this dependency are public and
must say so explicitly in their own doc section below.

| Method | Path | Auth | Rate limit | Owner task |
|---|---|---|---|---|
| GET | `/health` | Public | None | NF-P1-001 |
| POST | `/api/v1/contracts/extract` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P1-006 |
| POST | `/api/v1/contracts/detect` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-002 |
| GET | `/api/v1/contracts/labor-law/{host_country}` | Firebase ID token | 60/min API-wide only (no Gemini call) | NF-P2-003 |
| POST | `/api/v1/contracts/compare` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-004 |
| POST | `/api/v1/contracts/translate` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-005 |
| POST | `/api/v1/internal/refresh-rates` | Cloud Scheduler OIDC token only (not in `/docs`) | Exempt (NF-P1-027) | NF-P1-019 |
| DELETE | `/api/v1/users/me` | Firebase ID token, signed in within the last 5 minutes | 60/min API-wide | NF-P1-023 |

## Error format

Every error response is JSON with a single human-readable `detail` string, for example `{"detail": "The file is larger than 10 MB."}`. The frontend should pick its translated message by **status code** and treat `detail` as a fallback. Errors never contain stack traces, model names or Gemini API messages.

Gemini failures (any endpoint that calls Gemini) map to (`app/core/errors.py`):

| Status | When | Retry? |
|---|---|---|
| 503 + `Retry-After: 30` | Gemini quota hit or Gemini unavailable, after 3 attempts | Yes, after the header's seconds |
| 504 | Gemini timed out on every attempt | Yes |
| 502 | Gemini answered with empty, blocked or invalid output | Yes, once |
| 500 | Our request was rejected by Gemini (a bug on our side) | No |

## CORS, rate limits and request size (NF-P1-027)

**CORS.** Browsers may call the API from these origins only (`CORS_ALLOWED_ORIGINS` overrides them):

| `APP_ENV` | Allowed origins |
|---|---|
| `prod` | `https://nomadfinance-prod.web.app`, `https://nomadfinance-prod.firebaseapp.com` |
| `local` | `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:4173`, `http://127.0.0.1:4173` |

Allowed: methods `GET POST PUT PATCH DELETE`, request headers `Authorization`, `Content-Type`, `X-Request-ID`; no cookies (`allow_credentials` off). Readable by the page: `X-Request-ID`, `Retry-After`, `X-RateLimit-*`. Preflights are cached for 1 hour. Other origins get no CORS headers (preflight `400`). In local development the Vite dev server forwards `/api`, so CORS is not involved there.

**Rate limits.** Counted per signed-in user (the token's uid, hashed), or per IP for requests without a token (the last `X-Forwarded-For` entry on Cloud Run). Budgets use a moving one-minute window:

| Budget | Default | Applies to |
|---|---|---|
| API-wide | `RATE_LIMIT_DEFAULT` = `60/minute` | Every path under `/api/` except `/api/v1/internal/*`, shared across endpoints |
| Gemini | `RATE_LIMIT_AI` = `10/minute` | Endpoints that call Gemini (`Depends(limit_ai_calls)`), in addition to the API-wide budget |

`/health` and `/api/v1/internal/*` are never limited. Counted responses carry `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` (seconds). Over a budget:

| Status | `detail` | Headers |
|---|---|---|
| 429 | `Too many requests. Please wait a minute and try again.` | `Retry-After` (seconds), `X-RateLimit-*` of the budget that ran out |

Counts live in each Cloud Run instance's memory: with up to 2 instances a caller can get up to twice the budget, and counts reset when an instance restarts.

**Request size.** Any request body over `UPLOAD_MAX_BYTES` + 64 KB (10 MB + 64 KB by default) gets `413` `The request is larger than 10 MB.` before the body is read (declared `Content-Length`), or as soon as the limit is passed (no `Content-Length`).

---

## `GET /health`

Liveness probe for Cloud Run and uptime checks. Unversioned so its path never changes across API versions.

- **Auth:** public, no token required
- **Request:** no parameters, no body
- **Response `200`:** `HealthResponse` (`app/schemas/common.py`)

| Field | Type | Description |
|---|---|---|
| `status` | `"ok"` | Always `"ok"` when the process is serving |
| `version` | string | `APP_VERSION` setting |
| `environment` | string | `APP_ENV` setting: `local`, `staging` or `prod` |

Example:

```bash
curl -s http://127.0.0.1:8080/health
```

```json
{"status": "ok", "version": "0.1.0", "environment": "local"}
```

- **Errors:** none from the handler. If required settings are missing, the process refuses to start, so no response is served.

---

## `POST /api/v1/contracts/extract`

Transcribes an uploaded contract (PDF or phone photo) in its **original language**, clause by clause, using Gemini's extraction tier (`gemini-3.5-flash-lite` by default, prompt `contract/extract.v2`). Step 1 of Contract Shield (NF-P1-006, structure added in NF-P2-001). The file is held in memory for the request only; nothing is stored.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request:** `multipart/form-data` with one field `file`
  - Accepted: PDF, PNG, JPEG, WebP, HEIC/HEIF. The type is detected from the file's bytes; the filename and `Content-Type` are ignored.
  - Max size: 10 MB (`UPLOAD_MAX_BYTES`)
- **Time:** usually 3 to 5 s for a photo or a 2-page PDF, about 2.6 s per PDF page (15 pages: 39 s). Gemini sometimes hangs or slows down (seen: 76 s for 2 pages); the client retries after 30 s (photos) or 90 s (PDFs), up to 3 attempts, then answers 504. Show progress in the UI.
- **Response `200`:** `ContractExtractResponse` (`app/schemas/contract.py`)

| Field | Type | Description |
|---|---|---|
| `filename` | string or null | Name of the uploaded file, as sent by the client |
| `mime_type` | string | Type detected from the file bytes |
| `size_bytes` | integer | Size of the uploaded file |
| `page_count` | integer | Pages in the PDF; 1 for a photo |
| `title` | string or null | Document title as written |
| `legibility` | `good` / `partial` / `poor` | `partial`: some words are `[illegible]`; `poor`: much of the text could not be read, so ask for a clearer photo before analysing |
| `text` | string | Whole document in its original language, built from `blocks`: each block's number then its text, blocks separated by a blank line |
| `blocks` | array | The document in reading order, see below |

A block has `page` (from 1), `kind` (`heading`, `clause`, `paragraph`, `list_item`, `table`, `signature`, `other`), `number` (as printed: `"3"`, `"3.1"`, `"(a)"`, or null) and `text` (exact words, without the number; a table is one row per line, cells separated by ` | `, header row first).

Example (bash; in PowerShell use `curl.exe`):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/contracts/sample_contract_sg.pdf" http://127.0.0.1:8080/api/v1/contracts/extract
```

Real output, shortened:

```json
{
  "filename": "sample_contract_sg.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1924,
  "page_count": 2,
  "title": "STANDARD EMPLOYMENT CONTRACT - FOREIGN DOMESTIC WORKER",
  "legibility": "good",
  "text": "STANDARD EMPLOYMENT CONTRACT - FOREIGN DOMESTIC WORKER

Republic of Singapore

Employer: Tan Wei Ming, ...

1 Duration: 24 months from the date of arrival in Singapore.

...",
  "blocks": [
    { "page": 1, "kind": "heading", "number": null, "text": "STANDARD EMPLOYMENT CONTRACT - FOREIGN DOMESTIC WORKER" },
    { "page": 1, "kind": "paragraph", "number": null, "text": "Republic of Singapore" },
    { "page": 1, "kind": "clause", "number": "1", "text": "Duration: 24 months from the date of arrival in Singapore." }
  ]
}
```

A table block, from a live run:

```json
{ "page": 4, "kind": "table", "number": null, "text": "Item | Amount | Paid by
Placement fee | SGD 2,400 | Worker
Medical examination | SGD 120 | Employer" }
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 400 | `The uploaded file is empty.` | Zero-byte file |
| 401 | `Missing bearer token` / `Invalid authentication token` / ... | No, invalid, expired or revoked token |
| 413 | `The request is larger than 10 MB.` / `The file is larger than 10 MB.` | Whole request over the limit (refused before reading) / file part over `UPLOAD_MAX_BYTES` |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 uploads a minute (Gemini budget) or 60 API calls a minute |
| 415 | `Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).` | Any other file type, including Word files and renamed text files |
| 422 | `No readable document found. ...` | Gemini found no document text (selfie, landscape, blank page) |
| 422 | FastAPI validation list | No `file` field in the form |
| 502 / 503 / 504 / 500 | see Error format above | Gemini failure |

## `POST /api/v1/contracts/detect`

Finds a contract's language, the country whose labor law applies, the kind of document and the worker's job type, and reads the employer, agency and basic salary when the document states them. Step 2 of Contract Shield (NF-P2-002), Gemini extraction tier (prompt `contract/detect.v2`). Send the `text` returned by `/contracts/extract`. Nothing is stored.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request:** JSON `{ "text": "<whole contract text, original language>" }`. Surrounding whitespace is trimmed; the text must not be empty and at most 200,000 characters (a 15-page contract is about 60,000).
- **Time:** about 1.5 to 2 s.
- **Response `200`:** `DetectedContract` (`app/schemas/contract.py`)

| Field | Type | Description |
|---|---|---|
| `language` | string or null | ISO 639-1 code of the main language (`en`, `ms`, `ko`, ...); null if it could not be told |
| `host_country` | `SG` / `KR` / `MY` / `JP` / `HK` / `AU` or null | Where the work is done. **Null for a contract from any other country or one that shows none: ask the worker** |
| `host_country_evidence` | string | What showed the country, e.g. `"laws of the Republic of Singapore"`; empty when `host_country` is null |
| `document_kind` | `employment_contract` / `recruitment_agreement` / `loan_agreement` / `other` | Loan agreements are not compared against labor law |
| `job_type` | `domestic_worker` / `manufacturing_worker` / `care_worker` / `plantation_worker` / `construction_worker` / `working_holiday` / `other` | Same values as the profile's job type |
| `employer_name`, `agency_name` | string or null | As written in the document |
| `salary_amount` | number or null | Basic pay only, without allowances or overtime |
| `salary_currency` | string or null | ISO 4217 code, e.g. `SGD` |
| `salary_period` | `month` / `week` / `day` / `hour` or null | Null when not stated or any other period |

Example (bash; in PowerShell use `curl.exe` and a here-string or a JSON file):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text": "EMPLOYMENT AGREEMENT - CONSTRUCTION LABOURER\n\nEmployer: Southern Cross Builders Pty Ltd, Sydney NSW, Australia\n\n2. Pay: AUD 230 per day worked, paid weekly.\n3. Governed by the Fair Work Act 2009 (Cth)."}' \
  http://127.0.0.1:8080/api/v1/contracts/detect
```

Real output (2026-09-28):

```json
{
  "language": "en",
  "host_country": "AU",
  "host_country_evidence": "Fair Work Act 2009 (Cth)",
  "document_kind": "employment_contract",
  "job_type": "construction_worker",
  "employer_name": "Southern Cross Builders Pty Ltd",
  "agency_name": null,
  "salary_amount": 230.0,
  "salary_currency": "AUD",
  "salary_period": "day"
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | `Missing bearer token` / `Invalid authentication token` / ... | No, invalid, expired or revoked token |
| 422 | FastAPI validation list | No `text`, empty or whitespace-only text, or more than 200,000 characters |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 Gemini calls a minute or 60 API calls a minute |
| 502 / 503 / 504 / 500 | see Error format above | Gemini failure |

## `GET /api/v1/contracts/labor-law/{host_country}`

Fetches a host country's curated labor-law rules from Firestore (`labor_laws/{country}`), each with the variant that applies to a given job type. Step 3 of Contract Shield (NF-P2-003). Plain Firestore read — **no Gemini call**, so only the API-wide rate limit applies. Send the `host_country` and `job_type` returned by `/contracts/detect`.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request:** path parameter `host_country` (`SG` / `KR` / `MY` / `JP` / `HK` / `AU`), query parameter `job_type` (one of the seven onboarding job types), required
- **Response `200`:** `LaborLawContext` (`app/schemas/contract.py`)

| Field | Type | Description |
|---|---|---|
| `country` | string | Same as the path parameter |
| `job_type` | string | Same as the query parameter |
| `law_version` | integer | `labor_laws/{country}/_meta/current.version`; record it on the eventual contract report (`docs/data-model/versioning.md`) |
| `rules` | array | All 15 curated categories, see below |

A rule has `category` (one of the 15 ids in [labor_laws](../data-model/collections/labor_laws.md)), `coverage` (`regulated` / `partly_regulated` / `not_regulated` / `unclear`), `title`, `summary`, `applicable_variant` (the variant matching `job_type`, falling back to the `all` variant), the full `variants` array (for any category a caller wants a different job type from), `references`, `confidence` and `notes`. A variant has `applies_to`, `requirements`, `limits`, `penalty` and `enforced_by`.

Example:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/contracts/labor-law/JP?job_type=domestic_worker"
```

```json
{
  "country": "JP",
  "job_type": "domestic_worker",
  "law_version": 1,
  "rules": [
    {
      "category": "working_hours",
      "coverage": "regulated",
      "title": "Working hours and breaks",
      "summary": "Workers may not be made to work more than 8 hours a day or 40 hours a week...",
      "applicable_variant": {
        "applies_to": ["all"],
        "requirements": ["No more than 40 hours per week and 8 hours per day..."],
        "limits": { "weekly_hours_limit": { "value": 40, "unit": "hours", "period": "week" } },
        "penalty": null,
        "enforced_by": "Labour standards inspection offices (Ministry of Health, Labour and Welfare)"
      },
      "variants": ["..."],
      "references": [{ "law": "Labor Standards Act (Act No. 49 of 1947)", "section": "Arts. 32, 34, 36(1)", "url": "https://www.japaneselawtranslation.go.jp/en/laws/view/3567/en" }],
      "confidence": "high",
      "notes": null
    }
  ]
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | `Missing bearer token` / `Invalid authentication token` / ... | No, invalid, expired or revoked token |
| 422 | FastAPI validation list | `host_country` outside `SG`/`KR`/`MY`/`JP`/`HK`/`AU`, or `job_type` missing/outside the seven job types |
| 404 | `No labor-law data is available yet for <country>.` | NF-P1-018 has not loaded that country yet |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `POST /api/v1/contracts/compare`

Checks every term of a contract against the host country's curated labor law and gives it a risk: `safe`, `caution` or `danger`. Step 4 of Contract Shield (NF-P2-004), reasoning tier (`gemini-3.5-flash`, prompt `contract/compare.v1`). Nothing is stored.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `blocks` | array (1 to 1000) | The `blocks` from `/contracts/extract`, unchanged. At most 200,000 characters of text |
| `host_country` | `SG` `KR` `MY` `JP` `HK` `AU` | From `/contracts/detect`, or asked from the worker |
| `job_type` | job type id | From `/contracts/detect`, or the worker's profile. Picks each rule's variant |
| `document_kind` | string, default `employment_contract` | From `/contracts/detect`. `loan_agreement` and `other` get 422 |

The labor law is fetched by the server (`labor_laws/{country}`), never taken from the request.

- **Time:** 20 to 38 s measured (6 to 25 terms, about 4k thinking tokens). Per attempt timeout 90 s (`GEMINI_COMPARE_TIMEOUT_SECONDS`), up to 3 attempts. The reasoning model is often 503 on the free tier; the client retries.
- **Response `200`:** `ContractComparison` (`app/schemas/contract_compare.py`)

| Field | Type | Description |
|---|---|---|
| `country`, `job_type` | string | As sent |
| `law_version` | integer | Labor-law version used (cache key, `docs/data-model/versioning.md`) |
| `health_score` | integer 0 to 100 | 100 is safest; see below |
| `risk_level` | `safe` / `caution` / `danger` | The worst risk of any term |
| `clause_counts` | `{safe, caution, danger}` | Terms per risk |
| `summary` | string | Two or three plain English sentences, worst problem first |
| `clauses` | array | The assessed terms in reading order, see below |
| `unassessed_block_ids` | array of integers | Clause, list item or table blocks the model did not assess; normally empty |

A clause has:
- `index` (1, 2, 3, ... in reading order)
- `number` and `page` (of its first block)
- `text` (the term's exact words, in the contract's language)
- `category` (one of the 15 labor-law categories, or `other`)
- `risk`
- `law_reference` (the curated rule's `"law, section"` for the variant that was applied; null when no rule regulates the matter)
- `explanation` and `recommendation` (plain English; the recommendation is null for safe terms)
- `block_ids` (1-based positions in the request's `blocks`)

Rules the server enforces, whatever the model says:
- Law references come from the curated data only, never from the model.
- A term can be `danger` only when a rule with coverage `regulated` or `partly_regulated` covers it. Otherwise it's reported as `caution`.

**Health score:** the worst risk sets the band. Any danger: 49 minus 10 per further danger and 2 per caution (at least 0). Caution only: 79 minus 3 per further caution (at least 50). Neither: 100.

Real output for `tests/fixtures/contracts/sample_contract_my_id.blocks.json` (Malaysia, plantation worker, Indonesian text), shortened:

```json
{
  "country": "MY", "job_type": "plantation_worker", "law_version": 1,
  "health_score": 19, "risk_level": "danger",
  "clause_counts": { "safe": 2, "caution": 0, "danger": 4 },
  "summary": "This contract contains multiple severe violations of Malaysian labor law. Most critically, it allows the employer to illegally withhold your passport, deducts unauthorized agency fees from your salary, ...",
  "clauses": [
    { "index": 3, "number": "3", "page": 1, "text": "3 Potongan gaji: RM 300 sebulan untuk
yuran agensi selama 12 bulan",
      "category": "recruitment_fees", "risk": "danger", "law_reference": "...",
      "explanation": "The contract deducts RM 300 a month for 12 months for agency fees. ...",
      "recommendation": "...", "block_ids": [6] }
  ],
  "unassessed_block_ids": []
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No labor-law data is available yet for XX.` | Country not curated yet |
| 422 | `The labor-law check covers employment contracts and recruitment agreements only.` | `document_kind` is `loan_agreement` or `other` |
| 422 | `No contract terms were found to check. Upload the full contract.` | The model found no term to assess |
| 422 | FastAPI validation list | No blocks, too many blocks or characters, unknown country or job type |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 AI calls a minute or 60 API calls a minute |
| 502 / 503 / 504 / 500 | see Error format above | Gemini failure (503 also when the free-tier quota is used up) |

---

## `POST /api/v1/contracts/translate`

Translates a finished report into the worker's language: `full_text`, `summary`, and each clause's `text`, `explanation` and `recommendation`. Step 5 of Contract Shield (NF-P2-005), classification tier (`gemini-3.1-flash-lite`, prompt `contract/translate.v1`). Nothing is stored.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `full_text` | string, 1 to 200,000 chars | The `text` from `/contracts/extract`, unchanged |
| `summary` | string, non-empty | The `summary` from `/contracts/compare` |
| `clauses` | array (1 to 200) | The `clauses` from `/contracts/compare`, unchanged; total clause text capped at 200,000 characters |
| `target_language` | `en` / `hi` / `tl` / `id` / `ne` / `bn` | The report language to translate into |

- **Time:** not yet measured live; classification tier is fast per call, but the output is a whole report (default timeout 60 s, `GEMINI_TRANSLATE_TIMEOUT_SECONDS`).
- **Response `200`:** `ContractReportTranslation` (`app/schemas/contract_translate.py`)

| Field | Type | Description |
|---|---|---|
| `language` | string | Same as `target_language` |
| `full_text` | string | Translated |
| `summary` | string | Translated |
| `clauses` | array | See below |

A clause has `index`, `number`, `page`, `category`, `risk`, `law_reference` and `block_ids` **unchanged from the request**, and `text`, `explanation`, `recommendation` **translated**. `category` and `risk` are never taken from Gemini's answer, even though the model sees them: they are the codes the UI keys its risk flags on.

Example (bash; in PowerShell use `curl.exe` and a here-string or a JSON file):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"full_text": "...", "summary": "The employer keeps the passport.", "target_language": "hi",
       "clauses": [{"index": 1, "number": "2", "page": 1, "text": "The employer keeps the passport.",
         "category": "passport_retention", "risk": "danger", "law_reference": "Passports Act, s. 47",
         "explanation": "The employer keeps your passport; the rule forbids it.",
         "recommendation": "Ask to keep your own passport.", "block_ids": [3]}]}' \
  http://127.0.0.1:8080/api/v1/contracts/translate
```

```json
{
  "language": "hi",
  "full_text": "...",
  "summary": "नियोक्ता पासपोर्ट रखता है।",
  "clauses": [
    {
      "index": 1, "number": "2", "page": 1,
      "text": "नियोक्ता कर्मचारी का पासपोर्ट रख सकता है।",
      "category": "passport_retention", "risk": "danger",
      "law_reference": "Passports Act, s. 47",
      "explanation": "नियोक्ता आपका पासपोर्ट रखता है; नियम इसे मना करता है।",
      "recommendation": "अपना पासपोर्ट खुद रखने के लिए कहें।",
      "block_ids": [3]
    }
  ]
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 422 | FastAPI validation list | Empty `full_text`/`summary`, no clauses, more than 200 clauses, over the character limit, or `target_language` outside the six supported codes |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 AI calls a minute or 60 API calls a minute |
| 502 | `The AI service returned an unusable answer. Please try again.` | Gemini left a clause out of its answer, or answered with something that did not match the schema |
| 503 / 504 / 500 | see Error format above | Gemini failure |

---

## `POST /api/v1/internal/refresh-rates` (internal)

Called only by the Cloud Scheduler job `refresh-rates` (every 2 hours). Hidden from the OpenAPI docs. Details: `docs/runbooks/NF-P1-019-fx-refresh-cron.md`.

- **Auth:** `Authorization: Bearer <Google-signed OIDC token>` for `CRON_SERVICE_ACCOUNT` with audience `CRON_AUDIENCE`. Firebase user tokens are rejected.
- **Request:** body ignored; send `{}` (Google's front end requires a body length on POST).
- **Response `200`:** `RefreshRatesResponse` (`app/schemas/remittance.py`): `history_point` (e.g. `2026-09-25T13`), `refreshed` (pair, rate, provider, rate_date), `failed` (pair, provider attempts), `completed_at`.
- **Errors:** 401 missing/invalid token, 403 other Google identity, 503 internal auth not configured **or** some pairs failed on every provider (body is the same `RefreshRatesResponse`; succeeded pairs are saved).

---

## `DELETE /api/v1/users/me`

Deletes the caller's account and everything stored about them (NF-P1-023). It cannot be undone.

- **Auth:** Firebase ID token (`get_current_user`). The account is always the token's own: there is no user id in the path or body, so nobody can name another user.
- **Fresh sign-in required:** the token's `auth_time` must be no more than `ACCOUNT_DELETION_MAX_LOGIN_AGE_SECONDS` old (default 300). Refreshing a token does not change `auth_time`; only signing in again does. The frontend asks the person to sign in again (Google popup, or an SMS code) and retries.
- **Request:** no body.
- **What it deletes, in this order** (`app/services/auth_service.py`):
  1. `users/{uid}` and every subcollection (Firestore `recursive_delete`).
  2. The user's files in Cloud Storage under `contracts/{uid}/`, `bills/{uid}/` and `exports/{uid}/`.
  3. The Firebase Auth user, last, so a person whose data step failed can still sign in and retry.
- **Kept on purpose:** `radar_reports` the user filed (they hold a salted hash, never the uid) and the `radar-evidence/` Storage folder.
- **Idempotent:** every step can run again, so calling it after a failure finishes the job.

| Status | When | `detail` |
|---|---|---|
| `204` | Everything was deleted | none (empty body) |
| `401` | Missing, invalid, expired or revoked token | see Authentication |
| `403` | The sign-in is older than the limit | `recent_login_required` (the frontend picks its "sign in again" screen by this exact string) |
| `503` | A backing service failed part-way | `We couldn't finish deleting the account. Please try again.` |
| `429` | Over 60 API calls a minute | `Too many requests. Please wait a minute and try again.` |

Production needs two roles for the backend's service account, or step 2 and 3 fail with `503`: `roles/firebaseauth.admin` and `roles/storage.objectUser` on the bucket (`infra/iam/grant-account-deletion-roles.sh`). A browser can call it from the allowed origins (CORS, NF-P1-027); the deployed site finds the backend through `VITE_API_BASE_URL`.

```bash
# local, with the emulators running and a token for the signed-in user
curl -s -X DELETE http://127.0.0.1:8080/api/v1/users/me -H "Authorization: Bearer $ID_TOKEN" -w "%{http_code}\n"
```
