# NF-P1-027 — CORS + Rate Limiting Middleware

## Summary

The backend can now be called from the deployed site, and no single caller can flood it.

**CORS.** CORS allows only the Firebase Hosting origins in production (`nomadfinance-prod.web.app`, `.firebaseapp.com`) and the Vite dev and preview servers locally. Any origin list can be set with `CORS_ALLOWED_ORIGINS`, and a malformed one stops the app at startup.
- Allowed request headers: `Authorization`, `Content-Type` and `X-Request-ID`.
- No cookies: we use bearer tokens.
- The page can read `X-Request-ID`, `Retry-After` and the rate-limit headers.

**Rate limits.** The API allows **60 requests a minute per caller** across all of `/api/`. Endpoints that call Gemini also have a **10 a minute** budget, because all users share one free-tier Gemini quota.
- **Who is counted:** a signed-in caller by user (the token's uid, hashed), otherwise by IP. Many workers share one IP (dormitory Wi-Fi, mobile carriers), so a per-IP limit would block them together.
- **Never limited:** `/health` and the Cloud Scheduler endpoints (`/api/v1/internal/*`).
- **Over a budget:** `429` with the usual `{"detail": ...}`, `Retry-After`, and `X-RateLimit-*`. The frontend already shows "Too many requests. Please wait a minute and try again." for a 429.

**Request size (D-05).** A request larger than the upload limit plus 64 KB is refused with `413` before its body is read. Before, FastAPI took in up to 32 MB (Cloud Run's cap) before the endpoint could refuse it.

**Middleware order.** CORS sits outside both refusals, so a `429` or `413` still carries CORS headers. Without them the browser hides the status, and the app could only say "network error".

**slowapi.** The tracker names slowapi, but slowapi 0.1.10 doesn't work with our FastAPI 0.141: its middleware cannot see routes inside included routers and **silently skips every `/api/v1` route**. A test with 62 requests found this. The app uses `limits` directly (slowapi's own engine, with the same `"60/minute"` notation) in a small middleware plus one dependency, so `requirements.txt` only gains `limits==5.8.0`.

**Account deletion on the live site (D-44, Pranjal's NF-P1-023).** It needed three things:
1. CORS: this task.
2. `VITE_API_BASE_URL` in the frontend build: this task passes it in `frontend-deploy.yml`, and a repository variable holds the value.
3. Two IAM roles for the backend: Pranjal's grant script, run once by a project owner.

Steps 2 (the variable) and 3 are in "Turn on account deletion in production" below.

## Files

| File | Purpose |
|---|---|
| `backend/app/core/rate_limit.py` (new) | `RateLimitMiddleware` (API-wide budget), `limit_ai_calls` dependency (Gemini budget), caller key (hashed uid, or last `X-Forwarded-For` hop), `reset_rate_limits()` for tests |
| `backend/app/core/middleware.py` | `BodySizeLimitMiddleware`: 413 from `Content-Length`, or while counting a body sent without one |
| `backend/app/main.py` | Middleware order: logging → CORS → rate limit → body size → app; CORS settings |
| `backend/app/config.py` | `cors_allowed_origins` (defaults per `APP_ENV`, checked), `rate_limit_enabled`, `rate_limit_default`, `rate_limit_ai` (checked with `limits`), `request_max_bytes` |
| `backend/app/api/v1/contracts.py` | `POST /contracts/extract` uses `Depends(limit_ai_calls)`; 429 documented |
| `backend/app/api/v1/internal.py` | Comment: never limited (the middleware skips `/api/v1/internal/`) |
| `backend/requirements.txt` (shared, approved) | `+limits==5.8.0` |
| `.github/workflows/frontend-deploy.yml` (shared, approved) | `VITE_API_BASE_URL: ${{ vars.VITE_API_BASE_URL }}` in the Build step |
| `backend/.env.example` | `UPLOAD_MAX_BYTES`, `CORS_ALLOWED_ORIGINS`, `RATE_LIMIT_*` (commented, defaults shown) |
| `backend/tests/integration/api/test_cors_rate_limit.py` (new) | 26 tests: CORS, budgets, keys, exemptions, 413 |
| `backend/tests/conftest.py` | Resets the limiter before every test |
| `docs/api/endpoints.md` | CORS, rate limits and request size section; 413/429 rows |
| `docs/runbooks/NF-P1-023-user-profile-page.md` | Status of its "Turn it on in production" steps; one wording fix in step 1 |
| `docs/deferred-items.md` | D-05 done, D-44 code done, D-47 partly; new D-52 |

## Decisions

1. **Who a limit counts against.** A signed-in caller's `sub` claim is read *without* checking the signature, only to choose the counter. The endpoint still verifies the token, so a forged `sub` only earns a fresh counter for a request that ends in 401. Callers without a token are counted by the **last** `X-Forwarded-For` entry: Google's front end appends the address it saw, and earlier entries can be forged.
2. **Memory storage, per instance.** With `--max-instances 2`, the worst case is twice the budget, and counts reset on restart. Redis (Memorystore) would cost money every month (D-52).
3. **Gemini budget on top of the API-wide one:** 10 a minute per user on `POST /contracts/extract`. Every future Gemini endpoint adds `dependencies=[Depends(limit_ai_calls)]`.
4. **One size limit for every route:** `UPLOAD_MAX_BYTES` + 64 KB. JSON requests are tiny.
5. **Moving window:** 60 in *any* 60 seconds, not a counter that resets on the minute, so no double burst at the boundary.

## Flow

```
request
  RequestLoggingMiddleware   id + one log line (also for 413/429)
  CORSMiddleware             preflight answered here (allowed origin → 200, else 400);
                             adds Access-Control-* to every response, including 413/429
  RateLimitMiddleware        only /api/..., not /api/v1/internal/...
                             key = user:<hash(uid)> or ip:<last X-Forwarded-For>
                             over 60/min → 429 {"detail"} + Retry-After (body never read)
                             else adds X-RateLimit-Limit/Remaining/Reset
  BodySizeLimitMiddleware    Content-Length > 10 MB + 64 KB → 413 (body never read)
                             no Content-Length → counts chunks, 413 once over
  FastAPI routing
    POST /contracts/extract  Depends(limit_ai_calls): over 10/min → 429 + its own X-RateLimit-*
```

## All commands, in order

From `backend/`, with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash).

### 1. Install the new dependency and run the checks

```bash
pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
black --check .
mypy app
```

Only this task's tests:

```bash
python -m pytest tests/integration/api/test_cors_rate_limit.py -q
```

### 2. Try it on a local server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

In a second terminal (bash / Git Bash; in PowerShell use `curl.exe` and the same arguments):

```bash
# Preflight from the Vite dev origin: 200 with Access-Control-Allow-Origin
curl -s -o /dev/null -D - -X OPTIONS http://127.0.0.1:8080/api/v1/users/me -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: DELETE" -H "Access-Control-Request-Headers: authorization"

# Preflight from another origin: 400, no Access-Control-Allow-Origin
curl -s -D - -X OPTIONS http://127.0.0.1:8080/api/v1/users/me -H "Origin: https://evil.example" -H "Access-Control-Request-Method: DELETE"

# 61 calls as one (fake) user: 60 x 401, then 429 with Retry-After
TOK="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJsb2NhbC10ZXN0In0.sig"
for i in $(seq 1 61); do curl -s -o /dev/null -w "%{http_code} " -X DELETE http://127.0.0.1:8080/api/v1/users/me -H "Authorization: Bearer $TOK"; done; echo
curl -s -D - -X DELETE http://127.0.0.1:8080/api/v1/users/me -H "Authorization: Bearer $TOK" | grep -iE "^HTTP|retry-after|x-ratelimit"

# 30 MB upload as another user: 413 at once, nothing uploaded
TOK2="eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJvdGhlci11c2VyIn0.sig"
head -c 31457280 /dev/zero > big.bin
curl -s -w "\nHTTP %{http_code}, sent %{size_upload} bytes\n" -X POST http://127.0.0.1:8080/api/v1/contracts/extract -H "Authorization: Bearer $TOK2" -F "file=@big.bin;type=application/pdf"
rm big.bin
```

The fake token is not signed, so the endpoints answer 401. That's enough to see the counting.

### 3. Turn on account deletion in production

**a. Grant the two roles** (once, a project owner, Git Bash from the repo root, logged in to gcloud):

```bash
bash infra/iam/grant-account-deletion-roles.sh
gcloud projects get-iam-policy nomadfinance-prod --flatten="bindings[].members" --filter="bindings.members:nomadfinance-backend@" --format="value(bindings.role)"
```

Expected: `roles/datastore.user` and `roles/firebaseauth.admin`. Check the bucket grant:

```bash
gcloud storage buckets get-iam-policy gs://nomadfinance-prod.firebasestorage.app --format="value(bindings)" | grep -o "storage.objectUser"
```

**Do this before anyone deletes an account in production.** Without the roles, the backend deletes the Firestore data, then fails with 503: the sign-in account and files stay behind.

**b. Add the GitHub repository variable.** Repository → Settings → Secrets and variables → Actions → **Variables** tab → New repository variable:

| Name | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://nomadfinance-api-54982290462.asia-south1.run.app` |

It's the Cloud Run URL: public, not a secret. Use the Variables tab, not Secrets.

**c. Merge the PR.** `backend-deploy.yml` deploys the API and `frontend-deploy.yml` rebuilds the site with the variable.

**d. Check the live API:**

```bash
API=https://nomadfinance-api-54982290462.asia-south1.run.app
curl -s -o /dev/null -D - -X OPTIONS $API/api/v1/users/me -H "Origin: https://nomadfinance-prod.web.app" -H "Access-Control-Request-Method: DELETE" -H "Access-Control-Request-Headers: authorization" | grep -iE "^HTTP|access-control-allow-origin"
curl -s -D - -X DELETE $API/api/v1/users/me -H "Origin: https://nomadfinance-prod.web.app" | grep -iE "^HTTP|x-ratelimit|access-control-allow-origin"
```

Expected: `200` with `access-control-allow-origin: https://nomadfinance-prod.web.app`, then `401` with `x-ratelimit-limit: 60`.

And the site bundle:

```bash
js=$(curl -s https://nomadfinance-prod.web.app/ | grep -oE '/assets/index-[^"]+\.js' | head -1)
curl -s "https://nomadfinance-prod.web.app$js" | grep -c "nomadfinance-api-54982290462"
```

Expected: `1` or more.

**e. Delete a throwaway account on the live site.**
1. Sign in at https://nomadfinance-prod.web.app/sign-in with one of the **test phone numbers** (D-20; the code is shared in chat, not in the repo) and finish onboarding. A returning browser shows "New version available" once; click Refresh.
2. Profile → **Delete my account** is now shown. Tick the box, delete, and confirm the sign-in again if asked.
3. You land on the sign-in page with "Your account and data have been deleted."
4. Check: Firebase console → Authentication → the test number's user is gone; Firestore → no `users/<uid>`.

Signing in with the same test number later creates a new, empty account. Never use a real person's account for this.

## Verified results (2026-09-27)

| Check | Result |
|---|---|
| `pytest -q` | 211 passed, 5 skipped (26 new) |
| `ruff check .`, `black --check .`, `mypy app` | Pass |
| `pip install --dry-run -r requirements.txt` | Resolves: 61 packages, `limits` 5.8.0 (+ `deprecated`, `wrapt`) |
| slowapi 0.1.10 check, before switching | `_find_route_handler` returned `None` for `/api/v1/contracts/extract`: 62 requests, never a 429 |
| Local server: preflight from `http://localhost:5173` | 200, `access-control-allow-origin` set, methods and headers as configured, max-age 3600 |
| Local server: preflight from `https://evil.example` | 400 "Disallowed CORS origin", no allow-origin |
| Local server: 61 calls as one user | #59 and #60 → 401, #61 → 429 with `retry-after: 55`, `x-ratelimit-limit: 60`, `remaining: 0`, CORS headers, `{"detail": "Too many requests…"}` |
| `/health` right after | 200 (never limited) |
| Local server: 30 MB upload with `Content-Length` | 413 "The request is larger than 10 MB." in 3 ms, **0 bytes** sent |
| Local server: 30 MB upload, chunked (no length) | 413 after about 11.3 MB instead of 30 MB |
| Tests also cover | Per-user budgets, one budget across endpoints, forged `X-Forwarded-For` prefix ignored, internal endpoint never limited, switch-off flag, unusable tokens fall back to IP, uid never in the key, Gemini budget (10/min, own headers), 413 carries CORS, settings validation |
| Production, 2026-09-27, before merge | Preflight from web.app → 405 (no CORS yet); backend service account has only `roles/datastore.user` (grant script not run yet) |

Still to verify: step 3 after merge. The Docker image build is left to `backend-ci.yml`, because Docker Desktop was not running locally.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Browser: "blocked by CORS policy" | The page's origin isn't allowed: check `CORS_ALLOWED_ORIGINS` / `APP_ENV`. An origin has no trailing slash or path |
| Browser shows "No internet connection" but the API is up | A response without CORS headers. From this task every refusal carries them; check the middleware order in `main.py` |
| App fails at startup: `... is not an origin` | A malformed entry in `CORS_ALLOWED_ORIGINS` (must be `https://host[:port]`) |
| App fails at startup: `RATE_LIMIT_DEFAULT: couldn't parse` | Use the `limits` notation: `60/minute`, `100/hour`, `60/minute;1000/day` |
| 429 during local testing | Wait for `Retry-After`, restart the server (counts are in memory), or set `RATE_LIMIT_ENABLED=false` in `backend/.env.local` |
| Tests hit 429 unexpectedly | A test built its own app without the `conftest.py` reset; the limiter is process-wide |
| Cron run gets 429 | Can't happen for `/api/v1/internal/*`; if a new internal route lives elsewhere, move it under `/api/v1/internal/` |
| "Delete my account" still missing on the live site | `VITE_API_BASE_URL` variable missing (step 3b) or the site wasn't rebuilt after adding it (re-run "Frontend deploy") |
| Delete answers 503 in production | The grant script hasn't been run (step 3a) |
| 413 for a file under 10 MB | `UPLOAD_MAX_BYTES` was lowered, or the client sends extra form fields over 64 KB |

## Definition of Done (Backend Endpoint, as it applies to middleware)

- [x] Pydantic/settings contracts: new settings typed and checked at startup
- [x] Firebase Auth: unchanged; the limiter never trusts the token, the endpoints still verify it
- [x] Structured logging: 413/429 pass through `RequestLoggingMiddleware` (id, hashed user, latency)
- [x] Specific status codes: 413 and 429 with `{"detail"}`, `Retry-After`; CORS on both
- [x] Manual test: local server with curl (step 2); live after merge (step 3)
- [x] OpenAPI: `429` documented on `POST /contracts/extract`
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied to user-facing endpoints

## Commit and PR for this task

Branch: `feature/backend-cors-rate-limit` (already checked out). From the repo root:

```bash
git add backend/app backend/requirements.txt backend/.env.example backend/tests .github/workflows/frontend-deploy.yml docs/api/endpoints.md docs/runbooks/NF-P1-027-backend-cors-rate-limit.md docs/runbooks/NF-P1-023-user-profile-page.md docs/deferred-items.md
git status
```

```bash
git commit -m "feat(api): add CORS, per-user rate limits and request size limit" -m "Refs: NF-P1-027"
```

PR title: `feat(api): CORS for Hosting, per-user rate limits, early 413 (NF-P1-027)`

## Not covered here

- Cloud Armor / DDoS protection and shared (Redis) counts: D-52
- Client-side file size check before upload: NF-P2-009 (upload UI)
- Rate limits for the remittance, radar and FIB endpoints: automatic (API-wide); their Gemini calls add `Depends(limit_ai_calls)` in their own tasks
