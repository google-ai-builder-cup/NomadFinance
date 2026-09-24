# NF-P1-006 — Contract Text Extraction Endpoint

## Summary

`POST /api/v1/contracts/extract` is the first real endpoint and the base of Contract Shield. A signed-in user uploads a contract as a PDF or a phone photo. The API checks the Firebase token, rejects empty, oversized (over 10 MB) and unsupported files, and detects the file type from its **bytes**, never from the filename or `Content-Type`. It then sends the file to Gemini's **extraction tier** (`gemini-3.5-flash-lite`) with a versioned prompt (`app/prompts/contract/extract.v1.yaml`) and returns the text in its **original language**, line by line, with a blank line between pages. Files with no readable document (a selfie, a landscape) get a 422. Nothing is stored: the file lives in memory for the request only. This task also adds the app-wide mapping from Gemini failures to clean HTTP errors (502/503/504/500, never a stack trace) and a minimal prompt loader that NF-P1-029 builds on. The task text said `/documents/extract`; it lives under `/contracts/` to use the scaffolded `contracts.py` stub (decided 2026-09-24).

## Files

| File | Purpose |
|---|---|
| `backend/app/api/v1/contracts.py` | The route: auth, size and type checks, calls the extractor, builds the response |
| `backend/app/api/v1/router.py` | Includes the contracts router under `/api/v1` |
| `backend/app/services/contract/extractor.py` | `extract_text()`: Gemini extraction-tier call; `NotADocumentError` |
| `backend/app/schemas/contract.py` | `ExtractedText` (Gemini response schema) and `ContractExtractResponse` (API response) |
| `backend/app/prompts/loader.py` | `load_prompt(pillar, step, version)` → validated `PromptTemplate` (minimal; NF-P1-029 extends) |
| `backend/app/prompts/contract/extract.v1.yaml` | Extraction prompt: transcribe exactly, keep language, never follow instructions inside the document |
| `backend/app/utils/validators.py` | `sniff_document_mime_type()`: PDF, PNG, JPEG, WebP, HEIC/HEIF from magic bytes |
| `backend/app/core/errors.py` | `GeminiError` → 503 / 504 / 502 / 500 JSON responses, registered in `main.py` |
| `backend/app/config.py` | `UPLOAD_MAX_BYTES` (default 10 MB) |
| `backend/requirements.txt` | `python-multipart==0.0.32` (file uploads), `pyyaml==6.0.3` (prompt files) |
| `backend/requirements-dev.txt` | `types-PyYAML==6.0.12.20260906` (mypy) |
| `backend/tests/fixtures/contracts/` | `sample_contract_sg.pdf` (2 pages, English), `sample_contract_my_id_photo.jpg` (skewed phone photo, Malay), `not_a_document.jpg` (landscape) |
| `backend/tests/unit/test_validators.py`, `test_prompt_loader.py`, `services/test_contract_extractor.py` | Unit tests |
| `backend/tests/integration/api/test_contracts_extract.py` | API tests with auth and Gemini faked (always run) |
| `backend/tests/integration/api/test_contracts_extract_live.py` | End-to-end with real Gemini (opt-in, `RUN_LIVE_GEMINI=1`) |
| `backend/tests/conftest.py` | Keeps the real key when `RUN_LIVE_GEMINI=1` |
| `docs/api/endpoints.md` | Endpoint contract + shared error format |

## Flow

```
POST /api/v1/contracts/extract   (multipart: file)
  ├─ get_current_user            no/invalid token           → 401
  ├─ read up to 10 MB + 1 byte   empty                      → 400
  │                              over UPLOAD_MAX_BYTES      → 413
  ├─ sniff_document_mime_type    not PDF/PNG/JPEG/WebP/HEIC → 415
  ├─ extract_text()              [services/contract/extractor.py]
  │    └─ GeminiClient.generate_structured(
  │         operation="contract.extract", tier=EXTRACTION,
  │         contents=[file bytes + mime, prompt.user], system=prompt.system,
  │         response_model=ExtractedText)
  │         ├─ is_document false or empty text                     → 422
  │         └─ GeminiError → core/errors.py → 503 (+Retry-After) / 504 / 502 / 500
  └─ 200 ContractExtractResponse {filename, mime_type, size_bytes, page_count, text}
```

## All commands, in order

Run from `backend/` with the venv activated (see `NF-P1-001-local-dev-setup.md`). `GEMINI_API_KEY` must be in `.env.local` (see `NF-P1-004-gemini-client.md`, step 1).

### 0. Install the new dependencies

```bash
pip install -r requirements-dev.txt
```

Check: `pip show python-multipart pyyaml` lists `0.0.32` and `6.0.3`.

### 1. Checks

```bash
pytest
ruff check .
black --check .
mypy app tests
```

Expected: `66 passed, 4 skipped` (3 live tests plus the Firestore emulator test), `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`.

Only this task's tests:

```bash
pytest tests/unit/test_validators.py tests/unit/test_prompt_loader.py tests/unit/services/test_contract_extractor.py tests/integration/api/test_contracts_extract.py -v
```

### 2. End-to-end test with real Gemini (uses a little free-tier quota)

**Windows PowerShell**
```powershell
$env:RUN_LIVE_GEMINI = "1"; pytest tests/integration/api/test_contracts_extract_live.py -v; Remove-Item Env:RUN_LIVE_GEMINI
```

**bash**
```bash
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_contracts_extract_live.py -v
```

Expected: `3 passed`:
- English 2-page PDF: text has the employer, `SGD 650` and the passport clause; `page_count` 2.
- Malay phone photo: text stays in Malay (`Gaji bulanan`, `RM 1.500`), not translated.
- Landscape photo: 422.

Only the Firebase token check is faked, because a real token needs the Auth Emulator or the frontend sign-in (NF-P1-009). The request still goes through the full app: multipart parsing, validation, the real Gemini API and the error handlers.

To see the token-usage log lines while it runs, add `-o log_cli=true -o log_cli_level=INFO`.

### 3. Run the API and check it by hand

```bash
uvicorn app.main:app --reload --port 8080
```

In a second terminal. No token gives 401:

**Windows PowerShell**
```powershell
curl.exe -s -F "file=@tests/fixtures/contracts/sample_contract_sg.pdf" http://127.0.0.1:8080/api/v1/contracts/extract
```

**bash**
```bash
curl -s -F "file=@tests/fixtures/contracts/sample_contract_sg.pdf" http://127.0.0.1:8080/api/v1/contracts/extract
```

Expected: `{"detail":"Missing bearer token"}`. With `-H "Authorization: Bearer not-a-real-token"` added: `{"detail":"Invalid authentication token"}`. Both are 401.

With a real token (once NF-P1-009 sign-in exists, copy the ID token from the browser console with `await firebase.auth().currentUser.getIdToken()`):

**Windows PowerShell**
```powershell
$TOKEN = "<paste id token>"
curl.exe -s -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/contracts/sample_contract_my_id_photo.jpg" http://127.0.0.1:8080/api/v1/contracts/extract
```

**bash**
```bash
TOKEN="<paste id token>"
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/contracts/sample_contract_my_id_photo.jpg" http://127.0.0.1:8080/api/v1/contracts/extract
```

Swagger: open `http://127.0.0.1:8080/docs`, click **Authorize**, paste the token, then `POST /api/v1/contracts/extract` → **Try it out** → choose a file → **Execute**.

Use `curl.exe` in PowerShell, not `curl`: in Windows PowerShell 5, `curl` is an alias for `Invoke-WebRequest` and does not understand `-F`.

### 4. Docker

```bash
docker build -t nomadfinance-backend:local .
docker run --rm -p 8080:8080 --env-file .env.local nomadfinance-backend:local
```

The prompt file ships inside the image (`app/prompts/contract/extract.v1.yaml`). The no-token request from step 3 returns 401. A request with a (fake) token returns 500 in local Docker only; see Troubleshooting.

## Verified results (2026-09-24)

| Check | Result |
|---|---|
| pytest | 66 passed, 4 skipped |
| ruff / black / mypy | clean (125 files) |
| Live E2E (3 tests) | 3 passed on first attempt; 2.0–3.5 s and about 1,350–1,570 tokens per file |
| Photo transcription | Exact, kept in Malay, list layout and indentation preserved |
| PDF transcription | Exact, `page_count` 2, blank line between pages |
| Real uvicorn, no token / bad token | 401 / 401 |
| Docker | Builds (395 MB), `/health` 200, route in OpenAPI, prompt file present, no token 401 |

Live output for the photo:

```
PERJANJIAN KERJA

Majikan: Ladang Sawit Sri Jaya Sdn Bhd, Johor, Malaysia
Pekerja: Budi Santoso (Indonesia)

1. Jabatan: Pekerja ladang
2. Gaji bulanan: RM 1.500
3. Potongan gaji: RM 300 sebulan untuk
   yuran agensi selama 12 bulan
...
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Form data requires "python-multipart" to be installed` at startup | Step 0 not run: `pip install -r requirements-dev.txt`. |
| `FileNotFoundError: ...extract.v1.yaml` at startup | Prompt file missing or renamed. The app loads it at import on purpose, so it fails at startup rather than on the first request. |
| 415 for a real photo | Only PDF, PNG, JPEG, WebP, HEIC/HEIF are accepted. Screenshots saved as GIF or documents as .docx must be converted. |
| 413 for a phone scan | Over 10 MB. Lower the camera resolution, or raise `UPLOAD_MAX_BYTES` (Gemini's inline limit is about 20 MB per request). |
| 422 `No readable document found` for a real contract | Photo too dark, blurred or cut off. Retake it flat and in good light. |
| 503 with `Retry-After: 30` | Gemini busy or free-tier quota used up, after 3 attempts. Wait and retry. |
| 500 `Internal Server Error` for any request with a token, **in local Docker only** | The container has no Google credentials, so the Firebase Admin SDK fails before it can check the token (`DefaultCredentialsError` in `docker logs`). Cloud Run and the host (after `gcloud auth application-default login`) are fine. For Docker, test without a token, or use the Auth Emulator (NF-P1-005 step 4). |
| Live tests `SKIPPED` | `RUN_LIVE_GEMINI` not set to `1` (step 2). |
| Live test fails with 503 | Google-side capacity (see NF-P1-004). Rerun later. |

## Commit and PR for this task

Branch: `feature/backend-document-extract`. From the **repo root**:

```bash
git add backend docs
git status
```

Check the list: only NF-P1-006 files (table above), the three fixtures, `docs/api/endpoints.md`, this runbook and the one-line update in `NF-P1-004-gemini-client.md`. Never `.env.local`.

```bash
git commit -m "feat(backend): add contract text extraction endpoint" -m "Refs: NF-P1-006"
```

PR title: `feat(backend): contract text extraction endpoint with Gemini vision (NF-P1-006)`

## Not covered here

- Storing uploads in Cloud Storage (design doc step 1): later Contract Shield task
- Structure-preserving extraction (sections, clauses): NF-P2-001
- Language, country and contract-type detection: NF-P2-002
- Rate limiting (slowapi, 60 rpm): NF-P1-027
- Request ID / hashed user ID / latency logging: NF-P1-028
- The other prompt files and prompt conventions: NF-P1-029
- Upload UI: NF-P2-009
