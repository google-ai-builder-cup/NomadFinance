# NF-P4-004 — Security audit

## Summary

The Firestore and Storage rules, the API's sign-in checks, the rate limits and every place a secret could live were reviewed and tested. Nothing was attacked on the live site: all bypass and rate-limit tests ran on local emulators and a local backend. The live site and Google Cloud were only read (headers, settings, access lists).

**The core is sound.** Every API endpoint behind sign-in refuses every kind of forged, expired or borrowed token that was tried. A worker cannot read another worker's data through the rules, even by collection-group queries. No secret is in the code, the git history or the built app.

**What was found:** 17 findings, none critical. Seven were fixed in this change, each with a test that fails without the fix. The rest need a person with Google Cloud access, or a shared-file change that waits for your OK.

| # | Severity | Finding | Status |
|---|---|---|---|
| F-01 | Medium | The browser API key has no website restriction | **Open: you run 2 commands** (D-87) |
| F-02 | Medium | The site sends no security headers (no CSP, framing, content-type protection) | **Open: diff for your OK** (D-90) |
| F-03 | Medium | One worker's malformed push token could stop alerts for every worker after them | **Fixed** |
| F-04 | Medium | A forged token could use up another worker's rate-limit budget | **Fixed** |
| F-05 | Low-Medium | An emulator setting in production would switch off token signature checks | **Fixed** (startup guard) |
| F-06 | Low | A deleted account's token, and a wrong-issuer scheduler token, answered 500 instead of 401 | **Fixed** |
| F-07 | Low | The API's endpoint list (`/docs`, `/redoc`, `/openapi.json`) was public in production | **Fixed** |
| F-08 | Low | Server-supplied links were put in `href` without checking the scheme | **Fixed** |
| F-09 | Low | A worker's income amount was written to the logs | **Fixed** |
| F-10 | Low | The profile rules accept any content inside the push-token and corridor lists | **Open: verified diff for your OK** (D-93) |
| F-11 | Low | Two moderate advisories in `react-router` (not reachable here) | **Open: needs v7** (D-92) |
| F-12 | Low | Rate limits are per server instance, and made-up user ids are not limited per address | **Open: documented** (D-94) |
| F-13 | Low | Google Cloud access is broader than needed (Editor on the default compute account, 4 owners, no public-access block on the bucket) | **Open: you run commands** (D-89) |
| F-14 | Info | 3 test phone numbers are still configured on the production project | **Open: confirm** (D-88) |
| F-15 | Info | No secret scan in CI; GitHub Actions are pinned by version tag, not commit | **Open: diff for your OK** (D-91) |
| F-16 | Info | App Check and reCAPTCHA Enterprise are off | Known (NF-P3-025, D-32) |
| F-17 | Info | The PDF download link is valid for 24 hours | Accepted |

## What was verified and held up

| Area | Result |
|---|---|
| Route table | 29 routes: 25 need a user token, 3 need the scheduler's token, and only `/health` is public. A test fails if a new route is added without one of them. |
| Bad tokens | 21 kinds, each on every one of the 25 user routes, all answer 401: no header, empty, wrong scheme, junk, unsigned (`alg: none`), signed with the public certificate as a secret (key confusion), signed by another key with the right and the wrong key id, no key id, expired, issued in the future, other project's audience and issuer, wrong issuer, no / empty / over-long subject, a custom token, a scheduler token, a null byte. |
| Session state | A valid token for a revoked session, a disabled user or a deleted user is a 401. |
| Look-alike identity | `X-User-Id`, `X-Forwarded-User`, cookies, a token in the query string and the like are ignored; the caller is only the verified subject. |
| Scheduler routes | 11 kinds of caller (no token, junk, unsigned, another key, a worker's token, wrong audience, expired, another service account, unverified email, no email, wrong issuer) are refused on all 3 routes; the real scheduler is let in; with the scheduler not configured they answer 503. Live: all 3 answer 401. |
| Cross-user data | Contracts are read from the caller's own `users/{uid}` path, IDs are pattern-checked (20 letters or digits), evidence ownership is checked by re-hashing the caller's uid. |
| Rules | 34 new cases: collection-group queries on 14 collection names, listing other users' data, cross-user and owner edits of notifications, profile updates that add or change protected fields, Storage list and delete. All deny correctly. |
| Uploads | The server identifies the file by its bytes (not the claimed type or name); evidence files are stored under generated names; size is cut off before the body is read. |
| CORS | Exact origins only: the real site is allowed, an unknown origin gets 400, no credentials mode. |
| Secrets | Tree (708 files), full git history (207 commits, 101,306 added lines) and the built app: nothing. Of the 4 secrets in Secret Manager, 3 are readable only by the backend's service account and the 4th (`recaptcha-secret-key`, for App Check) has no grants yet. Production env vars hold names and secret references, no values. |
| Web code | No `dangerouslySetInnerHTML`, `innerHTML`, `eval` or `document.write`; the print window uses `textContent`. |
| Prompt injection | Worker text put into prompts is fenced and told to be treated as data; answers are schema-bound. |
| CI | No `pull_request_target`, no untrusted event data in scripts, keyless OIDC deploys, `.dockerignore` keeps env files out of images. |
| Sign-in settings (live, read-only) | Anonymous and email sign-in off; phone on, SMS allowed only to SG, MY, HK, JP, KR, IN, AU, PH, ID, NP, BD. |
| Dependencies | `pip-audit`: no known vulnerabilities. `pnpm audit`: 2 moderate (F-11). |

## Findings in detail

### F-01 — The browser API key has no website restriction (Medium, open)

The Firebase "Browser key" is visible in the site's JavaScript, which is normal. Its safety rests on two restrictions: which APIs it may call, and from which websites. It has the first (27 APIs) and not the second. Anyone who copies it can call those APIs from their own script. Billing is now on, so abuse can cost money. Of the 27 APIs, 15 are enabled in the project, among them Identity Toolkit (sign-up and phone verification) and Firestore. The Gemini API is enabled but **not** in the key's list, so the public key cannot run Gemini on your account.

Fix (you run it; it changes production):

```bash
gcloud services api-keys update 08bf3f03-62a7-4220-a191-1e5ee3d2f79f --project nomadfinance-prod --allowed-referrers="https://nomadfinance-prod.web.app/*,https://nomadfinance-prod.firebaseapp.com/*,http://localhost:5173/*"
```

Then, in a second command, keep only the APIs the app uses (the app uses sign-in, token refresh, Firestore, push registration and installations; App Check only when it is turned on):

```bash
gcloud services api-keys update 08bf3f03-62a7-4220-a191-1e5ee3d2f79f --project nomadfinance-prod --api-target=service=identitytoolkit.googleapis.com --api-target=service=securetoken.googleapis.com --api-target=service=firestore.googleapis.com --api-target=service=firebaseinstallations.googleapis.com --api-target=service=fcmregistrations.googleapis.com --api-target=service=firebase.googleapis.com --api-target=service=firebaseappcheck.googleapis.com
```

Afterwards test sign-in (phone and Google) and the dashboard on the live site. If something breaks, remove the restriction with `--clear-restrictions` and tell me which call failed. Check the localhost entry is what you want for a deployed key: it lets local development use the production key.

### F-02 — No security headers on the site (Medium, diff for your OK)

Live: the site sends only `Strict-Transport-Security`. Without the others a page can be framed by another site (clickjacking on the sign-in or report form), a browser may guess a file's type, and a script injected by a future bug would face no limit.

A policy was tested **locally** against the real app, in enforcing mode, across every signed-in page, the map, the charts, a language switch and the signed-out pages: **0 violations**, and framing the site from another origin is refused. The sign-in services (Google popup, reCAPTCHA, Firebase Auth's frame, push, analytics) cannot be exercised locally (the emulator replaces them), so their addresses come from Firebase's documentation. For that reason the policy is proposed in **report-only** mode first: it blocks nothing and the browser console shows anything it would have blocked.

Proposed change to `frontend/firebase.json`, replacing the first entry of `hosting.headers`:

```json
{
  "source": "**",
  "headers": [
    { "key": "Cache-Control", "value": "no-cache" },
    { "key": "X-Content-Type-Options", "value": "nosniff" },
    { "key": "Referrer-Policy", "value": "strict-origin-when-cross-origin" },
    { "key": "X-Frame-Options", "value": "DENY" },
    { "key": "Permissions-Policy", "value": "microphone=(), geolocation=(), payment=()" },
    {
      "key": "Content-Security-Policy-Report-Only",
      "value": "default-src 'self'; script-src 'self' 'sha256-j6RCfXnC1snSVort/DOXZP3rnbJGBCTr5tvNW7ZPgIM=' https://apis.google.com https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/ https://www.googletagmanager.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https://tile.openstreetmap.org https://*.googleusercontent.com https://www.google-analytics.com; font-src 'self' data:; connect-src 'self' https://nomadfinance-api-azewstzfaa-el.a.run.app https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://firestore.googleapis.com https://firebaseinstallations.googleapis.com https://fcmregistrations.googleapis.com https://fcm.googleapis.com https://firebase.googleapis.com https://www.google.com/recaptcha/ https://*.google-analytics.com https://*.analytics.google.com https://www.googletagmanager.com; frame-src 'self' https://nomadfinance-prod.firebaseapp.com https://www.google.com/recaptcha/ https://recaptcha.google.com/recaptcha/; worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    }
  ]
}
```

Notes:
- `'sha256-…'` is the hash of the small inline theme script in `index.html`. If that script is ever edited, recompute it: the browser's console error shows the new hash, or hash the script text with SHA-256 and Base64.
- `style-src 'unsafe-inline'` is needed for the map and some components that set styles directly. The scripts, which matter most, have no `unsafe-inline`.
- `frame-ancestors` is not honoured in report-only mode, so `X-Frame-Options: DENY` carries the framing protection now.
- `camera` is left out of `Permissions-Policy` on purpose: the photo pickers use the phone's own camera app (`capture`), which was not tested against it.
- After a day with no console reports on the live site, change the key name to `Content-Security-Policy` to enforce.

### F-03 — A malformed push token stopped alerts for everyone (Medium, fixed)

The profile rules cap `fcm_tokens` at 5 entries but accept anything inside them. A worker could save a non-string (for instance a map). When the Radar alert job reached that worker, `firebase_admin` raised `ValueError`, nothing caught it, and the alert was not delivered to any worker after them in the loop; the alert was not marked as notified either, so the next run repeated it. Proof: three tests failed against the old code (the real `firebase_admin` validation). The file's own docstring already promised "one broken token must not stop the rest of the fan-out".

Fix in `backend/app/services/radar/notify.py`: only strings of 1 to 1,024 characters (at most 5) are used, and a push failure for one worker is logged by type and skipped.

### F-04 — A forged token could use up another worker's budget (Medium, fixed)

The rate limiter chooses whose counter to use from the token's `sub` **before** the token is verified (so refused requests cost little). Anyone who knew a worker's uid could send forged tokens naming them and get every request from that worker answered 429. Proof: 20 forged requests from one address got the victim's own next request, from their own address, refused.

Fix in `backend/app/core/rate_limit.py`: the counter key is now the user **and** the caller's address. Forged requests land in the forger's own bucket. Many workers on one address still do not block each other, and one worker has one budget from one address.

### F-05 — An emulator setting in production would switch off signature checks (Low-Medium, fixed)

Read from the `firebase_admin` source: when `FIREBASE_AUTH_EMULATOR_HOST` is set in the process, token signatures are not checked at all and the payload is trusted. Production does not set it (confirmed from the service's variable names), but nothing in the code prevented a future deploy from doing so. `backend/app/config.py` now refuses to start when `APP_ENV` is not `local` and any of the three emulator variables (`FIREBASE_AUTH_`, `FIRESTORE_`, `FIREBASE_STORAGE_EMULATOR_HOST`) is set. Local development is unchanged.

### F-06 — Two token failures answered 500 instead of 401 (Low, fixed)

Both failed closed (no access was given), but a 500 is noisy and tells a client nothing. After account deletion the old token stays valid for up to an hour; the user lookup raised `UserNotFoundError` on all 25 user routes. A scheduler token with the wrong issuer raised `GoogleAuthError`. Both now answer 401 (`backend/app/core/security.py`).

### F-07 — The API's endpoint list was public (Low, fixed)

`/docs`, `/redoc` and `/openapi.json` listed every endpoint and field to anyone (67 hits on `/docs` in the log; some may have been scanners). They are now served only when `APP_ENV=local` (`backend/app/main.py`); a deployed API answers 404. Run the backend locally to browse them (`docs/api/endpoints.md` says so).

### F-08 — Links built from server data (Low, fixed)

Complaint channels and the survey source went straight into `href`. They come from curated data, not from a worker, but a `javascript:` address in that data would run inside the app. `frontend/src/utils/safeUrl.ts` allows only `http` and `https`; used in `ComplaintPreview` and `RemittanceCompare`.

### F-09 — Income amount in the logs (Low, fixed)

`contract_income_logged` wrote the amount next to the contract id. Removed (`contract_to_fib.py`); the other log lines carry no personal figures.

### F-10 — List contents in the profile rules (Low, verified diff for your OK)

Confirmed on the emulator: the rules accept 5 maps or a 900 KB string as push tokens, and any text as a corridor id. With F-03 fixed this only affects the worker's own document (its size and its own screens), not other workers. Proposed change to `frontend/firestore.rules`, tested in memory against the emulator (every real case accepted; 5 maps, a map in slot 3, a 900 KB string, an empty token and unknown corridors rejected):

```diff
+    // A push token is a short string. Rules cannot loop, so each of the (at most 5) slots is checked.
+    function tokenOk(list, i) {
+      return list.size() <= i || (list[i] is string && list[i].size() > 0 && list[i].size() <= 1024);
+    }
+    function validTokens(list) {
+      return list is list && list.size() <= 5
+        && tokenOk(list, 0) && tokenOk(list, 1) && tokenOk(list, 2) && tokenOk(list, 3) && tokenOk(list, 4);
+    }
+
     function validNotificationPrefs(prefs) {
...
         && (!('radar_corridors' in prefs)
-            || (prefs.radar_corridors is list && prefs.radar_corridors.size() <= 6);
+            || (prefs.radar_corridors is list && prefs.radar_corridors.size() <= 6
+                && prefs.radar_corridors.hasOnly(['SG-PH', 'SG-IN', 'AU-IN', 'MY-ID', 'JP-PH', 'AU-PH'])));
...
-        && (!('fcm_tokens' in data)
-            || (data.fcm_tokens is list && data.fcm_tokens.size() <= 5));
+        && (!('fcm_tokens' in data) || validTokens(data.fcm_tokens));
```

If approved, the new cases go into `tests/rules/audit.rules.test.ts` and the rules deploy through the existing workflow.

### F-11 — `react-router` advisories (Low, open)

`pnpm audit` reports two moderate issues in `react-router` 6.30.6, fixed only in v7.18: an open redirect through a backslash in `Link`/`navigate`, and an issue in server-side hydration. The app has no server rendering, and the only value passed to `navigate` that is not a fixed path is the in-app history state, which a link from another site cannot set. Not reachable, but the library should move to v7 (changes `package.json` and the lock file: shared files, D-92).

### F-12 — Rate limit limits (Low, documented)

Measured with the real defaults: the first 429 comes at request **61** (general) and **11** (Gemini endpoints), with `Retry-After: 60`; an anonymous caller is cut off at 61 too. Limits:

1. The counts live in each server instance's memory. With `max-instances 2` the real limit can be up to twice as high, and a restart resets it.
2. A spray of **made-up** user ids from one address is not limited: 1,000 token-shaped requests with a different uid each all passed the limiter (all answered 401, in about 3 s on this PC), while the same flood with no token was cut off after 60. The requests end in 401 and never reach Gemini, so the cost is server time and log lines, not money. A per-address ceiling would stop it, but a high enough one for shared dormitory addresses is a judgement call, so none was added. The real defences are Cloud Armor in front of the service, and App Check (F-16).

### F-13 — Google Cloud access (Low, you run commands)

Read from the live project:

- `roles/editor` is held by the **default Compute Engine service account**. The API runs as its own account (`nomadfinance-backend`), so nothing needs this. Remove it: `gcloud projects remove-iam-policy-binding nomadfinance-prod --member="serviceAccount:54982290462-compute@developer.gserviceaccount.com" --role="roles/editor"`. Check first that nothing else (Cloud Build, a function) runs as it.
- 4 people hold `roles/owner`. Fine for a hackathon team; for later, Editor plus specific roles is safer.
- The backend account holds `roles/firebaseauth.admin` for the whole project (needed to delete a user, but it can change any user). A custom role with only user deletion would be tighter.
- The Storage bucket does not block public access (nothing is public today: no `allUsers` binding). Enforce it: `gcloud storage buckets update gs://nomadfinance-prod.firebasestorage.app --public-access-prevention`.
- The API is public to all callers (`allUsers` invoker): by design, since the app checks the Firebase token itself.
- Three of the four secrets are each readable only by the backend account; the fourth (`recaptcha-secret-key`) has no grants and is unused until App Check is turned on. The deploy accounts have no keys.

### F-14 — Test phone numbers (Info, confirm)

The live project still lists **3 test phone numbers**. D-31 says their shared code was changed or they were removed on 2026-09-27; they exist, so the code was changed. A test number signs in with a fixed code and bypasses SMS. Delete them before the demo on 2026-10-18 (Authentication → Sign-in method → Phone → Phone numbers for testing), or confirm the code is not written down anywhere public.

### F-15 — CI (Info, diff for your OK)

There is no secret scan in CI, and actions are pinned by version tag. A secret scan on every pull request, which would also catch a key in a **new** commit, is proposed for `.github/workflows/security-scan.yml`; pin the action to a commit when adding it:

```yaml
  secrets:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0 # the whole history, not only the new commits
      - uses: trufflesecurity/trufflehog@<pin to a release commit>
        with:
          extra_args: --only-verified
```

(`gitleaks-action` needs a paid licence for organisation repositories, so it is not suggested.)

## Rate limiting — measured

| Check | Result |
|---|---|
| General budget, one worker (default `60/minute`) | first 429 at request 61, `Retry-After: 60`, `X-RateLimit-Limit: 60` |
| Gemini endpoint, one worker (default `10/minute`) | first 429 at request 11 |
| Anonymous caller, one address | first 429 at request 61 |
| Counted per user and address, not per address alone | tests: a shared address does not block workers; a forger cannot spend a victim's budget |
| 429 carries CORS headers and `Retry-After` | existing test, passes |
| `/api/v1/internal/*` and `/health` never limited | existing tests, pass |
| Oversized upload | declared length refused before the body is read (413); a streamed body is cut off |
| Made-up user ids from one address | not limited (F-12) |

## Files

| File | Change |
|---|---|
| `backend/app/services/radar/notify.py` | Only usable push tokens; a push failure skips that worker (F-03) |
| `backend/app/core/rate_limit.py` | Counter key is user plus address (F-04) |
| `backend/app/config.py` | Refuse to start with an emulator variable outside local (F-05) |
| `backend/app/core/security.py` | Deleted user and wrong-issuer scheduler token answer 401 (F-06) |
| `backend/app/main.py` | API docs only in local (F-07) |
| `backend/app/services/cross_pillar/contract_to_fib.py` | Income amount out of the log (F-09) |
| `frontend/src/utils/safeUrl.ts`, `.test.ts` (new) | Only http(s) links (F-08) |
| `frontend/src/components/contract/ComplaintPreview.tsx`, `src/pages/remittance/RemittanceCompare.tsx` | Use `safeWebUrl` |
| `backend/tests/integration/api/test_auth_matrix.py` (new) | 25 tests: route table, 21 bad tokens on every route, revoked/disabled/deleted, look-alike identity, positive control, scheduler routes |
| `backend/tests/integration/api/test_rate_limit_verification.py` (new) | 5 tests |
| `backend/tests/integration/api/test_docs_exposure.py` (new) | 10 tests |
| `backend/tests/unit/test_config.py`, `tests/unit/services/test_radar_notify.py` | 8 and 3 new tests |
| `frontend/tests/rules/audit.rules.test.ts` (new) | 34 rules cases |
| `docs/SECURITY.md`, `docs/api/endpoints.md`, `backend/.env.example`, `docs/deferred-items.md` | Documentation |

No shared file (`package.json`, lock files, `firebase.json`, the rules files, Dockerfile, `tsconfig*`, workflows) was edited. Proposed diffs for them are above.

## All commands, in order

From `backend/`:

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m black --check -l 100 app tests
.venv/Scripts/python.exe -m ruff check app tests
.venv/Scripts/python.exe -m mypy --strict app/services app/core app/main.py app/config.py
```

Only the new security tests: `.venv/Scripts/python.exe -m pytest tests/integration/api/test_auth_matrix.py tests/integration/api/test_rate_limit_verification.py tests/integration/api/test_docs_exposure.py tests/unit/test_config.py -q`

From `frontend/` (`pnpm.cmd` in PowerShell if `pnpm` is blocked):

```bash
pnpm exec tsc --noEmit
pnpm exec eslint src tests
pnpm exec prettier --check --end-of-line auto src tests
pnpm exec vitest run src
pnpm run test:rules
```

If `test:rules` says "port taken", a Java process from the previous run is still alive (D-34): stop whatever listens on 8085, 9150 and 9199, then re-run.

Read-only checks on the live project (any shell, signed in to `gcloud`):

```bash
gcloud services api-keys list --project nomadfinance-prod
gcloud projects get-iam-policy nomadfinance-prod
gcloud secrets get-iam-policy gemini-api-key --project nomadfinance-prod
gcloud run services describe nomadfinance-api --region asia-south1 --project nomadfinance-prod
curl -sI https://nomadfinance-prod.web.app/
```

## Verified results (2026-10-04)

- Backend: **1,011 tests pass**, 66 skipped (they need the emulator or a live key); black, ruff and `mypy --strict` clean.
- Frontend: **222 tests pass**; types, lint and format clean; the build passes. Rules: **134 pass** on the emulators.
- The new tests were checked by breaking the thing they guard, then restoring it: signature check removed → 7 auth tests fail; revocation check removed → the 3 revocation tests fail; a leaky collection-group rule added to a copy of the rules → exactly the `income` cases fail; F-03 and F-04 tests fail on the old code and pass on the new.
- Secret scans: tracked tree (708 files; 21 hits, all resource names, placeholders or fake test strings), git history (101,306 added lines; 6 pattern hits, all browser-storage key names, an i18n key table or fake test strings), built app (one Google API key, the public Firebase web key; no server key, no emulator address). The history scanner was checked against known sample secrets and caught every format after one pattern was widened.
- Candidate CSP: 0 violations under enforcement across 8 screens, a language switch and the signed-out pages.
- Not run: a real iPhone or Android phone, the live sign-in flows under the new headers, load or denial-of-service tests, penetration testing by a third party.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Backend refuses to start: "FIREBASE_AUTH_EMULATOR_HOST is set but APP_ENV is prod" | An emulator variable is set in a deployed environment | Remove the variable. This is the guard doing its job |
| `/docs` gives 404 on the deployed API | Docs are local-only now | Run the backend locally |
| A worker gets 429 straight after switching Wi-Fi to mobile data | The budget is per user and address, so it is a new bucket; it should not get more 429s than before | Not a problem; report if it persists |
| `test:rules` "port taken" | Left-over emulator Java process (D-34) | Stop it, run again |
| After the CSP is enforced, a sign-in step fails | An address the policy does not list | The report-only phase is there to find it; read the console message and add the address |

## Definition of Done

Security audit tasks have no entry in the tracker's list, so the nearest ones are used:

**Bug Fix**
- [x] Root cause identified (F-03 to F-09, see above)
- [x] Regression tests added, each failing without its fix
- [x] `fix()` or `chore()` commit type; reference `NF-P4-004` in the commit

**Backend Endpoint** (for the changed behaviour)
- [x] Token verification and error handling: 401 for every bad token, now tested
- [x] Rate limiting applied and verified
- [x] OpenAPI sanity: docs now local-only; `docs/api/endpoints.md` updated

**Documentation**
- [x] Markdown, in `/docs`; no AI attribution
- [ ] Reviewed by a teammate (yours)

## For teammates

- **Pranjal** (the tracker's owner): F-01, F-13 and F-14 are Google Cloud actions only someone with owner access can do (D-87 to D-89). F-02, F-10 and F-15 are diffs waiting for the team's OK (shared files).
- **Anyone adding an API endpoint:** use `Depends(get_current_user)`; if it calls Gemini add `Depends(limit_ai_calls)` and list it in `AI_LIMITED` in `test_auth_matrix.py`. The test tells you.
- **Anyone letting the browser write to Firestore:** the rules must check the shape of every field, including what is inside lists. The backend must not trust that data.
- **Anyone putting a server-supplied address in a link:** use `safeWebUrl`.

## Commit and PR

Branch: `fix/security-audit` (already checked out).

```bash
git add backend frontend docs
git status
```

```bash
git commit -m "fix(security): harden alerts, rate limits, token checks and docs exposure" -m "Refs: NF-P4-004"
```

PR title: `fix(security): security audit — auth bypass tests, rules tests, alert and rate-limit fixes (NF-P4-004)`

## Not covered here

- Anything that changes production settings (F-01, F-13, F-14): yours to run, with the commands above.
- The shared-file changes: headers and CSP (D-90), secret scan job (D-91), `react-router` v7 (D-92), tighter profile rules (D-93).
- App Check and reCAPTCHA Enterprise (NF-P3-025, D-32), Cloud Armor, a third-party penetration test, and real-device testing (D-72).
