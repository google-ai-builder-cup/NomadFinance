# NF-P1-022 — User Onboarding Flow

## Summary

After their first sign-in, users answer **four questions, one per screen**: preferred language, the country they work in (host), the country they send money to (home), and their kind of work. The answers are saved to Firestore at `users/{uid}` straight from the browser (Firebase Web SDK); the security rules from NF-P1-014 are the validation: only the owner, only the allowed values, `serverTimestamp()` for `created_at` / `updated_at` / `onboarding_completed_at`, and `schema_version: 1`. A new layout route, `RequireOnboarding`, sits between `ProtectedRoute` and the app shell: a signed-in user without `onboarding_completed_at` is sent to `/onboarding`, and a user who has finished is never shown onboarding again. Language comes first and switches the UI immediately, so the other questions are already in the worker's language; country names come from the browser's own localized data (`Intl.DisplayNames`), and job types are translated in all six language files. **Language follows a clear rule** (fixed after first testing, when the sign-in page kept the last user's language): signed out, the app **always opens in English** (phones are often shared); the new selector on the sign-in page changes the language for that visit only, nothing is stored; signed in, it uses the profile's `preferred_language` on every device. The header selector is only a quick switch for the current tab session and never changes `preferred_language`, which also drives reports, notifications and SMS; that is set in onboarding and (from NF-P1-023) on the profile page. `<html lang>` and Firebase's SMS/reCAPTCHA language follow the UI language. The backend is untouched: saving through an API endpoint waits for CORS (NF-P1-027), and the backend can read the profile with the Admin SDK when a later task needs it.

## Files

| File | Purpose |
|---|---|
| `frontend/src/pages/Onboarding.tsx` | The 4-step form: progress bar, native radio buttons as large tap targets, back/next, save, errors |
| `frontend/src/components/common/RequireOnboarding.tsx` | Gate: spinner while loading, retry on load error, redirect to `/onboarding` if not finished |
| `frontend/src/router.tsx` | `/onboarding` under `ProtectedRoute`; all app pages under `RequireOnboarding` |
| `frontend/src/services/userService.ts` | `getUserProfile`, `isOnboarded`, `completeOnboarding` (create vs update shape required by the rules) |
| `frontend/src/hooks/useUser.ts` | `useUserProfile()` (TanStack Query, cached per uid), `useCompleteOnboarding()` |
| `frontend/src/types/user.ts`, `types/enums.ts` | `UserProfile`, `OnboardingAnswers`; allowed countries, job types, languages (must match `firestore.rules`) |
| `frontend/src/utils/format.ts` | `countryName(code, language)` via `Intl.DisplayNames` (short style: "Hong Kong") |
| `frontend/src/lib/firebase.ts`, `vite-env.d.ts`, `.env.emulator` | `db` (Firestore); Firestore emulator on 8085 in emulator mode |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `onboarding.*` and `common.retry` in all six languages |
| `frontend/src/components/common/LanguageSync.tsx` | Applies the right language (English signed out, profile or session switch signed in); sets `<html lang>` and `auth.languageCode` |
| `frontend/src/components/layout/LanguageSelector.tsx` | Signed in: quick switch for this tab session (`sessionStorage`), profile untouched. Signed out: this visit only, nothing stored. |
| `frontend/src/lib/languages.ts`, `lib/i18n.ts` | i18next always starts in English (no browser detection, nothing cached); session quick-switch helpers |
| `frontend/src/pages/SignIn.tsx`, `src/main.tsx` | Language selector on the sign-in page; `LanguageSync` mounted once |
| `frontend/src/services/userService.ts`, `hooks/useUser.ts` | `updatePreferredLanguage` / `useUpdatePreferredLanguage()`, for the profile page (NF-P1-023) |

## Which language is used when

| Situation | Language |
|---|---|
| Signed out (sign-in page) | **Always English** when the page opens |
| Signed out, a language picked with the sign-in page selector | That language until reload or sign-in; nothing stored |
| Signed in, onboarding not finished | Whatever is showing; step 1 of onboarding sets it |
| Signed in, profile exists | The profile's `preferred_language`, on every device and after reload |
| Signed in, header selector changed | Applied at once for this tab session, also after a reload; `preferred_language` is **not** changed |
| After sign-out | English; the quick switch is forgotten |
| Next sign-in | The profile's `preferred_language` again |

## Flow

```
/sign-in ──signed in──► any app URL
                         └─ ProtectedRoute (signed in?)
                              └─ RequireOnboarding
                                   ├─ loading profile   → spinner
                                   ├─ load failed        → "couldn't load" + Try again
                                   ├─ no onboarding_completed_at → /onboarding
                                   └─ done               → AppShell → page

/onboarding
  step 1 language   → i18n.changeLanguage() at once
  step 2 host country (SG MY HK JP KR AU)
  step 3 home country (PH IN ID NP BD)
  step 4 job type   (7 values)
  Finish → no profile yet:  setDoc(users/{uid}, answers + created_at/updated_at/onboarding_completed_at = serverTimestamp(), schema_version 1)
           profile exists:  updateDoc(users/{uid}, answers + updated_at/onboarding_completed_at = serverTimestamp())
         → re-read profile → /dashboard
  Already onboarded → /dashboard
```

## All commands, in order

From `frontend/` (pnpm 10; NVM for Windows users use `pnpm.cmd`, see the NF-P1-009 runbook step 0).

### 1. Checks

```bash
pnpm lint
pnpm build
pnpm test:rules
```

Expected: lint clean, build succeeds, `94 passed` (the rules this flow relies on).

### 2. Try it on the emulators (no real accounts)

Terminal 1:

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

Terminal 2:

```bash
pnpm dev --mode emulator
```

Open `http://localhost:5173/sign-in`, sign in with any number (the SMS code is printed in terminal 1), then:

1. You land on `/onboarding`, "Step 1 of 4", with your current language pre-selected.
2. Choose हिन्दी: the page switches to Hindi at once. Next stays disabled until you choose an answer.
3. Answer the other three, then **Finish** (पूरा करें) → dashboard.
4. See the saved document: Emulator UI `http://127.0.0.1:4000/firestore` → `users/<uid>`, or

   **bash**
   ```bash
   curl -s -H "Authorization: Bearer owner" "http://127.0.0.1:8085/v1/projects/demo-nomadfinance/databases/(default)/documents/users"
   ```

   **PowerShell**
   ```powershell
   curl.exe -s -H "Authorization: Bearer owner" "http://127.0.0.1:8085/v1/projects/demo-nomadfinance/databases/(default)/documents/users"
   ```

5. Reload `/dashboard` → stays. Open `/onboarding` → back to `/dashboard`. Sign out and in again → straight to `/dashboard`.

The emulator keeps data only while it runs; restart it to test the new-user path again.

### 3. Try it on real Firebase

```bash
pnpm dev
```

Open `http://localhost:5173/sign-in`, sign in with a test phone number (`+61 491 570 156/157/158`, code in the team chat) or Google. A new account goes through onboarding; the profile appears in the Firebase console → Firestore → `users`. To run onboarding again for a test account, delete its `users/<uid>` document in the console.

## Verified results (2026-09-25)

| Check | Result |
|---|---|
| `pnpm lint` / `tsc -b` | clean / clean |
| Prettier on changed files | pass |
| All six language files | identical key sets |
| Emulators (Auth + Firestore, real rules): new user after sign-in | → `/onboarding`, step 1 of 4, focus on the question |
| Choose Hindi | whole page in Hindi at once, country names in Hindi, job types in Hindi |
| Next without an answer | disabled |
| Finish | `users/<uid>` = `preferred_language hi, host_country SG, home_country IN, job_type domestic_worker, schema_version 1`, three server timestamps; → dashboard in Hindi |
| Reload / visit `/onboarding` again / sign out + in | dashboard / redirected to dashboard / straight to dashboard |
| 375 px wide | one column, 50 px tap targets, no horizontal scroll, buttons on screen |
| Language, emulator: old stored values (`nomadfinance.language = hi`, `nomadfinance.deviceLanguage = tl`) | Sign-in page in English (no longer read) |
| Sign-in page selector → Tagalog, then reload | Tagalog for that visit, nothing stored; reload → English |
| New user picks Hindi in onboarding → dashboard → **sign out** | Dashboard Hindi; **sign-in page English** (device language still `en`) |
| Sign in again | Hindi (from the profile) |
| Onboarding in Nepali → header → English | UI English; profile still `ne`, not written (`updated_at` = `created_at`) |
| Reload | Still English (session switch) |
| Sign out → sign in | Sign-in page English → dashboard **Nepali** (saved preference) |
| **Real Firebase** (test number `+61 491 570 158`, done by Devam) | production `users/nlxlH6SRrRPBir4qjODk9SEdW3r2` = `hi, JP, IN, other, schema_version 1`, server timestamps, accepted by the production rules |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Stuck on "Saving…" | Offline: Firestore keeps the write and finishes it when the connection returns. The page moves on by itself. |
| "We couldn't load your profile" | Profile read failed (offline or permission). **Try again**. With the emulator: is the Firestore emulator running on 8085? |
| "We couldn't save your answers" | Firestore refused the write. In development the console shows the Firebase error. Usually a value outside `types/enums.ts`, which must match `frontend/firestore.rules`. |
| Onboarding loops back after Finish | The profile re-read didn't see `onboarding_completed_at`. Check the document in Firestore. |
| Want to redo onboarding for a test account | Delete `users/<uid>` in the Firebase console (or restart the emulator). |
| Country names show as codes ("SG") | The browser has no locale data for that language; rare, harmless. |
| Sign-in page not in English | An old version is still running (D-42): close the tab and hard-reload. The current version always opens the sign-in page in English. |
| Signed in, the header language is gone after closing the tab or signing out | Expected: the header selector is a quick switch. Change `preferred_language` in onboarding or the profile page (NF-P1-023). |

## Deploy the frontend

Only the frontend changed (no backend, rules or Scheduler change). After the PR is merged, from `frontend/` on the updated `main`, with the real `frontend/.env.local`:

```bash
git checkout main
git pull
pnpm install
pnpm build
firebase deploy --only hosting --project nomadfinance-prod
```

(NVM for Windows: `pnpm.cmd` instead of `pnpm`.) Expected: `✔ Deploy complete!` and the hosting URL. Then check on `https://nomadfinance-prod.web.app`:

1. `/sign-in` is in English and has the language selector.
2. Sign in with a test number that has no profile (or delete its `users/<uid>` in the console first): onboarding appears; finish it.
3. Sign out: the sign-in page is English again. Sign in: your chosen language comes back.

The installed PWA may keep the previous version until it's closed and reopened once (service worker update).

## Commit and PR for this task

Branch: `feature/frontend-onboarding`. From the repo root:

```bash
git add frontend docs
git status
```

```bash
git commit -m "feat(onboarding): add post-sign-in onboarding flow saved to Firestore" -m "Refs: NF-P1-022"
```

PR title: `feat(onboarding): 4-step onboarding saved to users/{uid} with route gate (NF-P1-022)`

## Not covered here

- Edit profile, change language later, delete account: NF-P1-023
- Backend profile API (`/api/v1/users/me`): after CORS (NF-P1-027), when a feature needs it
- Notification preferences and push tokens: NF-P3-004 / NF-P3-009
