# Deferred Items Log

Things found while working on a task but left out of it on purpose, so they are not lost. Each item says where it came from, why it waits, and which task or person should pick it up.

**How to use this file**
- Add a row when a task finds something out of its scope. Use the next free `D-` number.
- When an item is done, set its status to `Done (<task or PR>)`. Don't delete it.
- Before starting a task, search this file for its task ID.

Last updated: 2026-09-24, after NF-P1-006.

## 1. Actions needed now (no code, a person has to do them)

| ID | Found in | Item | Why it matters | Who | Status |
|---|---|---|---|---|---|
| D-01 | NF-P1-004 | Grant the Cloud Run service account read access to the Gemini key: `gcloud secrets add-iam-policy-binding gemini-api-key --project nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"` | Checked 2026-09-24: the secret has **no IAM bindings**. `main` now requires `GEMINI_API_KEY`, so the next Cloud Run deploy fails until this is done. | Project owner | Open |
| D-02 | NF-P1-004 | Redeploy after D-01: `bash scripts/deploy_manual.sh` from `backend/` | Checked 2026-09-24: the live service only has `APP_ENV=prod`, and is still running an image from before NF-P1-004. | Devam / Pranjal | Open |
| D-03 | NF-P1-004 | Every teammate adds `GEMINI_API_KEY` to `backend/.env.local` | The backend refuses to start without it (NF-P1-004 runbook, step 1). | Aditya, Pranjal | Open |
| D-04 | NF-P1-001, 004, 006 | Update the task tracker: NF-P1-006 path is `/api/v1/contracts/extract` (not `/documents/extract`); DoD model names (2.5 / 1.5 / 2.0 Flash) are outdated, see ADR-002; DoD mentions `docs/api-contract.md`, the real file is `docs/api/endpoints.md`; NF-P3-002 says `text-embedding-004`, which is gone (use `gemini-embedding-001`). | The tracker is the team's source for task scope. | Devam | Open |

## 2. Code fixes scheduled into a later task

| ID | Found in | Item | Target task | Status |
|---|---|---|---|---|
| D-05 | NF-P1-006 | Enforce the upload size on the raw request body, before the whole file is received. Today FastAPI reads the full upload first; the 10 MB check runs after. Cloud Run's 32 MB request cap still applies. | NF-P1-027 (CORS + rate limiting, Devam) | Open |
| D-06 | NF-P1-004 | App logging isn't configured, so INFO logs from `app.*` (including `gemini_call` token usage) are dropped under uvicorn/gunicorn. The smoke test shows them because it configures logging itself. | NF-P1-028 (structured logging, Pranjal) | Open |
| D-07 | NF-P1-001, 002 | All six `.github/workflows/*.yml` are empty, so no checks run in CI. Backend CI should run `pytest`, `ruff check .`, `black --check .`, `mypy app tests` and the Docker build. | NF-P1-020 (GitHub Actions, Pranjal) | Open |
| D-08 | NF-P1-004 | Reasoning tier (`gemini-3.5-flash`) takes 13–23 s on short prompts because of thinking. Long contracts may hit the 30 s timeout. Consider a thinking budget for that tier or a larger `GEMINI_TIMEOUT_SECONDS`. | NF-P2-004 (clause comparison, Devam) | Open |
| D-09 | NF-P1-004 | `gemini-3.8-flash` was the first choice for reasoning but returned 503 on the free tier. Retry it with the smoke test; switch with `GEMINI_MODEL_REASONING=gemini-3.8-flash` if it works. | Any time; recheck before NF-P2-004 | Open |
| D-10 | NF-P1-006 | Frontend must show translated error messages by **HTTP status code**; the API's `detail` text is English only (see `docs/api/endpoints.md`, Error format). | NF-P2-009 (upload UI, Aditya) and every frontend task that calls the API | Open |

## 3. Code fixes not yet assigned to a task

| ID | Found in | Item | Impact | Suggested owner | Status |
|---|---|---|---|---|---|
| D-11 | NF-P1-006 | In a container without Google credentials (local Docker), any request **with** a token returns 500: firebase-admin raises `DefaultCredentialsError` before verifying the token, and `core/security.py` doesn't catch it. Fix: map it to a clear 503, or check credentials at startup. | Local Docker testing only. Cloud Run and the host are fine. Client sees plain "Internal Server Error", no stack trace. | Aditya (NF-P1-005 owner) | Open |
| D-12 | NF-P1-001 | Starlette 1.7 warns that `TestClient` on `httpx` is deprecated and suggests `httpx2`. Harmless while versions are pinned. Fix needs a `requirements-dev.txt` change (shared file). Keep `httpx` itself: the Gemini client imports it. | Warning in every pytest run. Would break only on a future Starlette upgrade. | Devam, before any Starlette/FastAPI upgrade | Open |

## 4. Notes and decisions to keep in mind (no fix planned)

| ID | Found in | Note |
|---|---|---|
| D-13 | NF-P1-004 | Google may use free-tier Gemini content to improve its products (pricing page). Use demo data only until a billing-enabled key is set up; real worker contracts and bills need the paid tier. Recorded in ADR-002. |
| D-14 | NF-P1-002 | `NF-P1-002-backend-docker.md` "Verified results" shows 286 MB and step 9 expects `2 passed`. Both were true for that task; the image is 395 MB and the test count has grown since. Step 1 already points to the new size. |
| D-15 | NF-P1-001, 002 | Merged commits `5173f5a` and `056dea0` have `Refs: ...` on the subject line. History, left as is. Use two `-m` flags so `Refs:` lands on its own line. |
| D-16 | NF-P1-006 | Uploads are not stored (the design doc's Cloud Storage step 1 is not built yet). Good for privacy; whichever Contract Shield task needs the original file later must add storage with a retention rule. |
