# NF-F0-002 — API v2 conventions and error envelope

## Summary

Every `/api/v2` endpoint now has one set of rules to follow, written in `docs/api/v2-conventions.md`, with a sample for each rule in `docs/mocks/conventions/` and the backend's error handling changed to match. The Coach, Scam and Partner contracts (NF-FC-002, NF-SA-002, NF-PA-001) cite that file instead of repeating it.

| Convention | Rule in one line |
|---|---|
| Prefix | New routes under `/api/v2/`; v1 unchanged |
| Error envelope | `{code, message, request_id}`, plus `details` on 422 only; `request_id` equals `X-Request-ID` |
| Pagination | `limit` (1 to 100, default 20) and opaque `cursor`; response `{items, next_cursor}` |
| Streaming | SSE events `token`, `slot_update`, `done`, `error`; `: ping` after 15 s of silence; a message is final only after `done` |
| Idempotency | `Idempotency-Key`, 24 h, same body replays, different body 422, still running 409 |
| Versioning | Additive changes are free; breaking ones need 90 days between `Deprecation` and `Sunset`, then 410 |

Decisions taken (Devam, 2026-10-06):
- The conventions are a new file, `docs/api/v2-conventions.md`, not a section of the 1,300-line `endpoints.md`. The tracker's `docs/api-contract.md` is `docs/api/endpoints.md` in the repo (D-04); `endpoints.md` now points to the new file.
- `details: [{field, issue}]` is allowed on 422 only, and never holds the value the client sent.
- The rate limiter's 429 and the size limit's 413 also answer in the envelope on `/api/v2`, so "every v2 error is an envelope" is true without exceptions.

## What changed in the backend

Only paths under `/api/v2` change. Every other path gets exactly what it got before (a test checks the old bodies).

| File | Change |
|---|---|
| `backend/app/schemas/errors.py` (new) | `ErrorEnvelope`, `ErrorDetail` |
| `backend/app/core/errors.py` | `ApiError` (an `HTTPException` with a `code`), handlers for `HTTPException`, validation errors, Gemini errors and uncaught exceptions; `error_response()` builds the body; v1 requests are handed to FastAPI's own handlers |
| `backend/app/core/middleware.py` | The request id is also kept on the request scope (the 500 handler runs after the logging context is gone); 413 in envelope form on v2 |
| `backend/app/core/rate_limit.py` | 429 in envelope form on v2 |
| `backend/app/core/logging.py`, `backend/app/main.py` | `REQUEST_ID_HEADER` moved to `logging.py` to avoid an import cycle; `main.py` imports it from there |

No new package, no environment variable, no shared file.

## Manual test

With the venv active, from `backend/`. There are no real v2 routes yet, so the unknown-path answer is the visible one.

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --port 8080
# second terminal
curl.exe -s -i http://127.0.0.1:8080/api/v2/anything
curl.exe -s -i http://127.0.0.1:8080/api/v1/anything
```

bash:

```bash
source .venv/bin/activate   # .venv/Scripts/activate on Windows Git Bash
uvicorn app.main:app --port 8080 &
curl -s -i http://127.0.0.1:8080/api/v2/anything
curl -s -i http://127.0.0.1:8080/api/v1/anything
```

Expected: the v2 call returns `404` with `{"code":"not_found","message":"Not Found","request_id":"..."}` and the same value in the `X-Request-ID` header; the v1 call returns `404` with `{"detail":"Not Found"}`.

The other cases (422, 429, 413, 500, Gemini errors, `ApiError`) need a route that fails on purpose, so they are covered by the automated tests, which add throwaway routes to the app:

```bash
python -m pytest tests/integration/api/test_v2_error_envelope.py tests/unit/test_v2_mocks.py -v
```

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `black --check app tests` | clean |
| `ruff check app tests` | clean |
| `mypy app` (what CI runs) | no issues, 133 files |
| `pytest tests` | 1,036 passed, 66 skipped (live and emulator tests); 25 of the passes are new |

## How later tasks use this

- A route raises `HTTPException(...)` or `ApiError(status, code, message)`; it never builds an error body itself.
- The first v2 route (NF-F0-005) creates `backend/app/api/v2/` and mounts it at `/api/v2`, and must widen CORS (D-98).
- Feature contracts say `required`, `optional` or `not used` for the idempotency key on each route, and list any codes of their own.
- Frontend: the API client for v2 reads `code`, then the status, and shows `request_id` in the "contact support" text (D-99).
- Mocks for coach and scam go in their own folders under `docs/mocks/`.
