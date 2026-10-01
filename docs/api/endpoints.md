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
| POST | `/api/v1/contracts/complaint` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-006 |
| POST | `/api/v1/contracts` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-007 |
| POST | `/api/v1/contracts/{contract_id}/analyze` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-007 |
| POST | `/api/v1/contracts/{contract_id}/reports/{language}` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-007 |
| POST | `/api/v1/remittance/compare` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P2-014 |
| GET | `/api/v1/remittance/trends` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P2-015 |
| POST | `/api/v1/remittance/recommend` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P2-016 |
| POST | `/api/v1/remittance/log` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P2-017 |
| GET | `/api/v1/remittance/savings` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P2-022 |
| POST | `/api/v1/radar/report` | Firebase ID token | 60/min API-wide + 10/min Gemini budget | NF-P3-001 |
| POST | `/api/v1/radar/report/{report_id}/evidence` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-004 |
| GET | `/api/v1/radar/entities/{slug}/reports` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-008 |
| POST | `/api/v1/fib/income` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-010 |
| POST | `/api/v1/fib/bill` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-010 |
| POST | `/api/v1/fib/savings` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-010 |
| POST | `/api/v1/fib/bill/scan` | Firebase ID token | 10/min per user (AI calls) | NF-P3-011 |
| POST | `/api/v1/fib/categorize` | Firebase ID token | 10/min per user (AI calls) | NF-P3-012 |
| POST | `/api/v1/fib/report/export` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-014 |
| GET | `/api/v1/fib/report/export` | Firebase ID token | 60/min API-wide (no Gemini call) | NF-P3-014 |
| POST | `/api/v1/internal/refresh-rates` | Cloud Scheduler OIDC token only (not in `/docs`) | Exempt (NF-P1-027) | NF-P1-019 |
| POST | `/api/v1/internal/aggregate-radar` | Cloud Scheduler OIDC token only (not in `/docs`) | Exempt (NF-P1-027) | NF-P3-004 |
| POST | `/api/v1/internal/recompute-fib-profiles` | Cloud Scheduler OIDC token only (not in `/docs`) | Exempt (NF-P1-027) | NF-P3-013 |
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

## `POST /api/v1/contracts/complaint`

Writes a formal complaint to the host country's labor authority for the clauses that break the law. Step 6 of Contract Shield (NF-P2-006), reasoning tier (`gemini-3.5-flash`, prompt `contract/complaint.v2`). Nothing is stored.

The letter is written twice: `letter_text` in the language the authority works in (English, Korean, Malay or Japanese), and `worker_copy` in the worker's own language so the worker can read what they are sending. `worker_copy` is `null` when both are the same language. The worker's name, contact details and start date are left as `[bracketed blanks]`, in the same places in both texts.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `host_country` | `SG` / `KR` / `MY` / `JP` / `HK` / `AU` | From `/contracts/detect`, or the worker's answer |
| `clauses` | array (1 to 200) | The `clauses` from `/contracts/compare`, unchanged. Only clauses with `risk` `danger` go in the letter; total clause text capped at 200,000 characters |
| `contract_facts` | object, optional | `employer_name`, `agency_name`, `salary_amount`, `salary_currency`, `salary_period` from `/contracts/detect`; every field may be `null` |
| `worker_language` | `en` / `hi` / `tl` / `id` / `ne` / `bn` | Language of the worker's own copy |

- **Time:** see the runbook `docs/runbooks/NF-P2-006-contract-complaint.md` (default timeout 60 s per attempt, `GEMINI_COMPLAINT_TIMEOUT_SECONDS`).
- **Response `200`:** `ContractComplaint` (`app/schemas/contract_complaint.py`)

| Field | Type | Description |
|---|---|---|
| `template_type` | string | `general` for every violation |
| `authority_name` | string | From the curated template, never from Gemini |
| `authority_url` | string or null | Official page of the authority |
| `channels` | array | Ways to reach it: `{kind: web/email/phone/post, value, note}` |
| `letter_language` | `en` / `ko` / `ms` / `ja` | Language of `letter_text` |
| `letter_text` | string | The letter to send |
| `worker_language` | string | Same as the request |
| `worker_copy` | string or null | The same letter in `worker_language` |
| `violation_count` | number | How many danger clauses the letter covers |

The authority, its channels and `template_type` come from `complaint_templates/{country}/types/general`, so a wrong phone number can only come from the curated file, never from a model answer. `authority_name`, `template_type` and `letter_text` are the `complaint` map of `reports/{lang}` (`docs/data-model/collections/contracts.md`).

Example (bash; in PowerShell use `curl.exe` and a here-string or a JSON file):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"host_country": "SG", "worker_language": "hi",
       "contract_facts": {"employer_name": "Acme Pte Ltd", "salary_amount": 650, "salary_currency": "SGD"},
       "clauses": [{"index": 1, "number": "2", "page": 1,
         "text": "The employer may keep the worker's passport.",
         "category": "passport_retention", "risk": "danger", "law_reference": "Passports Act, s. 47",
         "explanation": "The employer keeps your passport; the rule forbids it.",
         "recommendation": "Ask to keep your own passport.", "block_ids": [3]}]}' \
  http://127.0.0.1:8080/api/v1/contracts/complaint
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No complaint letter is available yet for <country>.` | The complaint templates are not loaded for this country |
| 422 | `No term of this contract was found to break the law, so there is nothing to report.` | No clause has `risk` `danger` |
| 422 | FastAPI validation list | No clauses, more than 200, over the character limit, or a country or language outside the supported codes |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 AI calls a minute or 60 API calls a minute |
| 502 | `The AI service returned an unusable answer. Please try again.` | Gemini's answer had no letter, no worker copy, or left a `{{marker}}` unfilled |
| 503 / 504 | see Error format | Gemini busy or timed out |

## Contract Shield as the app uses it (NF-P2-007)

The endpoints above run one step each and store nothing. These three run the whole pipeline and store every result under `users/{uid}/contracts/{contract_id}` (`docs/data-model/collections/contracts.md`). The app reads the contract and its reports straight from Firestore; the security rules already let the owner read them.

**How the app uses them:**

1. `POST /api/v1/contracts` with the file (multipart field `file`). The server reads it (step 1, 3 to 40 s) and returns `contract_id`. If `legibility` is `poor`, ask for a clearer photo instead of analysing.
2. Start listening to `users/{uid}/contracts/{contract_id}` in Firestore (`onSnapshot`). Its `status` and `step` show progress: `detect`, `law`, `compare`, `complaint`, `translate`.
3. `POST /api/v1/contracts/{contract_id}/analyze`, with the upload form's choices if any. Usually 30 s to 2 minutes. Keep the request open: all the work happens inside it (Cloud Run gives CPU only to open requests).
4. Show `reports/{language}` from Firestore. To switch language, `POST .../reports/{language}`.

### `POST /api/v1/contracts`

- **Request:** `multipart/form-data`, field `file`. The same checks as `/contracts/extract`: PDF, PNG, JPEG, WebP or HEIC, up to 10 MB, type from the bytes.
- **Response `201`:** `ContractUploadResponse`: `contract_id` (20 characters), `status` (`uploaded`), `reused`, `page_count`, `title`, `legibility`.
- The same file uploaded again by the same user returns the stored contract (`reused: true`) without calling Gemini. The file is **not stored**, only the blocks and text read from it (`extraction/current`, backend only).
- **Errors:** 400 empty file, 413 too large, 415 wrong type, 422 no readable document, 429, 502/503/504 (Gemini).

### `POST /api/v1/contracts/{contract_id}/analyze`

- **Request body (optional JSON):** the upload form's choices, each winning over the contract and the profile: `host_country`, `job_type`, `report_language`.
- **Choosing values when not given:**

  | Value | Order |
  |---|---|
  | Country | Worker's choice, then detected, then profile `host_country`. None at all: 422 `country_unknown` |
  | Job | Worker's choice, then detected (unless `other`), then profile `job_type` |
  | Report language | Worker's choice, then profile `preferred_language`, then `en` |

- **Response `200`:** `ContractAnalysis`:
  - `contract_id`, `status` (`completed`)
  - `cached`: the stored analysis was still current, so no Gemini call
  - `host_country`, `job_type`, `health_score`, `risk_level`, `clause_counts`
  - `report_language`, `report_languages` (alphabetically sorted — not source-language-first; e.g. `["bn", "en"]`, not `["en", "bn"]`)
  - `complaint_pending`: the letter failed for a passing reason; call analyze again to write only the letter
  - `complaint_pending_reason`: why, while `complaint_pending` is true, else `null`: `ai_daily_limit` (Gemini's daily quota is used up: comes back tomorrow), `ai_busy` (overloaded, per-minute limit or timeout: minutes), `ai_failed` (an unusable answer), `no_template` (the host country's template is not loaded in that Firestore)
- **Stored:**
  - the contract's `detected`, `extracted`, `host_country`, `job_type`, scores, `law_version`, `prompt_versions`, `models`
  - `reports/en`: the analysis in English, with the complaint letter when a term is danger
  - `reports/{report_language}` when that isn't English
- **Errors** (the code is also stored as the contract's `error`, with the step):

| Status | `detail` | `error.code` |
|---|---|---|
| 404 | `No such contract.` | (not stored) |
| 409 | `This contract is already being analysed. Please wait.` | (not stored) |
| 422 | `The contract is too hard to read. ...` | `poor_legibility` |
| 422 | `Choose the country where you work, then try again.` | `country_unknown` |
| 422 | `The labor-law check covers employment contracts and recruitment agreements only.` | `not_employment_contract` |
| 404 | `Labor-law data for this country is not available yet.` | `no_law_data` |
| 422 | `No contract terms were found to check. Upload the full contract.` | `no_terms` |
| 503 / 504 / 502 / 500 | see Error format above | `gemini_unavailable`, `gemini_busy`, `gemini_timeout`, `gemini_bad_answer`, `internal` |

A failed analysis can be run again with the same call. What was stored is reused: after a failed translation, only the translation runs again.

### `POST /api/v1/contracts/{contract_id}/reports/{language}`

- **Path:** `language` is one of `en`, `hi`, `tl`, `id`, `ne`, `bn`.
- **Response `200`:** `ContractReport`, the stored `reports/{language}` document without timestamps:
  - `language`, `is_source`, `full_text`, `summary`
  - `clauses` (with `number`, `page`, `block_ids`)
  - `complaint`
  - `content_hash`, `law_version`, `prompt_versions`, `models`
- A current stored report is returned at once; otherwise the English report is translated (a few seconds), stored and returned. This is the language switch of NF-P2-012.
- **How the app uses it (NF-P2-012):** the report language switcher reads a language listed in the analysis' `report_languages` straight from Firestore (`reports/{language}`) and calls this endpoint only for a language that is not stored yet. It sends no body, does not retry a failed call by itself (the backend already tries Gemini three times), and keeps each language it has seen, so switching back makes no request. A `409` means the analysis is not current: the app tells the worker to check the contract again. It does not use the position of a language in `report_languages`, which is sorted alphabetically (D-60).
- **Errors:** 404 no such contract, 409 not analysed yet (or stale: analyze again), 502 incomplete translation, 503/504.

---

## `POST /api/v1/remittance/compare`

Compares every surveyed way to send money along one corridor, for the amount the worker chooses: what each service costs, and how much the recipient receives, best first. Steps 1 to 6 of the Remittance X-Ray pipeline (NF-P2-014, `docs/pipelines/remittance-xray.md`). No Gemini call, so only the API-wide budget applies. Nothing is stored.

The prices are the World Bank's Remittance Prices Worldwide survey of early 2025, not a live price list. The mid-market exchange rate is the cron's latest (`rates_cache`). The response carries the survey period and the attribution text the World Bank requires wherever the prices are shown.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `corridor_id` | `SG-PH` / `SG-IN` / `AU-IN` / `MY-ID` / `JP-PH` / `AU-PH` | Sending country and receiving country |
| `amount` | number, greater than 0 | Amount to send, **in the corridor's sending currency** (SGD for `SG-PH`) |

- **Amount limits:** from a quarter of the smaller survey amount to ten times the larger one (about USD 50 to 5,000): `SG-PH` 65 to 6,450 SGD, `JP-PH` 4,250 to 420,000 JPY. Outside them the answer is a `422` that states the limits.
- **Response `200`:** `RemittanceComparison` (`app/schemas/remittance_compare.py`)

| Field | Type | Description |
|---|---|---|
| `corridor_id`, `send_amount`, `send_currency`, `receive_currency` | | The request, with the two currencies |
| `rate` | object | `pair`, `rate` (units received per 1 sent), `source` (`live` or `survey`), `provider`, `rate_date`, `fetched_at`, `stale` |
| `survey` | object | `period`, `surveyed_from`, `surveyed_to`, `source_name`, `source_url`, `attribution` |
| `providers` | array | Ranked services first, then the ones that cannot be compared |
| `summary` | object | `comparable_count`, `best_rpw_id`, `best_firm`, `best_recipient_receives`, `worst_rpw_id`, `worst_firm`, `worst_recipient_receives`, `extra_vs_worst`, `mid_market_receives`, `median_total_cost_pct` |

Each entry of `providers`:

| Field | Description |
|---|---|
| `rpw_id` | The service's id. A firm appears once per service (Wise on the web, at an agent, ...), so `firm` is not unique: use `rpw_id` as the key |
| `firm`, `firm_type`, `payment_instrument`, `access_point`, `pickup_method`, `network_coverage`, `note` | What the World Bank recorded |
| `speed`, `speed_order` | Delivery time, and 0 (fastest) to 5 to sort by |
| `rank` | 1 = the recipient receives most. `null` when `comparable` is false |
| `comparable` | False for services that pay out in another currency (USD): 6 of 221, in SG-PH, SG-IN and JP-PH. They are listed last and not ranked |
| `estimated` | True when the amount is outside the two survey amounts, so the fee and rate margin are the nearest survey point's |
| `fee`, `rate_cost`, `total_cost` | Flat fee, the rate markup as an amount, and their sum, in the sending currency |
| `fx_margin_pct`, `total_cost_pct` | The markup, and the total cost as a percentage of the amount sent |
| `recipient_receives` | In the receiving currency; `null` when not comparable |
| `lost_to_costs` | Mid-market amount minus `recipient_receives`. Negative for the few services the survey found cheaper than mid-market |
| `less_than_best` | What the best service gives the recipient over this one; 0 for rank 1 |
| `flagged`, `flag_report_count` | `true` (and the number of reports) when workers have reported the service on the Exploitation Radar (a flagged `money_transfer_operator` in `radar_entities`, matched by slug or alias). It keeps its rank; `/recommend` passes over it. `false` / `null` otherwise, and when Radar cannot be read |

`stale` on `rate` is true when the cached rate is older than 6 hours, or when there is none and the survey's own median rate was used (`source: "survey"`): the app should say the rate may be out of date. All amounts are rounded to two decimals (the rate to six).

Example: 500 SGD to the Philippines, with a live rate of 43.2 (abridged: 39 services in the real answer).

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"corridor_id": "SG-PH", "amount": 500}' \
  http://127.0.0.1:8080/api/v1/remittance/compare
```

```json
{
  "corridor_id": "SG-PH",
  "send_amount": 500.0,
  "send_currency": "SGD",
  "receive_currency": "PHP",
  "rate": {
    "pair": "SGD_PHP", "rate": 43.2, "source": "live", "provider": "frankfurter",
    "rate_date": "2026-09-28", "fetched_at": "2026-09-28T11:40:00Z", "stale": false
  },
  "survey": {
    "period": "2025_1Q", "surveyed_from": "2025-02-05", "surveyed_to": "2025-02-28",
    "source_name": "World Bank Remittance Prices Worldwide",
    "source_url": "http://remittanceprices.worldbank.org",
    "attribution": "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org"
  },
  "providers": [
    {
      "rpw_id": 521250759, "firm": "InstaReM", "firm_type": "Money Transfer Operator",
      "payment_instrument": "Bank account transfer", "access_point": "Internet",
      "pickup_method": "Bank account", "speed": "Same day", "speed_order": 1,
      "network_coverage": "Medium", "note": null, "payout_currency": "PHP",
      "comparable": true, "rank": 1, "estimated": false,
      "fee": 3.3, "fx_margin_pct": 0.07, "rate_cost": 0.35, "total_cost": 3.65,
      "total_cost_pct": 0.73, "recipient_receives": 21442.17, "lost_to_costs": 157.83,
      "less_than_best": 0.0
    }
  ],
  "summary": {
    "comparable_count": 38, "best_firm": "InstaReM", "best_recipient_receives": 21442.17,
    "worst_firm": "Maybank", "worst_recipient_receives": 18874.08, "extra_vs_worst": 2568.09,
    "mid_market_receives": 21600.0, "median_total_cost_pct": 1.74
  }
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No prices are available yet for <corridor>.` | The corridor is not loaded in Firestore (data-scripts loader, NF-P1-016), or none of its services can be compared |
| 422 | `Enter an amount between 65.00 and 6,450.00 SGD.` | The amount is outside the limits of that corridor |
| 422 | FastAPI validation list | Missing or unknown `corridor_id`, or an amount that is missing, not a number, zero, negative, `NaN` or infinite |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

## `GET /api/v1/remittance/trends`

A corridor's mid-market exchange rate over time, one value per market day, for the trend chart, plus the weekday that is usually best to send on. Steps 4 and 7 of the Remittance X-Ray pipeline (NF-P2-015, `docs/pipelines/remittance-xray.md`). One Firestore read (`rates_history/{pair}`, its `daily` map), no Gemini call. Nothing is stored.

The rates are the European Central Bank's reference rates (via Frankfurter): backfilled for past days (`data-scripts/src/loaders/frankfurter_backfill.py`) and kept up by the rate cron. The ECB publishes on working days only, so there are no weekend points. `providers` lists every source used in the period; show "Rates by Exchange Rate API" when it contains `exchangerate_api` (D-35).

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Query parameters:**

| Name | Type | Description |
|---|---|---|
| `corridor_id` | `SG-PH` / `SG-IN` / `AU-IN` / `MY-ID` / `JP-PH` / `AU-PH`, required | Sending country and receiving country |
| `days` | `30` / `90` / `180` / `365`, default `90` | Period of the `points` and the `summary` |

- **Response `200`:** `RemittanceTrends` (`app/schemas/remittance_trends.py`)

| Field | Type | Description |
|---|---|---|
| `corridor_id`, `pair`, `base_currency`, `quote_currency`, `days` | | The request, with the pair id (`AUD_INR`) and its currencies |
| `points` | array of `{date, rate}` | One per market day in the period, oldest first. `rate` = units received per 1 sent, so higher is better for the worker |
| `summary` | object or `null` | `first`, `latest`, `low`, `high` (each `{date, rate}`), `change_pct` (latest against first; above 0 = the recipient now gets more), `average`. `null` when the period has no points |
| `last_date` | date | The newest day stored, even if it is outside the period (a stalled cron shows here) |
| `best_day` | object or `null` | `weekday` (`monday` … `friday`), `advantage_pct`, `weeks`, `beat_share`: see below |
| `best_day_reason` | `not_enough_history` / `no_clear_pattern` / `null` | Why `best_day` is null |
| `weeks_analysed` | integer | Weeks with at least 3 market days in the last 52 weeks |
| `weekdays` | array | The same four fields for all five weekdays, Monday first; empty with `not_enough_history` |
| `providers` | array of string | Rate sources used in `points`, e.g. `["frankfurter"]` |

**How the best day is found.** Each market day of the last 52 weeks is compared with the average rate of its own week (Monday to Friday), so a rate that rises or falls over the year does not favour the days that come later in the week.
- `advantage_pct` is a weekday's average percentage above its week's average.
- `beat_share` is the share of weeks in which it was above that average.
- A weekday is named only when:
  - at least 8 weeks count, otherwise `not_enough_history`
  - it leads by at least 0.05 % and in more than half of the weeks, otherwise `no_clear_pattern`
- The period chosen with `days` does not change the best day.
- Days are market dates (the rate's own date), not the worker's local weekday.

On the ECB data of 2025-09 to 2026-09 this names Wednesday for AU-IN (0.085 %, 65 % of weeks) and Thursday for MY-ID. The other four corridors have no clear pattern. The app must say "no reliable best day" rather than invent one.

Example: AU-IN, last 30 days (real ECB data; `points` abridged).

```bash
curl -s -H "Authorization: Bearer $TOKEN"   "http://127.0.0.1:8080/api/v1/remittance/trends?corridor_id=AU-IN&days=30"
```

```json
{
  "corridor_id": "AU-IN", "pair": "AUD_INR", "base_currency": "AUD", "quote_currency": "INR",
  "days": 30,
  "points": [{"date": "2026-08-31", "rate": 68.161}, {"date": "2026-09-01", "rate": 67.807}],
  "summary": {
    "first": {"date": "2026-08-31", "rate": 68.161}, "latest": {"date": "2026-09-28", "rate": 67.418},
    "change_pct": -1.09, "low": {"date": "2026-09-25", "rate": 67.361},
    "high": {"date": "2026-09-09", "rate": 68.713}, "average": 68.095143
  },
  "last_date": "2026-09-28",
  "best_day": {"weekday": "wednesday", "advantage_pct": 0.085, "weeks": 52, "beat_share": 0.65},
  "best_day_reason": null,
  "weeks_analysed": 52,
  "weekdays": [
    {"weekday": "monday", "advantage_pct": -0.066, "weeks": 50, "beat_share": 0.48},
    {"weekday": "tuesday", "advantage_pct": -0.109, "weeks": 52, "beat_share": 0.35},
    {"weekday": "wednesday", "advantage_pct": 0.085, "weeks": 52, "beat_share": 0.65},
    {"weekday": "thursday", "advantage_pct": 0.044, "weeks": 50, "beat_share": 0.52},
    {"weekday": "friday", "advantage_pct": 0.048, "weeks": 49, "beat_share": 0.51}
  ],
  "providers": ["frankfurter"]
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No rate history is available yet for <corridor>.` | Nothing in `rates_history/{pair}.daily`: run the backfill, or wait for the cron |
| 422 | FastAPI validation list | Missing or unknown `corridor_id`, or `days` not one of 30, 90, 180, 365 |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `GET /api/v1/remittance/savings`

The "you would have saved $X" figure: what sending `amount` with the best comparable service, instead of the worst, would have been worth over real history. Step 8 of the Remittance X-Ray pipeline (NF-P2-022, `docs/pipelines/remittance-xray.md`). No Gemini call, so only the API-wide budget applies. Nothing is stored.

The best and worst service, and their total cost as a percentage of `amount`, are exactly what `/compare` would rank for the same `corridor_id` and `amount` — the survey's fees are one quarter, not a history, so the same two services are used for every month. Only the mid-market rate changes month to month, from `rates_history` (the same data `/trends` reads); each of the last `months` **full** calendar months is priced at that month's own average rate. Today's own, still-incomplete month is never included.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `corridor_id` | `SG-PH` / `SG-IN` / `AU-IN` / `MY-ID` / `JP-PH` / `AU-PH`, required | Sending country and receiving country |
| `amount` | number, required, > 0 | Amount to send, in the corridor's sending currency; same limits as `/compare` |
| `months` | integer, 1 to 12, default `12` | Full calendar months to look back over |

- **Response `200`:** `RemittanceSavings` (`app/schemas/remittance_savings.py`)

| Field | Type | Description |
|---|---|---|
| `corridor_id`, `send_amount`, `send_currency`, `receive_currency` | | The request, with the corridor's currencies |
| `months_requested` | integer | `months` from the query |
| `months_used` | integer | Full months that actually had rate history; less than `months_requested` when the history does not reach back that far |
| `best_rpw_id`, `best_firm` | | The comparable service that pays out the most, for `amount` |
| `worst_rpw_id`, `worst_firm` | | The comparable service that pays out the least |
| `total_best_receives`, `total_worst_receives` | number | Sum of `months[].best_receives` / `worst_receives` |
| `total_savings` | number | `total_best_receives` minus `total_worst_receives` — the headline figure |
| `months` | array | One entry per month used, oldest first: `month` (`YYYY-MM`), `average_rate`, `best_receives`, `worst_receives`, `savings` |
| `survey` | object | Same shape as `/compare`'s `survey`; show the attribution wherever `total_savings` is shown |

Example: SGD 500 on SG-PH, last 3 months (illustrative numbers).

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8080/api/v1/remittance/savings?corridor_id=SG-PH&amount=500&months=3"
```

```json
{
  "corridor_id": "SG-PH", "send_amount": 500.0, "send_currency": "SGD", "receive_currency": "PHP",
  "months_requested": 3, "months_used": 3,
  "best_rpw_id": 521250759, "best_firm": "InstaReM",
  "worst_rpw_id": 500123456, "worst_firm": "Maybank",
  "total_best_receives": 72823.0, "total_worst_receives": 70200.0, "total_savings": 2623.0,
  "months": [
    {"month": "2026-06", "average_rate": 43.1, "best_receives": 24200.0, "worst_receives": 23350.0, "savings": 850.0},
    {"month": "2026-07", "average_rate": 43.3, "best_receives": 24312.0, "worst_receives": 23420.0, "savings": 892.0},
    {"month": "2026-08", "average_rate": 43.6, "best_receives": 24311.0, "worst_receives": 23430.0, "savings": 881.0}
  ],
  "survey": {
    "period": "2025_1Q", "surveyed_from": "2025-02-05", "surveyed_to": "2025-02-28",
    "source_name": "World Bank Remittance Prices Worldwide",
    "source_url": "http://remittanceprices.worldbank.org",
    "attribution": "The World Bank, Remittance Prices Worldwide"
  }
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No prices are available yet for <corridor>.` | The corridor is not loaded, or nothing in it can be compared |
| 404 | `No rate history is available yet for <corridor>.` | No month within the requested period has any stored rate history |
| 422 | FastAPI validation list | Missing or unknown `corridor_id`, `months` outside 1 to 12, or an amount outside the range `/compare` can be stretched to |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `POST /api/v1/remittance/recommend`

Writes a short, personal recommendation from a finished comparison: one headline and two to four sentences, in the worker's own language. Step 9 of the Remittance X-Ray pipeline (NF-P2-016, `docs/pipelines/remittance-xray.md`), classification tier (`gemini-3.1-flash-lite`, prompt `remittance/recommend.v1`) — the only remittance step that calls Gemini, on a separate quota bucket from Contract Shield's reasoning tier (ADR-002, D-58). Nothing is stored.

**The recommended provider is never a name Gemini chose.** `recommended_rpw_id` and `recommended_firm` are the comparison's highest-ranked comparable provider that is not `flagged` (the top-ranked one when every provider is flagged), set by code (`recommender.recommended_provider`, prompt `recommend.v2`); the prompt's own answer is only checked against them, and a mismatch is a `502`.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `comparison` | object, required | The unmodified response of `POST /remittance/compare`, at least one ranked provider |
| `trend` | object or omitted | The unmodified response of `GET /remittance/trends`, for the timing tip. Omit it, or send it with `best_day: null`, when you have none |
| `target_language` | `en` / `hi` / `tl` / `id` / `ne` / `bn` | Language to write the recommendation in |

- **Response `200`:** `RemittanceRecommendation` (`app/schemas/remittance_recommend.py`)

| Field | Type | Description |
|---|---|---|
| `corridor_id` | | Same as `comparison.corridor_id` |
| `target_language` | | Same as the request |
| `recommended_rpw_id`, `recommended_firm` | | The highest-ranked comparable provider of `comparison` that is not flagged, set by code |
| `headline` | string | One short sentence with the key number |
| `explanation` | string | Two to four short sentences: the gap to the most expensive option, and the fee or rate markup that causes it, in plain words (never a field name like `fx_margin_pct`) |
| `timing_tip` | string or `null` | One sentence from `trend.best_day`; always `null` when `trend` had none, whatever Gemini wrote |

Example: the SGD 500 to PHP comparison above, with a Wednesday trend, in Hindi (real Gemini answer, 2026-09-30).

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"comparison": <the /compare response above>,
       "trend": {"best_day": {"weekday": "wednesday", "advantage_pct": 0.3, "weeks": 12, "beat_share": 0.75}, ...},
       "target_language": "hi"}' \
  http://127.0.0.1:8080/api/v1/remittance/recommend
```

```json
{
  "corridor_id": "SG-PH",
  "target_language": "hi",
  "recommended_rpw_id": 521250759,
  "recommended_firm": "InstaReM",
  "headline": "InstaReM के साथ पैसे भेजें: आपका परिवार 2907.3 PHP अधिक प्राप्त करेगा।",
  "explanation": "InstaReM चुनने पर आपके परिवार को Maybank की तुलना में 2907.3 PHP अधिक मिलेंगे। यह अंतर मुख्य रूप से Maybank द्वारा लिए जाने वाले उच्च शुल्क और खराब विनिमय दर के कारण है।",
  "timing_tip": "बुधवार को पैसे भेजने पर आपको 0.3 प्रतिशत का अधिक लाभ मिल सकता है।"
}
```

The headline reads "Send with InstaReM: your family will get 2907.3 PHP more."

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 422 | FastAPI validation list | `comparison` has no ranked provider, more than 60 providers, or `target_language` outside the six supported codes |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 AI calls a minute or 60 API calls a minute |
| 502 | `The AI service returned an unusable answer. Please try again.` | Gemini's answer had no headline or explanation, or named a provider other than the recommended one |
| 503 / 504 | see Error format | Gemini busy or timed out |

---

## `POST /api/v1/remittance/log`

Stores a transfer the worker actually sent, under `users/{uid}/transfers/{id}` — the entry that links Remittance X-Ray to Financial Identity (NF-P2-017, `docs/pipelines/remittance-xray.md`, `docs/data-model/collections/fib.md`). No Gemini call, so only the API-wide budget applies.

**Every stored amount is read from the comparison's own chosen provider, never typed freely by the client.** `comparison` is the unmodified response of `POST /remittance/compare`; `rpw_id` names which of its providers the worker actually used. `provider_name`, `send_amount`, `receive_amount`, `fee`, `cost_pct` and `mid_market_rate` are all copied from that provider's row and `comparison`'s own fields — the same reasoning `/remittance/recommend` uses to never trust a provider name Gemini wrote over the comparison's own top-ranked one (D-58-adjacent, not an ADR). A `rpw_id` that does not match a comparable, ranked provider (for example one that pays out in another currency, or was never on the ranked list) is a `422`, since there is no `recipient_receives` to log for it.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `comparison` | object, required | The unmodified response of `POST /remittance/compare`, at most 60 providers |
| `rpw_id` | integer, required | The service the worker actually used, from `comparison.providers[].rpw_id` |
| `entry_date` | `YYYY-MM-DD`, optional | The day the transfer was sent. Defaults to today (UTC) |
| `notes` | string, optional (≤500 chars) | Free text from the worker. Blank or whitespace-only is stored as `null` |

- **Response `201`:** `TransferLogResponse` (`app/schemas/remittance_log.py`)

| Field | Type | Description |
|---|---|---|
| `transfer_id` | string | Id of `users/{uid}/transfers/{transfer_id}` |
| `corridor_id`, `provider_rpw_id`, `provider_name` | | Copied from `comparison` and the chosen provider |
| `send_amount`, `send_currency` | | `comparison.send_amount` / `send_currency` |
| `receive_amount`, `receive_currency` | | The chosen provider's `recipient_receives` / `comparison.receive_currency` |
| `fee` | number | The chosen provider's fee, in `send_currency` |
| `mid_market_rate` | number | `comparison.rate.rate`, the live rate every provider was compared against |
| `cost_pct` | number | The chosen provider's `total_cost_pct` |
| `entry_date`, `notes` | | Same as the request |

Example:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"comparison": <the /compare response above>, "rpw_id": 521250759}' \
  http://127.0.0.1:8080/api/v1/remittance/log
```

```json
{
  "transfer_id": "aBc123XyZ0123456789A",
  "corridor_id": "SG-PH",
  "provider_rpw_id": 521250759,
  "provider_name": "InstaReM",
  "send_amount": 500.0,
  "send_currency": "SGD",
  "receive_amount": 24274.33,
  "receive_currency": "PHP",
  "fee": 3.3,
  "mid_market_rate": 43.2,
  "cost_pct": 0.73,
  "entry_date": "2026-09-30",
  "notes": null
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 422 | FastAPI validation list, or `rpw_id is not a comparable, ranked provider of the comparison sent.` | `comparison`/`rpw_id` missing, `comparison.providers` over 60 entries, or `rpw_id` not a comparable ranked provider of `comparison` |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `POST /api/v1/radar/report`

A worker reports a money transfer operator, recruitment agency or employer. Steps 2 to 7 of the Exploitation Radar pipeline (NF-P3-001 and NF-P3-002, `docs/mermaid/exploitation-radar-pipeline.mmd`): extract who and where it's about (extraction tier, prompt `radar/extract_entity.v1`), screen for spam/abuse/personal data and classify the violation (classification tier, prompts `radar/validate.v1` and `radar/categorize.v1`), then store `radar_reports/{id}`. Steps 5 to 6 embed the description (`gemini-embedding-001`, 768 numbers) and search `report_embeddings` for a near-duplicate report on the same business and corridor; a match joins that report's cluster, otherwise the report starts its own. If embedding or the search fails, the report is still stored as its own cluster. Steps 8 to 9 (`radar_entities` aggregation, community rating) are NF-P3-003.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required, plus a Firebase App Check token (`X-Firebase-AppCheck` header) when `APP_CHECK_ENABLED=true` (NF-P3-025; off by default — see that task's runbook for when it turns on). The two are checked separately: a missing or invalid App Check token is a 403, distinct from a 401 on the Firebase Auth token.
- **Request body (JSON):**

| Field | Type | Description |
|---|---|---|
| `entity_type` | `money_transfer_operator` / `recruitment_agency` / `employer`, optional | From the submission form (NF-P3-006), if it collected one |
| `entity_name` | string, optional (≤200 chars) | As the worker wrote it |
| `corridor_id` | `SG-PH` / `SG-IN` / `AU-IN` / `MY-ID` / `JP-PH` / `AU-PH`, optional | For an operator or agency |
| `host_country` | `SG` / `KR` / `MY` / `JP` / `HK` / `AU`, optional | For an employer |
| `description` | string, required (10 to 2,000 chars) | What happened, in the worker's own words |
| `language` | `en` / `hi` / `tl` / `id` / `ne` / `bn`, required | Language of `description` |

All four identifying fields are optional: whatever is left blank, step 2 fills in from `description` itself. A value sent here wins over what step 2 extracts on its own. **`violation_type` is not accepted here** — it is always classified fresh from the text (step 4), never a worker's own pick.

- **Response `201`:** `RadarReportResponse` (`app/schemas/radar_report.py`)

| Field | Type | Description |
|---|---|---|
| `report_id` | string | Id of `radar_reports/{report_id}` — also its `cluster_id` when it starts a new cluster; a near-duplicate joins an earlier report's cluster, so the two ids can differ |
| `entity_type`, `entity_name` | | The entity actually reported (form value, or step 2's) |
| `violation_type` | string | Step 4's classification — one of the 9 violation types |
| `corridor_id`, `host_country` | | The entity actually reported (form value, or step 2's); at least one is set |
| `description` | string | As sent |
| `summary` | string | One neutral English sentence from step 4, for the worker's own confirmation screen. Also stored on the report (`radar_reports.summary`, NF-P3-004). The alert cron generates its own separate, alert-level summary from facts aggregated across multiple reports — it never reuses this one |
| `created_at` | timestamp | |

Example (illustrative — not a real Gemini call):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type": "money_transfer_operator", "entity_name": "Example Remit",
       "corridor_id": "SG-IN",
       "description": "They showed one rate and gave me a worse one at the counter.",
       "language": "en"}' \
  http://127.0.0.1:8080/api/v1/radar/report
```

```json
{
  "report_id": "r_01",
  "entity_type": "money_transfer_operator",
  "entity_name": "Example Remit",
  "violation_type": "hidden_fees",
  "corridor_id": "SG-IN",
  "host_country": null,
  "description": "They showed one rate and gave me a worse one at the counter.",
  "summary": "Operator showed one rate and charged a worse one at the counter.",
  "created_at": "2026-09-30T05:41:00Z"
}
```

**Anonymity.** `reporter_hash` (HMAC-SHA-256 of the uid, `RADAR_REPORTER_HASH_SECRET`) is stored, never returned to any client and never the uid itself; see "Kept on purpose" under `DELETE /api/v1/users/me` below.

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid Firebase Auth token |
| 403 | `Missing App Check token` / `Invalid App Check token` | Only when `APP_CHECK_ENABLED=true` (NF-P3-025) |
| 422 | FastAPI validation list | Missing/too-short/too-long `description`, missing or unsupported `language`, or an unknown `corridor_id`/`host_country`/`entity_type` |
| 422 | `Could not tell who this report is about. Add a business name.` | Neither the form nor step 2 named a business |
| 422 | `Could not tell where this happened. Add a corridor or the country you work in.` | Neither the form nor step 2 gave a corridor or host country |
| 422 | `This doesn't look like a real report. Please describe what happened.` | Step 3's spam score was at or above the threshold. Not stored |
| 422 | `This report cannot be published as written. Remove any threats or abusive language.` | Step 3 found threats, hate speech or sexual content. Not stored |
| 422 | `Please remove personal details (names, phone numbers, addresses) and try again.` | Step 3 found personal data in the free text. Not stored |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 10 AI calls a minute or 60 API calls a minute |
| 502 / 503 / 504 / 500 | see Error format above | Gemini failure |

## `POST /api/v1/radar/report/{report_id}/evidence`

Attaches a photo or screenshot to a report the caller filed themselves. A separate call from `POST /radar/report`, not a field on it (NF-P3-004): `radar-evidence/{report_id}/` needs a real report id first, and a worker may want to attach evidence after the fact without resubmitting the whole report. No Gemini call — only the API-wide rate limit applies.

**Ownership, without a stored uid-to-report mapping.** The caller's uid is re-hashed (`RADAR_REPORTER_HASH_SECRET`, the same HMAC `POST /radar/report` uses for `reporter_hash`) and compared to the report's own stored `reporter_hash`. A `contract_signal` or `seed` report has no `reporter_hash` at all — nobody can attach evidence to one, and the endpoint answers `404` rather than `403` so it doesn't confirm whether the id exists.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Path:** `report_id` — the id from `POST /radar/report`'s own response
- **Request:** `multipart/form-data`, field `file`. Same checks as `/contracts/extract`: PDF, PNG, JPEG, WebP or HEIC, up to 10 MB (`UPLOAD_MAX_BYTES`), type read from the bytes, never the client's filename or `Content-Type` header
- **Response `201`:** `RadarEvidenceResponse` (`app/schemas/radar_report.py`): `report_id`, `evidence_paths` (every attachment on the report so far, including this one)
- **Storage:** `radar-evidence/{report_id}/{a fresh id}.{ext}` — never the client's own filename. `storage.rules` denies all browser access to this folder; only the backend ever reads or writes it
- **Limit:** at most 5 attachments per report (not calibrated to anything, just a round number)

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 400 | `The uploaded file is empty.` | Zero-byte file |
| 401 | see Authentication | No, invalid, expired or revoked token |
| 403 | `This report wasn't filed by you.` | The caller's uid doesn't hash to the report's `reporter_hash` |
| 404 | `No such report.` | No report with this id, or it has no `reporter_hash` to check ownership against (`contract_signal`/`seed`) |
| 413 | `The request is larger than 10 MB.` / `The file is larger than 10 MB.` | Whole request over the limit (refused before reading) / file part over `UPLOAD_MAX_BYTES` |
| 415 | `Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).` | Any other file type |
| 422 | `Already has the maximum of 5 attachments.` | The report is already at the cap |
| 422 | FastAPI validation list | No `file` field, or `report_id` doesn't look like a Firestore auto id |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

## `GET /api/v1/radar/entities/{slug}/reports`

The individual reports behind one `radar_entities/{slug}` profile, newest first (NF-P3-008's entity profile page). The profile itself (name, `report_count`, `community_rating`, `risk_level`, `flagged`) is client-readable straight from Firestore (`firestore.rules`) and holds no personal data; `radar_reports` isn't, so this is how the profile page gets its report list. No Gemini call, so only the API-wide rate limit applies.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Path:** `slug` — a `radar_entities` document id (lowercase words joined by hyphens, e.g. `example-remit`)
- **Response `200`:** `list[RadarReportSummary]` (`app/schemas/radar_report.py`)

| Field | Type | Description |
|---|---|---|
| `report_id` | string | Id of `radar_reports/{report_id}` |
| `violation_type` | string | One of the 9 violation types |
| `description` | string | The reporter's own words (`contract_signal` reports: built from the flagged clauses' explanations) |
| `summary` | string or null | One neutral English sentence (NF-P3-001's classification step). Null for `contract_signal`/`seed`, which have no free text to summarize |
| `language` | string | Language of `description` |
| `corridor_id`, `host_country` | | At least one is set |
| `source` | `user` / `contract_signal` / `seed` | Where the report came from |
| `created_at` | timestamp | |

Never included: `reporter_hash`, `entity_slug`/`entity_type`/`entity_name` (redundant — every report in the list is about the same entity), or `validation` (spam score, category confidence, model — backend-only).

**An unknown slug and an entity with no reports both answer `200` with an empty list** — indistinguishable from a query over `radar_reports` alone, and there is nothing sensitive in the distinction. No 404.

Example:

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/v1/radar/entities/example-remit/reports
```

```json
[
  {
    "report_id": "aBc123XyZ0123456789A",
    "violation_type": "hidden_fees",
    "description": "They showed one rate and gave me a worse one at the counter.",
    "summary": "Operator showed one rate and charged a worse one at the counter.",
    "language": "en",
    "corridor_id": "SG-IN",
    "host_country": null,
    "source": "user",
    "created_at": "2026-09-27T05:41:00Z"
  }
]
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 422 | FastAPI validation list | `slug` isn't lowercase-words-and-hyphens shaped |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `POST /api/v1/fib/income`, `POST /api/v1/fib/bill`, `POST /api/v1/fib/savings`

Manual Financial Identity Builder activity logging (NF-P3-010): `users/{uid}/income`, `users/{uid}/bills`, `users/{uid}/savings` — the same pattern `POST /remittance/log` (NF-P2-017) already established for `users/{uid}/transfers`, the fourth entry type in the same activity log (`docs/data-model/collections/fib.md`). No Gemini call, so only the API-wide rate limit applies. A bill photo read by Gemini Vision is a separate endpoint, `POST /api/v1/fib/bill/scan` (NF-P3-011, below), writing into the same `bills` collection.

Every entry's `category` (income, bills) is always `category_source: "user"` here, whatever the worker chose or left blank — Flash-Lite categorization of uncategorized entries is its own step, `POST /api/v1/fib/categorize` (NF-P3-012, below).

- **Auth:** `Authorization: Bearer <firebase-id-token>` required for all three

**`POST /api/v1/fib/income`** — body: `entry_date` (optional, defaults to today), `amount` (> 0), `currency` (ISO 4217), `category` (required: `salary` / `overtime` / `bonus` / `other_income`), `employer_name` (optional), `notes` (optional, ≤500 chars). Response `201`: `IncomeLogResponse` (`app/schemas/fib.py`) — `entry_id`, the fields above, plus `category_source` (always `"user"`) and `verified` (always `false`: `true` is set only by the contract cross-pillar flow, NF-P3-024, never a manual entry).

**`POST /api/v1/fib/bill`** — body: `entry_date` (optional), `amount` (> 0), `currency`, `vendor` (optional), `bill_date` (optional — the date printed on the bill, separate from `entry_date`), `paid` (required), `category` (optional: `rent` / `utilities` / `phone_internet` / `transport` / `food` / `medical` / `other_expense`), `notes` (optional). Response `201`: `BillLogResponse` — `category_source` is `"user"` when a category was sent, `null` when it was left for NF-P3-012 to fill in later.

**`POST /api/v1/fib/savings`** — body: `entry_date` (optional), `amount` (> 0, always positive — `direction` carries the sign), `currency`, `direction` (required: `deposit` / `withdrawal`), `account_type` (optional: `cash` / `bank` / `mobile_wallet` / `other`), `notes` (optional). Response `201`: `SavingsLogResponse`.

Example (bill, with a category; bash — in PowerShell use `curl.exe`):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"amount": 38.5, "currency": "SGD", "paid": true, "vendor": "Example Telecom", "category": "phone_internet"}' \
  http://127.0.0.1:8080/api/v1/fib/bill
```

```json
{
  "entry_id": "aBc123XyZ0123456789A",
  "entry_date": "2026-09-30",
  "amount": 38.5,
  "currency": "SGD",
  "vendor": "Example Telecom",
  "bill_date": null,
  "paid": true,
  "category": "phone_internet",
  "category_source": "user",
  "notes": null,
  "created_at": "2026-09-30T12:00:00Z"
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 422 | FastAPI validation list | Missing a required field (`category` for income, `paid` for a bill, `direction` for savings), a non-positive `amount`, or `currency` not 3 uppercase letters |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

---

## `POST /api/v1/fib/bill/scan`

Reads a photo or PDF of a bill with Gemini Vision (extraction tier) and stores it as `users/{uid}/bills/{id}` with `source: "bill_ocr"` (NF-P3-011). Step 2a of the Financial Identity pipeline. Manual entry stays `POST /fib/bill`.

- **Auth:** `Authorization: Bearer <firebase-id-token>`
- **Request:** `multipart/form-data`, one field `file` (PDF, PNG, JPEG, WebP or HEIC/HEIF, up to 10 MB). The type is detected from the content, not the filename.
- **Response `201`:** `BillScanResponse` (`app/schemas/fib.py`): everything `POST /fib/bill` returns, plus `image_path` (Cloud Storage path of the photo, `null` if the upload failed), `confidence` (0 to 1, for amount and currency together) and `paid_assumed` (`true` when the bill did not say whether it was paid, so `paid` is `false` by default).
- **What is stored:** `amount`, `currency`, `vendor`, `bill_date`, `paid`, `image_path`, `extraction` (`confidence`, `model`, `prompt_version`), and the suggested `category` with `category_source: "model"`. `category_confidence` is not set here: Gemini's one confidence is for amount and currency, so Flash-Lite (NF-P3-012) sets it when it categorizes. `entry_date` is the bill's date when it shows as paid, otherwise today.
- **Nothing is stored** unless the file is a bill with a readable amount and a 3-letter currency. A date Gemini misreads is dropped, not stored.

| Status | `detail` | Cause |
|---|---|---|
| 400 | `The uploaded file is empty.` | Zero bytes |
| 401 | see Authentication | No or invalid token |
| 413 | `The file is larger than 10 MB.` | Over `UPLOAD_MAX_BYTES` |
| 415 | `Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).` | Content is not one of those types |
| 422 | `No bill found. Upload a clear photo or PDF of the bill or receipt.` | Not a bill, invoice or receipt |
| 422 | `The amount or currency could not be read. ...` | A bill, but amount or currency unreadable |
| 422 | FastAPI validation list | No `file` field |
| 429 | see Rate limits | Over 10 AI calls a minute |
| 502 / 503 / 504 | Gemini error text | Unusable answer / busy or out of quota / timed out |

Example (bash; in PowerShell use `curl.exe`):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@bill.jpg" http://127.0.0.1:8080/api/v1/fib/bill/scan
```

```json
{
  "entry_id": "aBc123XyZ0123456789A",
  "entry_date": "2026-09-20",
  "amount": 38.5,
  "currency": "SGD",
  "vendor": "Example Telecom",
  "bill_date": "2026-09-20",
  "paid": true,
  "category": "phone_internet",
  "category_source": "model",
  "notes": null,
  "created_at": "2026-10-01T09:30:00Z",
  "image_path": "bills/uid_priya_demo/aBc123XyZ0123456789A/bill.jpg",
  "confidence": 0.94,
  "paid_assumed": false
}
```

---

## `POST /api/v1/fib/categorize`

Gives a category and a confidence to the caller's income and bill entries that have no trusted one, with Gemini Flash-Lite (classification tier, prompt `fib/categorize.v1`) (NF-P3-012). Step 3 of the Financial Identity pipeline. Call it after logging entries; the weekly recompute (NF-P3-013) can use the same service before it computes metrics.

- **Auth:** `Authorization: Bearer <firebase-id-token>`
- **Request:** no body.
- **Pending entries** are in `users/{uid}/income` and `users/{uid}/bills` with no `category`, or with `category_source: "model"` and no `category_confidence` (a bill photo's suggestion from `POST /fib/bill/scan`, categorized again here). A category the worker chose (`category_source: "user"`) is never changed.
- **Writes** on each categorized entry: `category`, `category_source: "model"`, `category_confidence` (0 to 1, stored as Gemini returned it; no threshold is applied here).
- **Limits:** 25 entries per Gemini call, at most 100 entries (4 calls) per request, oldest `entry_date` first. Calling again continues. With nothing pending there is no Gemini call.
- **Response `200`:** `FibCategorizeResponse` (`app/schemas/fib.py`): `categorized` (a list of `entry_id`, `entry_type` `income` or `bill`, `category`, `confidence`), `skipped` (entries Gemini gave no usable answer for, such as a category that does not fit the type: they stay pending), `remaining` (pending entries left over by the 100 limit).

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 429 | see Rate limits | Over 10 AI calls a minute |
| 502 / 503 / 504 | Gemini error text | Unusable answer / busy or out of quota / timed out. Batches already done stay written; call again to continue. |

Example (bash; in PowerShell use `curl.exe`):

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/v1/fib/categorize
```

```json
{
  "categorized": [
    { "entry_id": "aBc123XyZ0123456789A", "entry_type": "bill", "category": "phone_internet", "confidence": 0.97 }
  ],
  "skipped": 0,
  "remaining": 0
}
```

---

## `POST /api/v1/fib/report/export`, `GET /api/v1/fib/report/export`

The portable Financial Identity report as a PDF (NF-P3-014), made with weasyprint from the worker's current `users/{uid}/financial_profile/current`. It does not recompute the profile (that is the weekly job, NF-P3-013); the PDF prints the date the profile was computed. No Gemini call, so only the API-wide rate limit applies.

- **Auth:** `Authorization: Bearer <firebase-id-token>`
- **`POST`** — body (optional): `holder_name` (up to 100 characters; blank is ignored). It is printed on the PDF only and never stored. Renders the PDF, stores it at `exports/{uid}/financial-identity-{timestamp}.pdf`, sets `latest_export` on the profile, deletes the previous export (a worker has at most one PDF), and returns `201`.
- **`GET`** — a fresh signed link to the latest export without rendering it again (links are made on request and never stored). `200`, same response shape.
- **Response:** `ExportReportResponse` (`app/schemas/fib_export.py`): `download_url` (a V4 signed link; anyone who has it can download the PDF), `expires_at`, `created_at` (when the PDF was made), `language`, `filename`. The link lasts `EXPORT_URL_EXPIRY_MINUTES` (default 1440, 24 hours) and downloads the file as `financial-identity-report.pdf`.
- **Content:** title, period, months of records, reporting currency, dates; entry counts; the four metric scores as bars (`Not enough records` for a metric with no score); the narrative; verified employment (employer and salary) when the profile has it; a disclaimer. The overall score is left out on purpose (it is an average of this project's own formulas and could be read as a credit score). No uid, email or phone.
- **Language:** the profile narrative's (`en`, `hi`, `tl`, `id`, `ne`, `bn`); the headings and disclaimer come from `app/services/fib/report_labels.py`.

| Status | `detail` | Cause |
|---|---|---|
| 401 | see Authentication | No or invalid token |
| 404 | `No Financial Identity profile yet. It is computed weekly from your logged activity.` | `POST` before the first weekly recompute |
| 404 | `No report has been exported yet.` | `GET` before any export |
| 422 | FastAPI validation list | `holder_name` longer than 100 characters |
| 429 | `Too many requests. Please wait a minute and try again.` | Over 60 API calls a minute |

Example (bash; in PowerShell use `curl.exe`):

```bash
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"holder_name": "Priya Sharma"}' http://127.0.0.1:8080/api/v1/fib/report/export
```

```json
{
  "download_url": "https://storage.googleapis.com/nomadfinance-prod.firebasestorage.app/exports/uid_priya_demo/financial-identity-20261002T093015Z.pdf?X-Goog-Algorithm=...",
  "expires_at": "2026-10-03T09:30:15Z",
  "created_at": "2026-10-02T09:30:15Z",
  "language": "hi",
  "filename": "financial-identity-report.pdf"
}
```

---

## `POST /api/v1/internal/refresh-rates` (internal)

Called only by the Cloud Scheduler job `refresh-rates` (every 2 hours). Hidden from the OpenAPI docs. Details: `docs/runbooks/NF-P1-019-fx-refresh-cron.md`.

- **Auth:** `Authorization: Bearer <Google-signed OIDC token>` for `CRON_SERVICE_ACCOUNT` with audience `CRON_AUDIENCE`. Firebase user tokens are rejected.
- **Request:** body ignored; send `{}` (Google's front end requires a body length on POST).
- **Response `200`:** `RefreshRatesResponse` (`app/schemas/remittance.py`): `history_point` (e.g. `2026-09-25T13`), `refreshed` (pair, rate, provider, rate_date), `failed` (pair, provider attempts), `completed_at`.
- **Errors:** 401 missing/invalid token, 403 other Google identity, 503 internal auth not configured **or** some pairs failed on every provider (body is the same `RefreshRatesResponse`; succeeded pairs are saved).

## `POST /api/v1/internal/aggregate-radar` (internal)

Called only by the Cloud Scheduler job `radar-aggregation` (every 6 hours). Hidden from the OpenAPI docs. The AGG subgraph of the Exploitation Radar pipeline (NF-P3-004, `docs/mermaid/exploitation-radar-pipeline.mmd`): for each of the 6 corridors, detects a surge (a business reported noticeably more than its own 7-day baseline), writes `radar_alerts/{corridor}/current/{alertId}`, expires alerts past `expires_at`, and for each freshly created alert writes a `users/{uid}/notifications/{id}` in every subscribed worker's own language plus an FCM push. Details: `docs/runbooks/NF-P3-004-radar-alert-cron.md`.

- **Auth:** `Authorization: Bearer <Google-signed OIDC token>` for `CRON_SERVICE_ACCOUNT` with audience `CRON_AUDIENCE`, the same as `/internal/refresh-rates`. Firebase user tokens are rejected.
- **Request:** body ignored; send `{}` (Google's front end requires a body length on POST).
- **Response `200`:** `AggregateRadarResponse` (`app/schemas/radar_alert.py`): `corridors_scanned` (always 6), `alerts_created`, `alerts_expired`, `notifications_sent`, `completed_at`.
- **Always 200.** A failure on one corridor (for example a missing Firestore index) or one recipient (a Gemini failure for one language, a dead FCM token) is caught and logged inside the run itself, never left to make Cloud Scheduler retry the whole thing.
- **Errors:** 401 missing/invalid token, 403 other Google identity, 503 internal auth not configured.

---

## `POST /api/v1/internal/recompute-fib-profiles` (internal)

Called only by the Cloud Scheduler job `fib-recompute` (Sundays 02:00 UTC). Hidden from the OpenAPI docs. The weekly recompute of the Financial Identity pipeline (NF-P3-013, `docs/mermaid/financial-identity-pipeline.mmd`): for each user with income, transfer, bill or savings entries in the last 12 months it computes the four metrics, has the reasoning tier write the report text in the worker's `preferred_language` (prompt `fib/synthesize_narrative.v1`), and overwrites `users/{uid}/financial_profile/current`. Details and formulas: `docs/runbooks/NF-P3-013-fib-weekly-recompute.md`.

- **Auth:** `Authorization: Bearer <Google-signed OIDC token>` for `CRON_SERVICE_ACCOUNT` with audience `CRON_AUDIENCE`, the same as `/internal/refresh-rates`. Firebase user tokens are rejected.
- **Request:** body ignored; send `{}` (Google's front end requires a body length on POST).
- **Response `200`:** `RecomputeResponse` (`app/schemas/fib_profile.py`): `users_seen`, `recomputed` (profiles written), `skipped_no_data` (no activity in the period, or none a metric could use; nothing written), `failed` (the previous profile was kept), `completed_at`.
- **Always 200.** A failure for one user (the narrative call timing out, a Firestore error, an entry that does not match its schema) is caught and logged inside the run with a hashed user id. That user keeps last week's profile and the others still run; a retry would run, and pay for, every other user again.
- **Run time:** one reasoning-tier call per user, 3 users at a time. Measured 15 to 24 s per call (2026-10-01), so about 100 users fit in Cloud Run's 900 s request timeout.
- **Errors:** 401 missing/invalid token, 403 other Google identity, 503 internal auth not configured.

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
