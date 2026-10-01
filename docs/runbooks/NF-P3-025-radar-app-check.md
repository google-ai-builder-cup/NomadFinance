# NF-P3-025 — Radar: Firebase App Check Enforcement

## Summary

`POST /api/v1/radar/report` now verifies a Firebase App Check token (`X-Firebase-AppCheck` header) before it does anything else — ahead of even the AI-call rate limit, so a scripted caller is rejected before it costs any of that shared budget. This closes the gap that endpoint's own docstring had flagged since NF-P3-001: *"App Check / reCAPTCHA enforcement is wired separately (NF-P3-025)."*

Despite the tracker listing this as "Backend," it genuinely needed a small frontend half too — nothing anywhere sent an App Check token before this task, and no other task owned that. Enforcement defaults to **off** (`APP_CHECK_ENABLED=false`), on purpose: App Check was only ever turned on at the Firebase *project* level (NF-P0-005), never wired into any code, and there's no real reCAPTCHA v3 site key registered for a deployed domain yet. Enforcing before one exists would reject every real submission along with the bots — see "Before this works in production" below.

## What "reject if score < 0.5" actually means here

Checked the installed `firebase_admin.app_check` module's own source before writing anything: `verify_token()` is binary — a valid signed JWT, or a `ValueError`. There is no score field anywhere in what the backend can see. The score threshold genuinely exists, but Firebase enforces it *before* minting a token at all, configured in Firebase Console → App Check → the reCAPTCHA v3 provider's score settings — not something Python code here computes. Implemented real Firebase App Check (matching the task's own title) rather than a raw call to Google's `siteverify` REST API (which *would* hand back a literal score, but wouldn't be "Firebase App Check Enforcement" — a different product, duplicating what App Check already does upstream).

## Files

| File | Change |
|---|---|
| `backend/app/config.py` | `app_check_enabled: bool = False` |
| `backend/app/core/security.py` | `verify_app_check_token()` — mirrors `verify_id_token()`'s exact wrapping style |
| `backend/app/dependencies.py` | `verify_app_check` — a FastAPI dependency, off when `app_check_enabled` is false, 403 on a missing or invalid token, 503 if App Check's signing keys can't be fetched |
| `backend/app/api/v1/radar.py` | `Depends(verify_app_check)` added to `/radar/report`'s dependencies, first in the list (ahead of `limit_ai_calls`); docstring updated; 403 added to the documented responses |
| `backend/tests/unit/test_dependencies.py` | 5 new tests |
| `backend/.env.example` | `APP_CHECK_ENABLED` (commented, default shown) |
| `frontend/src/lib/appCheck.ts` (new) | `appCheckHeader()` — mirrors `lib/messaging.ts`'s graceful-no-op shape exactly |
| `frontend/src/services/radarService.ts` | `submitReport()` spreads `appCheckHeader()` into its request headers |
| `frontend/src/vite-env.d.ts`, `frontend/.env.example` | `VITE_FIREBASE_APPCHECK_SITE_KEY` |
| `docs/api/endpoints.md` | `/radar/report`'s own section: the placeholder "wired separately (NF-P3-025)" sentence replaced with what's actually true now; new 403 row in its error table |

No new npm dependency: `firebase/app-check` is already part of the installed `firebase` package, same as `firebase/auth`/`firebase/messaging`.

## Decisions

1. **`app_check_enabled` defaults to `false`, not `true`.** The opposite choice — secure by default — was the first draft, until working through what happens if the real site key is never registered before the real demo: every genuine report submission would 403 in production too, not just bots. A missing anti-abuse check is a smaller risk than an accidentally-disabled submission form on the one day it matters. Mirrors `rate_limit_enabled`'s own existing boolean-toggle shape in `config.py`, not the stricter "required outside local" pattern `cron_service_account`/`cron_audience` use — there's no missing *credential* to validate against here, just a feature that shouldn't turn on by accident.
2. **Wired onto `/radar/report` only**, not evidence upload or any read endpoint — the task says this endpoint specifically, and it's the one public-facing *submission* form; reads and the evidence follow-up already require a signed-in user via Firebase Auth, a different and already-enforced gate.
3. **Runs before `limit_ai_calls`, not after.** Placed first in the route's `dependencies=[...]` list on purpose: a request this gate would reject shouldn't also burn through the shared AI-call rate limit on its way to being rejected anyway.
4. **403, not 401, for a missing or bad App Check token.** `401` is already this same endpoint's answer for a missing or invalid *Firebase Auth* token (`get_current_user`) — reusing it for a second, different credential would make one status code mean two different failures. `403` matches this codebase's own existing precedent (`require_cloud_scheduler`'s identity-mismatch check).
5. **`lib/appCheck.ts` mirrors `lib/messaging.ts`'s shape deliberately**, down to the "both configured or neither, nothing else breaks either way" framing — same kind of optional Firebase feature, same established pattern for one, reused rather than inventing a new shape for this one.

## Flow

```
api/v1/radar.py, POST /report — dependencies, in order:
  verify_app_check(token=Header("X-Firebase-AppCheck"), settings)
    app_check_enabled is false              → return, no-op (today's default)
    token is None                            → 403 "Missing App Check token"
    verify_app_check_token(token) raises     → 403 "Invalid App Check token"
                                        or    → 503 (App Check's signing keys unreachable)
    else                                     → passes through
  limit_ai_calls(...)                        → unchanged, NF-P1-027
  (the route function itself, unchanged)

services/radarService.ts, submitReport()
  appCheckHeader()
    VITE_FIREBASE_APPCHECK_SITE_KEY unset    → {} (today's default — no header sent)
    getToken(appCheckInstance) fails         → {} (never throws into the caller)
    else                                     → { "X-Firebase-AppCheck": token }
  spread into the POST's own headers
```

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| Backend: `ruff check .`, `black --check .`, `mypy --strict app/services/`, `mypy app/` | Clean |
| Backend: `pytest -q` | 936 passed, 60 skipped (unrelated live-Gemini tests) |
| New: `test_dependencies.py` (+5) | Disabled passes through without even calling the verifier; missing token → 403; valid token → no exception; invalid token → 403; signing-keys-unreachable → 503 |
| Frontend: `tsc -b`, `eslint --max-warnings 0`, `prettier --check` | Clean |
| Frontend: `vitest run` | 181 passed, unchanged (no new pure logic to unit test — `appCheckHeader()` is thin I/O, exercised live instead) |
| Frontend: `pnpm build` | Clean |

**Live (Firebase emulators, a real signed-in test worker, a real Firebase Auth ID token)**

- Submitted a real report with `APP_CHECK_ENABLED` left at its default (`false`, the actual running config): request reached the real pipeline and only failed on the pre-existing, unrelated local-dev gap (`GEMINI_API_KEY=not-used-here` → a 500 from Gemini itself) — confirms the disabled path is a genuine no-op, not just in tests
- Started a second backend process on another port, same emulators, with `APP_CHECK_ENABLED=true`:
  - The same valid Auth token, no `X-Firebase-AppCheck` header → **403 "Missing App Check token"**, before any Gemini call (confirmed in the log — no `gemini_error` line this time, unlike the disabled-path run above)
  - The same valid Auth token, a garbage `X-Firebase-AppCheck` value → **403 "Invalid App Check token"**
  - `/openapi.json` for this endpoint lists `403` with the documented description

**Not verified** (the credential gap flagged before building): a real, valid App Check token succeeding end-to-end — needs a reCAPTCHA v3 site key registered for a real deployed domain, which doesn't exist yet.

## Before this works in production (manual)

1. Register a reCAPTCHA v3 site key in [Google's reCAPTCHA admin console](https://www.google.com/recaptcha/admin) for `nomadfinance-prod.web.app` and `nomadfinance-prod.firebaseapp.com`.
2. Firebase Console → Project settings → App Check → register the web app, reCAPTCHA v3 provider, that site key. Set the minimum score there — this is where "reject if score < 0.5" actually lives, not in this code.
3. Set `VITE_FIREBASE_APPCHECK_SITE_KEY` in the frontend's production env, redeploy.
4. Set `APP_CHECK_ENABLED=true` on the backend (Cloud Run env var / Secret Manager as appropriate), redeploy.
5. One real submission from the deployed site, confirmed in Cloud Run logs — suggested as part of **NF-P4-013 (Final Deployment Verification)**, which already exists in the tracker for exactly this kind of real-deployed-site check, rather than inventing a separate task for it.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Every real report submission gets 403 in production | `APP_CHECK_ENABLED=true` was set before steps 1–3 above were done — the frontend has nothing to send. Either finish those steps or set it back to `false` |
| `verify_app_check` never seems to run, even with `APP_CHECK_ENABLED=true` | Check the header name is exactly `X-Firebase-AppCheck` (case-insensitive over HTTP, but the alias must match) |
| 503 instead of 403 on a bad token | App Check's own JWKS endpoint couldn't be reached (network/outbound issue) — a real signing-key fetch failure, not a bad token; check outbound connectivity from Cloud Run |

## Definition of Done (Backend Endpoint)

- [x] Endpoint defined in FastAPI with Pydantic request/response models (unchanged; this task adds a dependency, not a new route)
- [x] Firebase Auth token verification — unchanged, still `get_current_user`; App Check is a second, distinct gate
- [x] Structured logging — existing request-id/user-id logging on this route is untouched
- [x] Error handling with specific HTTP status codes (403 for a bad/missing App Check token, 503 when verification itself is unreachable)
- [x] Manual test via Swagger /docs successful — done live via curl against a running instance (see Verified results); OpenAPI schema confirmed to list the new 403
- [x] OpenAPI docs updated
- [x] docs/api/endpoints.md updated — the endpoint's own placeholder sentence replaced, new 403 row added to its error table
- [x] Rate limiting applied — unchanged; App Check now runs ahead of it (decision 3)

## Commit and PR

Branch: `feature/radar-app-check` (already checked out, matches tasks.md).

```
feat(radar): wire app check enforcement to report submission
Refs: NF-P3-025
```

PR title: `feat: Firebase App Check enforcement for radar report submission (NF-P3-025)`

## Not covered here

Actually registering a reCAPTCHA v3 site key, or turning `APP_CHECK_ENABLED` on anywhere — both need a real Google credential tied to a real deployed domain, outside what this task (or this sandbox) can do. See "Before this works in production" above.
