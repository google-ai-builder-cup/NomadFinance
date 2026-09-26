# NF-P1-023 — User Profile / Settings Page

## Summary

A signed-in user can open **Profile** (the person icon in the header, `/profile`) to see and change their details, change their notification choices, and delete their account.

**Every edit is saved to Firestore.** Saving writes straight to the user's own document `users/{uid}` (Firebase Web SDK; the security rules from NF-P1-014 are the validation), then the page reads the document back, so the screen shows what Firestore really holds. The button stays disabled until something changed, only the changed fields are written, and `updated_at` is set by the server on every save.

| Section | What it edits | Firestore fields |
|---|---|---|
| Your account | Shows the name, email or phone number. Read-only: it comes from Google or the phone number and is not copied to Firestore | none |
| Your details | Language, country you work in, country you send money to, kind of work | `preferred_language`, `host_country`, `home_country`, `job_type` |
| Notifications | Warnings about cheating agents and money transfer services, which routes to watch, reminders | `notification_prefs` (`radar_alerts`, `radar_corridors`, `reminders`) |
| Delete my account | Removes the account and all data (see below) | `users/{uid}` tree, Storage files, Auth user |

**Language.** Saving a new language switches the whole app at once and also clears the header's per-tab language switch, which would otherwise keep overriding the saved one. Firestore holds the new `preferred_language`, which also drives reports, notifications and SMS.

**Notification defaults.** If the user never saved a choice, the page shows the documented default: everything on, for their own corridor (host to home) when it is one of the six. The default is only shown; nothing is written until they press Save. The form keeps only the user's own edits on top of what is saved, so changing the host country above does not make an untouched form look edited.

## Delete my account

The backend does the deleting, because a browser cannot delete subcollections, Storage files or the sign-in account (the rules forbid it on purpose). Flow:

```
Delete my account ─► tick "I understand this cannot be undone" ─► Delete permanently
   │
   ├─ signed in within the last 4 minutes? ── no ─► "Confirm it's you"
   │        (Google: sign in with Google again | phone: new SMS code to the same number)
   ▼
DELETE /api/v1/users/me   (Authorization: Bearer <ID token>)
   │   backend: token valid? sign-in ≤ 5 min old? (else 403 recent_login_required → same re-login screen)
   ▼
1. users/{uid} and every subcollection   (Firestore recursive delete)
2. Storage: contracts/{uid}/, bills/{uid}/, exports/{uid}/
3. Firebase Auth user                    (last, so a failed data step can be retried)
   ▼
204 ─► sign out ─► /sign-in with "Your account and data have been deleted."
```

- **Kept on purpose:** reports the user sent to Exploitation Radar (only a salted hash, never the account) and the `radar-evidence/` Storage folder. The page says so.
- **Failure is safe to retry.** Every step can run again. The sign-in account goes last, so a person whose data step failed can still sign in and try again. The page shows "We couldn't finish deleting your account. Please try again."
- **Fresh sign-in.** The backend refuses (403) unless the ID token's `auth_time` is at most 5 minutes old (`ACCOUNT_DELETION_MAX_LOGIN_AGE_SECONDS`, default 300). The page checks first (4 minutes, a margin for slow screens) and only calls the backend when the login is recent; if the backend still refuses, it shows the same re-login screen.
- **The delete section is hidden when the backend cannot be reached** (a deployed site with no `VITE_API_BASE_URL`), so nobody sees a button that can only fail. See "Turn it on in production".

## Files

| File | Purpose |
|---|---|
| `frontend/src/pages/Profile.tsx` | The page: loads the profile (spinner, retry on error) and lays out the four sections |
| `frontend/src/components/profile/DetailsForm.tsx` | Edit language, host, home, job; writes only changed fields; applies a language change |
| `frontend/src/components/profile/NotificationsForm.tsx` | Edit notification preferences; writes the whole map |
| `frontend/src/components/profile/DeleteAccount.tsx`, `ReauthPanel.tsx` | Confirmation, "confirm it's you" (Google or phone code), the delete call |
| `frontend/src/components/profile/SaveStatus.tsx`, `styles.ts` | Shared "Saving…/Saved/error" line (a live region) and styles |
| `frontend/src/services/userService.ts`, `hooks/useUser.ts` | `updateProfile` (Firestore write) and `useUpdateProfile` (write, then read back) |
| `frontend/src/services/apiClient.ts` | Calls the backend with the user's ID token; `VITE_API_BASE_URL`; `isApiConfigured` |
| `frontend/src/services/accountService.ts` | `deleteAccount()`, the "sign in again" error check, the "account deleted" notice flag |
| `frontend/src/services/authService.ts` | Added: sign-in method, `signedInWithin`, Google and phone re-login |
| `frontend/src/router.tsx`, `components/layout/Header.tsx` | `/profile` route and the header icon |
| `frontend/src/pages/SignIn.tsx` | Shows "Your account and data have been deleted." once after a deletion |
| `frontend/src/types/user.ts`, `types/enums.ts` | `NotificationPrefs`, `ProfileChanges`, `CORRIDOR_IDS` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `profile.*` and `nav.profile` in all six languages (identical key sets) |
| `frontend/vite.config.ts`, `src/vite-env.d.ts`, `.env.example` | Dev proxy `/api` to the local backend; `VITE_API_BASE_URL` |
| `frontend/tests/rules/firestore.rules.test.ts` | 5 more rule tests for the profile page's write shapes (94 to 99 tests) |
| `backend/app/api/v1/users.py` | `DELETE /api/v1/users/me` |
| `backend/app/services/auth_service.py` | `AccountService`: the three steps in order, `AccountDeletionError` |
| `backend/app/integrations/cloud_storage.py`, `firebase_auth.py` | Delete a user's files; delete the Auth user (`firebase_auth.py` is new) |
| `backend/app/dependencies.py`, `schemas/user.py`, `config.py`, `api/v1/router.py` | `get_account_service`, `auth_time` on the caller, two settings, the router |
| `backend/tests/unit/services/test_account_service.py`, `tests/integration/api/test_users_delete.py` | 19 tests |
| `infra/iam/grant-account-deletion-roles.sh` | The two production roles the backend needs (run by a project owner) |
| `docs/api/endpoints.md`, `docs/data-model/collections/users.md`, `infra/iam/service-accounts.md` | Endpoint contract, deletion order, the new grants |

Shared files: none changed. `firestore.rules` is untouched (the existing rules already accept these writes; the new tests prove it).

## Try it locally (all on emulators, nothing real is touched)

Needs the Firebase CLI and Java (as for NF-P1-014). Four terminals.

**1. Emulators** (from `frontend/`):

```bash
firebase emulators:start --only auth,firestore,storage --project demo-nomadfinance
```

**2. Backend** (from `backend/`, venv active) — pointed at the emulators:

**bash**
```bash
APP_ENV=local GEMINI_API_KEY=test FIREBASE_PROJECT_ID=demo-nomadfinance \
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
STORAGE_EMULATOR_HOST=http://127.0.0.1:9199 FIREBASE_STORAGE_BUCKET=demo-nomadfinance.appspot.com \
uvicorn app.main:app --port 8080
```

**Windows PowerShell**
```powershell
$env:APP_ENV="local"; $env:GEMINI_API_KEY="test"; $env:FIREBASE_PROJECT_ID="demo-nomadfinance"
$env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8085"; $env:FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099"
$env:STORAGE_EMULATOR_HOST="http://127.0.0.1:9199"; $env:FIREBASE_STORAGE_BUCKET="demo-nomadfinance.appspot.com"
uvicorn app.main:app --port 8080
```

**3. Frontend** (from `frontend/`): `pnpm dev --mode emulator`. In development Vite forwards `/api` to `http://127.0.0.1:8080`, so no CORS is involved.

**4. Try the page.** Open `http://localhost:5173/sign-in`, sign in with any number (the SMS code is at `http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`, or in the emulator log), finish onboarding, then click the person icon.

| Try | Expect |
|---|---|
| Change the country you work in and the kind of work, press **Save changes** | "Saved". In the emulator UI (`http://127.0.0.1:4000/firestore`, `users/<uid>`) `host_country`, `job_type` and `updated_at` changed; `created_at` and other fields did not |
| Header language switch to Tagalog, then save the language on the profile page as Hindi | The whole page turns Hindi and stays Hindi after a reload; Firestore `preferred_language` is `hi` |
| Tick two routes, untick reminders, **Save changes** | Firestore `notification_prefs` = `{radar_alerts, reminders, radar_corridors}` as chosen; reload shows the same |
| Nothing changed | Both Save buttons are disabled |
| **Delete my account**, tick the box, **Delete permanently** | Signed in less than 4 minutes ago: deleted at once, back on `/sign-in` with the notice. Older: "Confirm it's you" first (phone: **Send a code**, enter it, **Confirm and delete**) |
| After a deletion | `users/<uid>` and all its subcollections are gone; the user's files under `contracts/`, `bills/`, `exports/` are gone; the Auth user is gone (emulator UI, Authentication tab); another user's data and `radar-evidence/` are untouched |

The endpoint on its own (no browser), with a token for a signed-in user:

```bash
curl -s -X DELETE http://127.0.0.1:8080/api/v1/users/me -H "Authorization: Bearer $ID_TOKEN" -w "%{http_code}\n"
```

Expected: `204`; without a token `401`; with a sign-in older than the limit `403 {"detail":"recent_login_required"}`. To force the 403 while testing, start the backend with `ACCOUNT_DELETION_MAX_LOGIN_AGE_SECONDS=20`.

Checks: `pnpm lint`, `pnpm format:check`, `pnpm build`, `pnpm test:rules` (99 passed); in `backend/`: `ruff check .`, `black --check .`, `mypy app`, `pytest` (119 passed).

## Turn it on in production

Deleting an account works from the browser only after these three things. The page hides the delete section until the last two are done, so nothing broken is shown.

> **Status (2026-09-27, NF-P1-027):** step 2 (CORS) and the workflow half of step 3 (`VITE_API_BASE_URL` passed in `frontend-deploy.yml`) are done in NF-P1-027. Still to do by a project owner: step 1 (the grant script: not run yet when checked) and the GitHub variable. The live test is in `NF-P1-027-backend-cors-rate-limit.md`, "Turn on account deletion in production".

1. **Roles for the backend service account** (a project owner runs it once; CI cannot do it):

   ```bash
   gcloud config set project nomadfinance-prod
   bash infra/iam/grant-account-deletion-roles.sh
   ```

   It grants `roles/firebaseauth.admin` (delete the sign-in account) and `roles/storage.objectUser` on the Storage bucket only (delete files). Without them the endpoint answers `503` after deleting the Firestore data.

2. **CORS on the backend** (NF-P1-027, Devam): allow the site's origin (`https://nomadfinance-prod.web.app`, also `https://nomadfinance-prod.firebaseapp.com` if used) with the `Authorization` header and the `DELETE` method. Without it the browser blocks the call.

3. **Tell the frontend where the backend is:** add the GitHub repository **Variable** `VITE_API_BASE_URL` (the Cloud Run URL, `https://nomadfinance-api-54982290462.asia-south1.run.app`) and pass it to the Build step of `.github/workflows/frontend-deploy.yml` (`VITE_API_BASE_URL: ${{ vars.VITE_API_BASE_URL }}`; that file is a shared file, so agree the change first). After the next frontend deploy the delete section appears.

**Handing it to Devam to test the delete API** (after CORS): call it once against production with a throwaway account (a test phone number): create the account and sign in, add a contract or upload a file if possible, then press **Delete my account** (or use the curl command with a fresh token). Expected `204`, then check Firestore (`users/<uid>` gone with its subcollections), Storage (that user's files gone) and the Firebase console Authentication tab (user gone). A `503` after the data is gone means a role from step 1 is missing; run the delete again once it is added.

## Remove the grants (if you must)

```bash
gcloud projects remove-iam-policy-binding nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role=roles/firebaseauth.admin
gcloud storage buckets remove-iam-policy-binding gs://nomadfinance-prod.firebasestorage.app --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role=roles/storage.objectUser
```

## Verified results (2026-09-25, emulators: Auth + Firestore + Storage, real backend, real rules)

| Check | Result |
|---|---|
| Edit host country + job type, Save | Firestore: `host_country`, `job_type` changed, `updated_at` moved, `created_at` and `preferred_language`, `home_country` untouched; page shows "Saved"; Save disabled before the edit |
| Header switch to Tagalog, then save Hindi | UI Hindi, `<html lang="hi">`, session override cleared, Firestore `preferred_language: hi` |
| Notifications: SG-IN off, AU-IN on, reminders off | Firestore `{radar_alerts: true, reminders: false, radar_corridors: ["AU-IN"]}`, other fields intact |
| Reload | Page shows exactly the saved values in Hindi; both Save buttons disabled |
| Bug found in testing and fixed | The untouched notifications form looked edited after the host country changed (its remembered default went stale). It now keeps only the user's edits on top of the saved values |
| Delete, recent sign-in | `204`; `users/<uid>` and nested documents gone; the 3 file folders emptied (nested file included); Auth user gone; another user's documents, files and account, and `radar-evidence/`, untouched; `/sign-in` shows the notice once |
| Delete, backend refuses (`ACCOUNT_DELETION_MAX_LOGIN_AGE_SECONDS=20`) | `403`, nothing deleted; the page shows "Confirm it's you" with the phone number; new SMS code, then `204` and everything removed |
| Phone size (375 px) | One column, no horizontal scroll, 44 px tap targets, text wraps |
| `pytest`, `ruff`, `black`, `mypy` (backend) | 119 passed (19 new); clean |
| `pnpm test:rules` | 99 passed (5 new) |
| `pnpm lint`, `format:check`, `build` | clean |

## Definition of Done

Frontend feature:
- [x] Built with Tailwind, native controls and the existing shadcn `Button`
- [x] Mobile responsive (checked at 375 px)
- [x] Loading state (spinner), error state with retry, saving/saved/error status on each form
- [x] i18n keys in all six languages
- [x] Accessibility: labelled controls, hints tied with `aria-describedby`, live status regions, focusable native controls
- [ ] Works on a throttled 3G connection (not tested; saves are small single writes)
- [ ] Screenshots added to the PR (take them from the emulator run above)

Backend endpoint:
- [x] FastAPI endpoint with Firebase token verification; specific status codes (401, 403, 503)
- [x] Manual test against the real emulators (Swagger not used; curl and the browser)
- [x] `docs/api/endpoints.md` updated; the schema is auto-generated
- [ ] Structured logging with request id and hashed user id (NF-P1-028); the endpoint logs only counts and the failure type, never the uid
- [ ] Rate limiting (NF-P1-027)

Firestore schema change:
- [x] Migration: not needed (no field changes)
- [x] Security rules: unchanged and sufficient; 5 tests added
- [x] `docs/data-model/collections/users.md` updated
- [x] Emulator tests pass (99 rule tests)

## Commit and PR

Branch: `feature/frontend-profile-page`.

```bash
git add frontend backend docs infra
git status
git commit -m "feat(profile): add profile page with Firestore edits and account deletion" -m "Refs: NF-P1-023"
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Save button stays disabled | Nothing changed compared with Firestore. Change a value |
| "We couldn't save your changes" | Firestore refused or the connection dropped. Offline writes are queued and finish when the connection returns. A value outside `types/enums.ts` is refused by the rules |
| No "Delete my account" section | The backend is not configured for this site: on a deployed site `VITE_API_BASE_URL` is unset. In development it always shows (Vite proxy) |
| Delete: "We couldn't finish deleting your account" | The backend answered 503 or was unreachable. Check the backend log line `account_deletion_failed cause=...`. Production: `PermissionDenied` means a role from "Turn it on" step 1 is missing. Press delete again; every step can be repeated |
| Delete works locally, browser error in production | CORS not set up yet (NF-P1-027), or `VITE_API_BASE_URL` points to the wrong address |
| Always asked to sign in again | The backend and browser clocks differ a lot, or `ACCOUNT_DELETION_MAX_LOGIN_AGE_SECONDS` is very small |
| Phone re-login: "security check didn't pass" | reCAPTCHA. Refresh and try again; on localhost only test numbers or the emulator work |
| Google re-login popup blocked | Allow popups for the site, or sign out and sign in again with Google, then retry within 4 minutes |
| `ModuleNotFoundError`/emulator port busy | Another emulator run is using 8085/9099/9199; stop it (`pkill -f "firebase emulators"`) |

## Not covered here

- Push tokens and the notification feed: NF-P3-004, NF-P3-009
- CORS and rate limiting: NF-P1-027 (Devam)
- The toast system: NF-P1-026 (the page uses inline status lines)
- Structured request logging: NF-P1-028
- Changing the Google or phone sign-in details themselves (managed by Google or the phone number)
- A "download my data" export
