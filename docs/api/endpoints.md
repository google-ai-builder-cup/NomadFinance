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
| POST | `/api/v1/contracts/extract` | Firebase ID token | Not yet (NF-P1-027) | NF-P1-006 |

## Error format

Every error response is JSON with a single human-readable `detail` string, for example `{"detail": "The file is larger than 10 MB."}`. The frontend should pick its translated message by **status code** and treat `detail` as a fallback. Errors never contain stack traces, model names or Gemini API messages.

Gemini failures (any endpoint that calls Gemini) map to (`app/core/errors.py`):

| Status | When | Retry? |
|---|---|---|
| 503 + `Retry-After: 30` | Gemini quota hit or Gemini unavailable, after 3 attempts | Yes, after the header's seconds |
| 504 | Gemini timed out on every attempt | Yes |
| 502 | Gemini answered with empty, blocked or invalid output | Yes, once |
| 500 | Our request was rejected by Gemini (a bug on our side) | No |

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

Transcribes an uploaded contract (PDF or phone photo) into text in its **original language**, using Gemini's extraction tier (`gemini-3.5-flash-lite` by default). First building block of Contract Shield. The file is held in memory for the request only; nothing is stored.

- **Auth:** `Authorization: Bearer <firebase-id-token>` required
- **Request:** `multipart/form-data` with one field `file`
  - Accepted: PDF, PNG, JPEG, WebP, HEIC/HEIF. The type is detected from the file's bytes; the filename and `Content-Type` are ignored.
  - Max size: 10 MB (`UPLOAD_MAX_BYTES`)
- **Response `200`:** `ContractExtractResponse` (`app/schemas/contract.py`)

| Field | Type | Description |
|---|---|---|
| `filename` | string or null | Name of the uploaded file, as sent by the client |
| `mime_type` | string | Type detected from the file bytes |
| `size_bytes` | integer | Size of the uploaded file |
| `page_count` | integer | Pages in the PDF; 1 for a photo |
| `text` | string | Full transcription, original language, one line per paragraph or list item, blank line between pages |

Example (bash; in PowerShell use `curl.exe`):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/contracts/sample_contract_sg.pdf" http://127.0.0.1:8080/api/v1/contracts/extract
```

```json
{
  "filename": "sample_contract_sg.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1881,
  "page_count": 2,
  "text": "STANDARD EMPLOYMENT CONTRACT - FOREIGN DOMESTIC WORKER\nRepublic of Singapore\n\nEmployer: Tan Wei Ming, ...\n2. Monthly salary: SGD 650, paid on the last day of each month.\n..."
}
```

- **Errors:**

| Status | `detail` | Cause |
|---|---|---|
| 400 | `The uploaded file is empty.` | Zero-byte file |
| 401 | `Missing bearer token` / `Invalid authentication token` / ... | No, invalid, expired or revoked token |
| 413 | `The file is larger than 10 MB.` | Over `UPLOAD_MAX_BYTES` |
| 415 | `Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).` | Any other file type, including Word files and renamed text files |
| 422 | `No readable document found. ...` | Gemini found no document text (selfie, landscape, blank page) |
| 422 | FastAPI validation list | No `file` field in the form |
| 502 / 503 / 504 / 500 | see Error format above | Gemini failure |
