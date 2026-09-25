# NF-P1-009 — Frontend Firebase Auth (Google + Phone OTP)

## Summary

Users sign in on `/sign-in` with **Google** or with their **mobile number and a 6-digit SMS code**. The Firebase Web SDK (`firebase@12.19.0`) is set up once in `src/lib/firebase.ts` from `VITE_FIREBASE_*` env vars and fails at startup with a clear message if one is missing. `AuthProvider` (in `src/hooks/useAuth.ts`) listens to Firebase and gives every component `useAuth()` → `{ user, loading }`. `ProtectedRoute` is a layout route: it shows a spinner while Firebase restores a saved session, sends signed-out users to `/sign-in` and brings them back to the page they wanted afterwards. Google sign-in opens a popup and falls back to a full-page redirect when the popup is blocked (in-app browsers); redirect errors are shown on the sign-in page. Phone numbers can be typed the local way (`012-345 6789`): the dial code picker covers the 6 host and 5 home countries, and the leading trunk `0`, spaces and dashes are removed to build the international (E.164) number. `getIdToken()` returns the token the backend's `get_current_user` (NF-P1-005) verifies. For local testing the **Firebase Auth Emulator** replaces real Google accounts and real SMS, so no billing or phone is needed. User-facing text goes through `t()` keys in `src/i18n/en.json`; `t()` is a stand-in until react-i18next lands in NF-P1-011.

## Files

| File | Purpose |
|---|---|
| `frontend/src/lib/firebase.ts` | Firebase app + `auth`; requires the 4 `VITE_FIREBASE_*` vars; connects to the emulator when `VITE_USE_FIREBASE_EMULATOR=true` |
| `frontend/src/services/authService.ts` | `signInWithGoogle` (popup → redirect fallback), `redirectSignInErrorKey`, `createRecaptchaVerifier`, `disposeRecaptchaVerifier`, `sendPhoneCode`, `confirmPhoneCode`, `signOut`, `getIdToken`, `authErrorKey` (Firebase error → i18n key) |
| `frontend/src/hooks/useAuth.ts` | `AuthProvider` (default export) + `useAuth()` |
| `frontend/src/components/common/ProtectedRoute.tsx` | Guard for signed-in pages (layout route with `<Outlet />`) |
| `frontend/src/components/common/LoadingSpinner.tsx` | Accessible spinner (`role="status"`), inline or full screen |
| `frontend/src/pages/SignIn.tsx` | Google button, phone number step, code step, resend, change number, error messages |
| `frontend/src/pages/Dashboard.tsx` | **Placeholder** ("signed in as …", sign out) so the guard can be tested; NF-P1-010 replaces it |
| `frontend/src/router.tsx`, `src/main.tsx` | `/sign-in`, protected `/dashboard`; `AuthProvider` around the router |
| `frontend/src/utils/constants.ts` | `PHONE_DIAL_CODES` (SG, MY, HK, JP, KR, AU, PH, IN, ID, NP, BD) |
| `frontend/src/utils/validators.ts` | `toE164(dialCode, localNumber)` |
| `frontend/src/lib/i18n.ts`, `src/hooks/useI18n.ts`, `src/i18n/en.json` | `t()` stand-in and the `auth.*` / `dashboard.*` / `common.*` keys |
| `frontend/src/vite-env.d.ts` | Types for the `VITE_*` env vars |
| `frontend/.env.example` | Placeholder names for the real config |
| `frontend/.env.emulator` | Demo-only values for `pnpm dev --mode emulator` (no real keys; the emulator accepts any config for a `demo-` project) |
| `frontend/firebase.json` | New `"emulators"` section (auth on 9099, UI on 4000); `"hosting"` unchanged |
| `frontend/package.json`, `pnpm-lock.yaml` | `firebase@12.19.0` |
| `frontend/README.md` | Sign-in section; blank lines after headings so `format:check` passes |

## Flow

```
main.tsx
  └─ <AuthProvider>                 onAuthStateChanged → { user, loading }
       └─ <RouterProvider>
            ├─ /sign-in  SignIn
            │    ├─ user already signed in → <Navigate to={from ?? "/dashboard"}>
            │    ├─ "Continue with Google" → signInWithPopup
            │    │     └─ auth/popup-blocked → signInWithRedirect → back to /sign-in
            │    │                              (errors: getRedirectResult → message)
            │    └─ phone: dial code + local number → toE164 → fresh invisible reCAPTCHA
            │          → signInWithPhoneNumber → SMS → 6-digit code → confirm
            └─ <ProtectedRoute>
                 ├─ loading      → full-screen spinner (no flash through /sign-in on reload)
                 ├─ no user      → <Navigate to="/sign-in" state={{ from }}>
                 └─ signed in    → <Outlet/> → /dashboard (placeholder)

Backend calls (later tasks): Authorization: Bearer ${await getIdToken()}
```

## All commands, in order

Run from `frontend/` unless a step says otherwise.

### 0. pnpm

If `pnpm --version` fails, either install it once:

```bash
npm install -g pnpm@10
```

or prefix every `pnpm` command below with `npx --yes pnpm@10` (e.g. `npx --yes pnpm@10 install`). Use pnpm **10**: the lockfile is format 9.0.

### 1. Install

```bash
pnpm install
```

Check: `pnpm list firebase` shows `12.19.0`. pnpm 10 prints "Ignored build scripts: @firebase/util, esbuild, protobufjs". That's expected, and the build works without them.

### 2. Checks

```bash
pnpm lint
pnpm build
pnpm format:check
```

Expected: lint prints nothing (0 warnings), build ends with `✓ built in …` (JS bundle about 390 kB, 125 kB of it Firebase Auth), format check passes.

On Windows, `format:check` may list files you never touched (`vite.config.ts`, `package.json`, …). That's git converting line endings to CRLF on checkout, not a style problem. See Troubleshooting.

### 3. Test sign-in locally with the Auth Emulator (no real accounts, no SMS, no billing)

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only auth --project demo-nomadfinance
```

Expected: `✔ All emulators ready!`, Auth on `127.0.0.1:9099`, Emulator UI on `http://127.0.0.1:4000`. Needs Java 11+ (`java -version`). The `demo-` prefix means nothing touches the real project.

Terminal 2, from `frontend/`:

```bash
pnpm dev --mode emulator
```

`--mode emulator` loads `.env.emulator`, which overrides `.env.local`. Open **`http://127.0.0.1:5173/dashboard`** in the browser. Use `127.0.0.1`, not `localhost`, so the Google redirect flow works (see Troubleshooting). A banner "Running in emulator mode" shows at the bottom.

Then check each flow:

1. **Guard:** `/dashboard` redirects to `/sign-in`.
2. **Phone:** choose `MY +60`, type `012-345 6789`, press **Send code**. The screen says `Code sent to +60123456789`. Read the fake SMS code:
   - terminal 1 prints `To verify the phone number +60123456789, use the code 123456.`, or
   - **bash:** `curl -s http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`
   - **PowerShell:** `Invoke-RestMethod http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes | Select-Object -ExpandProperty verificationCodes`
3. Enter `000000` first: "That code is wrong…". Then enter the real code: you land on `/dashboard`, "Signed in as +60123456789".
4. **Reload** `/dashboard`: still signed in, no flash through `/sign-in`.
5. **Sign out**: back to `/sign-in`; `/dashboard` redirects again.
6. **Google:** press **Continue with Google** → emulator account picker → **Add new account** → **Auto-generate user information** → **Sign in with Google.com** → `/dashboard`, "Signed in as <name>".
7. **Validation:** type `12` as the number and press **Send code**: "That mobile number doesn't look right…", with no network call.
8. **Phone width:** DevTools device toolbar at 375 px: no horizontal scroll, buttons full width.

Stop both terminals with `Ctrl+C`.

### 4. Optional: call the backend with a real token

Start the backend against the same emulator, from `backend/`:

**Windows PowerShell**
```powershell
$env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; uvicorn app.main:app --port 8080
```

**bash**
```bash
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 FIREBASE_PROJECT_ID=demo-nomadfinance uvicorn app.main:app --port 8080
```

Get the token after signing in: browser DevTools → Application → IndexedDB → `firebaseLocalStorageDb` → `firebaseLocalStorage` → the `firebase:authUser:…` entry → `value.stsTokenManager.accessToken`. Then:

```bash
curl -s -H "Authorization: Bearer <token>" -F "file=@tests/fixtures/contracts/sample_contract_my_id_photo.jpg" http://127.0.0.1:8080/api/v1/contracts/extract
```

(PowerShell: `curl.exe` instead of `curl`.) Expected: 200 with the Malay contract text. A changed token gives 401.

### 5. Real Firebase

One-time project setup (done 2026-09-25):

| Setting | Where | Value |
|---|---|---|
| Web app | `firebase apps:list --project nomadfinance-prod` | "NomadFinance Web" registered |
| Sign-in methods | Firebase console → Authentication → Sign-in method | Google and Phone enabled |
| Authorized domains | Authentication → Settings → Authorized domains | `localhost`, `nomadfinance-prod.firebaseapp.com`, `nomadfinance-prod.web.app` |
| **SMS region policy** | Authentication → Settings → SMS region policy | **Allow** only: SG, MY, HK, JP, KR, AU, PH, IN, ID, NP, BD. An empty allow list blocks every phone sign-in, test numbers included. |
| Test phone numbers | Sign-in method → Phone → Phone numbers for testing | `+61 491 570 156`, `+61 491 570 157`, `+61 491 570 158` (Australian range reserved for fiction; can't belong to a real person). The shared code is in the team chat, not in the repo. |
| OAuth redirect URI | Google Cloud console → APIs & Services → Credentials → "Web client (auto created by Google Service)" | `https://nomadfinance-prod.web.app/__/auth/handler` |

Each developer, once:

```bash
firebase apps:sdkconfig WEB --project nomadfinance-prod
```

Copy `apiKey` and `appId` into `frontend/.env.local` (start from `.env.example`). Keep `VITE_FIREBASE_AUTH_DOMAIN=nomadfinance-prod.web.app`, `VITE_FIREBASE_PROJECT_ID=nomadfinance-prod` and `VITE_USE_FIREBASE_EMULATOR=false`. These are public identifiers, but `.env.local` stays uncommitted.

Then:

```bash
pnpm dev
```

Open **`http://localhost:5173/sign-in`**. Not `127.0.0.1`: that isn't an authorized domain.

What works where:

| Sign-in | On `localhost` | On `nomadfinance-prod.web.app` |
|---|---|---|
| Phone, **test number** (`AU +61`, `491 570 156`, shared code) | Works | Works |
| Phone, **real number** (real SMS) | **Never works.** Firebase doesn't accept `localhost` as a domain for phone auth and rejects the reCAPTCHA token (`auth/invalid-app-credential`, shown as "The security check didn't pass…"). Test numbers skip that check. | Should work (billing on, region allowed). Needs a deploy to test (deferred item D-29). |
| Google | Works (popup) | Works (popup; redirect fallback through the `web.app` auth domain) |

A reCAPTCHA image challenge ("select all squares with buses") can appear, mostly in automated or unusual browsers. Whoever is testing solves it.

In development builds a failed sign-in also logs `Sign-in failed: FirebaseError: … (auth/<code>)` to the browser console, while the on-screen message stays user-friendly. Look there first when something fails.

## Verified results (2026-09-25; emulator rows at 375 × 812, then real Firebase)

| Check | Result |
|---|---|
| `pnpm lint` / `tsc -b` / `pnpm build` | clean / clean / built, JS 390 kB |
| `prettier --check src` | all files pass |
| `/dashboard` signed out | → `/sign-in`, `from: /dashboard` kept |
| Phone `MY +60` + `012-345 6789` | code sent to `+60123456789` |
| Wrong code `000000` | "That code is wrong. Check the SMS and try again." |
| Right code | → `/dashboard`, "Signed in as +60123456789" |
| Reload `/dashboard` | still signed in |
| Real emulator ID token → backend `/api/v1/contracts/extract` | 200, Malay text extracted; tampered token 401 |
| Sign out | → `/sign-in`; `/dashboard` redirects again |
| Google via redirect (fallback path) | → `/dashboard`, "Signed in as Priya Sharma" |
| Google via popup | Not verifiable in the test browser pane (it opens popups in the same tab). Needs a normal browser: step 3.6 |
| Number `12` | "That mobile number doesn't look right…", no request sent |
| Console errors | none |
| **Real Firebase**, test number `+61 491 570 156` (tester's Chrome and the test pane) | → `/dashboard`, "Signed in as +61491570156" |
| Real Firebase ID token (`RS256`, issuer `securetoken.google.com/nomadfinance-prod`) → backend `/api/v1/contracts/extract`, no emulator | 200, SG contract text extracted |
| Same token with a changed signature byte / with the phone number edited / no token | 401 / 401 / 401 |
| Real number on `localhost` | `auth/invalid-app-credential`, shown as "The security check didn't pass…" (expected, see step 5) |
| Second failed send in a row; two hot reloads after a failed send | Correct message again; no crash (bug found and fixed, see below) |
| Real SMS to a real phone | **Not run yet**: needs the app on a hosted domain (D-29) |
| **Google sign-in on real Firebase** (tester's Chrome, real popup, team Google account) | → `/dashboard`, "Signed in as AIBuilderCup" |

Bugs found during real-Firebase testing, fixed in this task:
- Firebase destroys the reCAPTCHA verifier itself after a failed send. Clearing it again threw `auth/internal-error`: on the next "Send code" (generic error shown) and on page unmount (React Router crash screen). Fixed with `disposeRecaptchaVerifier()`.
- `auth/invalid-app-credential` and `auth/captcha-check-failed` showed the generic message. They now show "The security check didn't pass. Refresh the page and try again."
- The project's SMS region allow list was empty, which blocked all phone sign-in. Set to the 11 countries.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Blank page, console: `Missing VITE_FIREBASE_API_KEY…` | `frontend/.env.local` missing or incomplete (step 5), or use `pnpm dev --mode emulator` (step 3). Also happens on a deployed build made without `.env.local`. |
| `No emulators to start, run firebase init emulators` | Old `firebase.json` without the `"emulators"` section. Pull `main`. |
| Emulator: `Could not spawn java` | Install Java 11+ (JDK 21 works). |
| Google redirect returns to `/sign-in` without signing in (emulator) | App opened at `localhost` while the emulator is on `127.0.0.1`. Browsers treat them as different sites and block the auth iframe's storage. Open `http://127.0.0.1:5173`. |
| Same symptom in production | `VITE_FIREBASE_AUTH_DOMAIN` is `*.firebaseapp.com` instead of `nomadfinance-prod.web.app`, or the redirect URI from step 5 is missing on the OAuth client. |
| `auth/unauthorized-domain` → "This sign-in method isn't available right now" | Real Firebase opened on `127.0.0.1` or a new domain. Use `localhost`, or add the domain under Authentication → Settings → Authorized domains. |
| Phone: "This sign-in method isn't available right now" with real Firebase | Phone provider off, or no billing for SMS (`auth/billing-not-enabled`, D-17). Use test phone numbers (step 5) or the emulator. |
| Phone: "The security check didn't pass…" on `localhost` with a real number | Expected. Firebase doesn't allow phone auth with real numbers on `localhost`. Use a test number locally; real numbers only work on the deployed site. |
| Phone: "This sign-in method isn't available right now" for every number, test numbers included | SMS region policy is "allow list" with no countries. Add the 11 countries (step 5). |
| Stuck on "Sending…" | A reCAPTCHA challenge (image grid) is waiting to be solved. Solve it; if the browser window is hidden, bring it to the front. |
| "Too many attempts…" | Firebase rate limit on SMS / codes. Wait, or use the emulator. |
| `pnpm: command not found` / `CommandNotFound` | Step 0. |
| `pnpm format:check` fails on files you didn't touch (Windows) | `core.autocrlf=true` checks files out with CRLF, and Prettier wants LF. The repo copies are LF. Tracked as deferred item D-21; to check your own files: `pnpm exec prettier --check src`. |
| "Running in emulator mode" banner in production | `VITE_USE_FIREBASE_EMULATOR=true` leaked into the build env. It must be `false` (or unset) in `.env.local`. |

## Commit and PR for this task

Branch: `feature/frontend-firebase-auth`. From the **repo root**:

```bash
git add frontend docs
git status
```

`git status` should list only the files in the table above, this runbook, `docs/deferred-items.md` and the NF-P1-006 runbook update. Never `frontend/.env.local`. `frontend/.env.emulator` is meant to be committed (demo values only).

```bash
git commit -m "feat(frontend): add Firebase Auth with Google and phone sign-in" -m "Refs: NF-P1-009"
```

PR title: `feat(frontend): Firebase Auth with Google + phone OTP and protected routes (NF-P1-009)`

## Not covered here

- App shell, header with sign-out, real dashboard: NF-P1-010
- react-i18next, the other 5 languages, SMS language (`auth.languageCode`): NF-P1-011
- Post-sign-in onboarding (home/host country, job, language) and the Firestore user profile: NF-P1-022
- API client that attaches `getIdToken()` to backend calls: first frontend feature calling the API (NF-P2-009)
- Firestore security rules: NF-P1-014
- Toasts and error boundary: NF-P1-026
