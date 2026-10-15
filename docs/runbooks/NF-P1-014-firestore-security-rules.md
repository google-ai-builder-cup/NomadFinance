# NF-P1-014 — Firestore and Storage Security Rules

## Summary

Until 2026-09-25 both Firestore and Cloud Storage ran the Firebase "test mode" starter rules: **anyone on the internet could read, change or delete everything**, and on 2026-10-21 those rules would have switched to "deny everything". They are now replaced by rules built from the access matrix in `docs/data-model/firestore-schema.md` (NF-P1-013) and **deployed to `nomadfinance-prod`**. The model: a signed-in user reads **only their own** `users/{uid}` tree; the only things a browser may write are the owner's profile fields (with value checks and server timestamps) and the `read` flag on their own notifications. Shared reference data (corridors, FX rates, labor laws, complaint templates, radar entities and alerts) is readable by any signed-in user and writable by nobody from the browser. `radar_reports`, `report_embeddings` and every path not listed are denied. In Storage, a user can read their own `contracts/`, `bills/` and `exports/` files; browser uploads stay closed until an upload task adds a rule. The backend is unaffected: it uses the Admin SDK, which skips rules. 94 emulator tests cover every rule, and a deliberately broken rule was confirmed to fail them.

## Files

| File | Purpose |
|---|---|
| `frontend/firestore.rules` | Firestore rules (the only copy) |
| `frontend/storage.rules` | Cloud Storage rules (the only copy) |
| `frontend/firebase.json` | `firestore.rules` / `storage.rules` paths for deploy; Firestore (8085) and Storage (9199) emulators next to Auth (9099) |
| `frontend/tests/rules/firestore.rules.test.ts` | 83 Firestore rule tests |
| `frontend/tests/rules/storage.rules.test.ts` | 11 Storage rule tests |
| `frontend/package.json` | `test:rules` script; `vitest@5.0.2`, `@firebase/rules-unit-testing@5.0.2` (dev only) |
| `infra/firebase/firestore.rules`, `storage.rules` | **Deleted** (empty stubs): the Firebase CLI refuses rules files outside the folder that holds `firebase.json` ("is outside of project directory"), so the rules live in `frontend/`. `infra/README.md` says so. |

## Who can do what

| Path | Owner (signed in, uid matches) | Other signed-in user | Signed out |
|---|---|---|---|
| `users/{uid}` | read; create/update profile fields only (see below); no delete | — | — |
| `users/{uid}/notifications/{id}` | read; update only `read`, `read_at` | — | — |
| `users/{uid}/contracts/{id}`, `.../reports/{lang}`, `transfers`, `income`, `bills`, `savings`, `financial_profile` | read | — | — |
| any other `users/{uid}/...` subcollection | — | — | — |
| `corridors`, `rates_cache`, `rates_history/**`, `labor_laws/**`, `complaint_templates/**`, `radar_entities`, `radar_alerts/**` | read | read | — |
| `radar_reports`, `report_embeddings`, anything else | — | — | — |
| Storage `contracts/{uid}/**`, `bills/{uid}/**`, `exports/{uid}/**` | read | — | — |
| Storage anything else (incl. `radar-evidence/`), all uploads | — | — | — |

`—` = denied. Backend (Admin SDK): everything, always.

**Profile writes (`users/{uid}`):**
- Allowed fields: `home_country` (PH, IN, ID, NP, BD), `host_country` (SG, KR, MY, JP, HK, AU), `job_type` (7 values in `collections/users.md`), `preferred_language` (en, hi, tl, id, ne, bn), `onboarding_completed_at` (timestamp), `notification_prefs` (map: `radar_alerts` bool, `reminders` bool, `radar_corridors` list ≤ 6), `fcm_tokens` (list ≤ 5).
- **Create** must also send `created_at: serverTimestamp()`, `updated_at: serverTimestamp()`, `schema_version: 1`. Anything else (another field, a client-chosen date, version 2) is refused.
- **Update** may change profile fields plus `updated_at`, which must be `serverTimestamp()` on every update. `created_at` and `schema_version` can't change.
- **Delete** is backend only (NF-P1-023 must also delete subcollections, Storage files and the Auth user).

For NF-P1-022 (onboarding), a valid first write looks like:

```ts
await setDoc(doc(db, "users", user.uid), {
  home_country: "IN",
  host_country: "SG",
  job_type: "domestic_worker",
  preferred_language: "hi",
  onboarding_completed_at: serverTimestamp(),
  created_at: serverTimestamp(),
  updated_at: serverTimestamp(),
  schema_version: 1,
});
```

## Flow

```
browser (Firebase Web SDK, signed in)        backend (Admin SDK)
        │                                            │
        ▼                                            ▼
  Firestore / Storage  ── rules checked ──►   rules skipped
  request.auth.uid == {uid} ?  field checks ?  server timestamps ?
        │ yes → allowed        │ no → PERMISSION_DENIED (REST 403)
```

Change rules → edit `frontend/firestore.rules` / `storage.rules` → add tests → `pnpm test:rules` → PR → deploy (step 3).

## All commands, in order

From `frontend/` (pnpm 10; NVM for Windows users: `pnpm.cmd`, see the NF-P1-009 runbook step 0). Needs the Firebase CLI and Java 11+.

### 1. Install

```bash
pnpm install
```

### 2. Run the rule tests on the emulators

```bash
pnpm test:rules
```

This starts the Firestore (8085) and Storage (9199) emulators with project `demo-nomadfinance`, runs `vitest run tests/rules`, and stops them. Expected: `Test Files 2 passed (2)`, `Tests 94 passed (94)`, `Script exited successfully (code 0)`. The first run downloads the emulator jars (~1 minute).

A Java `NullPointerException … processRequestsFromInputStream` printed while the emulators shut down comes from the Storage rules runtime and is harmless: check that the script exited with code 0.

**Windows:** the Firestore emulator's Java process can survive the run and block the next one with `Could not start Firestore Emulator, port taken`. Stop it:

**Windows PowerShell**
```powershell
Get-NetTCPConnection -LocalPort 8085,9199,9150 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

**bash (macOS / Linux)**
```bash
lsof -ti tcp:8085,9199,9150 | xargs kill
```

### 3. Deploy the rules (after changing them)

```bash
firebase deploy --only firestore:rules,storage --project nomadfinance-prod
```

Expected: `rules file firestore.rules compiled successfully`, `rules file storage.rules compiled successfully`, `released rules …`, `Deploy complete!`. Hosting is not touched.

### 4. Check the live rules

Anonymous reads must be refused (403). A 404 would mean "allowed, document missing", which is what the old open rules returned.

**bash**
```bash
curl -s -o /dev/null -w "%{http_code}\n" "https://firestore.googleapis.com/v1/projects/nomadfinance-prod/databases/(default)/documents/corridors/SG-PH"
curl -s -o /dev/null -w "%{http_code}\n" "https://firebasestorage.googleapis.com/v0/b/nomadfinance-prod.firebasestorage.app/o/contracts%2Fx%2Fy%2Fz.pdf"
```

**Windows PowerShell**
```powershell
curl.exe -s -o NUL -w "%{http_code}\n" "https://firestore.googleapis.com/v1/projects/nomadfinance-prod/databases/(default)/documents/corridors/SG-PH"
curl.exe -s -o NUL -w "%{http_code}\n" "https://firebasestorage.googleapis.com/v0/b/nomadfinance-prod.firebasestorage.app/o/contracts%2Fx%2Fy%2Fz.pdf"
```

Expected: `403` and `403`. To see what is live, Firebase console → Firestore Database → Rules (and Storage → Rules); the header comment says NF-P1-014.

### 5. Backend Firestore tests against the emulator (NF-P1-005)

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

Terminal 2, from `backend/`:

**Windows PowerShell**
```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"; pytest tests/integration/repositories -v
```

**bash**
```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance pytest tests/integration/repositories -v
```

Expected: `1 passed`. The Admin SDK skips rules, so this checks the repository code, not the rules.

## Verified results (2026-09-25)

| Check | Result |
|---|---|
| `pnpm test:rules` | 94 passed (83 Firestore, 11 Storage) |
| Mutation check: owner-only profile read changed to "any signed-in user" | 2 tests failed as they should ("lets only the owner read the profile", "blocks listing all users"); rule restored |
| `pnpm lint` / `tsc -b` / `pnpm build` | clean / clean / built |
| Live **before** deploy: anonymous GET `corridors/SG-PH`, `users/someone-else` | 404 = **allowed** (open database) |
| Deploy | Both rulesets compiled and released 2026-09-25 12:17 UTC |
| Live **after**: anonymous GET Firestore `corridors`, `users`, `radar_reports`; Storage `contracts/...` | 403, 403, 403, 403 |
| Live, real ID token (test account `+61 491 570 156`): own profile / other profile / `corridors` read / `corridors` write / `radar_reports` / add `is_admin` to own profile | allowed / 403 / allowed / 403 / 403 / 403 |
| Live Storage, same token: own `contracts/` path / someone else's | allowed / 403 |
| NF-P1-005 Firestore round-trip test on the emulator (was always skipped) | 1 passed |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `firestore.rules is outside of project directory` | Rules paths in `firebase.json` must stay inside `frontend/`. |
| `Could not start Firestore Emulator, port taken` | A leftover emulator (Windows) or the backend on 8080? The emulator uses 8085; stop the leftover process (step 2). |
| `Could not spawn java` | Install Java 11+. |
| A browser write fails with `permission-denied` / `Missing or insufficient permissions` | Check the table above: extra field, invalid value, `updated_at` not `serverTimestamp()`, or a collection the browser may only read. Reproduce it as a test in `tests/rules/firestore.rules.test.ts` first. |
| Need a new browser-readable collection | Add a `match` in `firestore.rules` and tests, run `pnpm test:rules`, deploy (step 3). Unlisted paths are denied on purpose. |
| Need browser uploads to Storage | Add an owner `create` rule for that folder with `request.resource.size` and `request.resource.contentType` limits (match the backend: 10 MB; PDF, PNG, JPEG, WebP, HEIC). |
| Tests hang or time out | The emulators didn't start. Run `firebase emulators:start --only firestore,storage --project demo-nomadfinance` to see the error. |

## Commit and PR for this task

Branch: `feature/data-firestore-rules`. From the repo root:

```bash
git add frontend infra docs
git status
```

Expect: `frontend/firebase.json`, `firestore.rules`, `storage.rules`, `package.json`, `pnpm-lock.yaml`, `tests/rules/*` (2 new), `infra/README.md`, `infra/firebase/firestore.rules` and `storage.rules` (deleted), this runbook, `docs/runbooks/NF-P1-005-firebase-admin-integration.md`.

```bash
git commit -m "feat(data): add Firestore and Storage security rules with emulator tests" -m "Refs: NF-P1-014"
```

PR title: `feat(data): Firestore + Storage security rules, emulator tests, deployed (NF-P1-014)`

## Not covered here

- Composite and vector indexes (`firestore.indexes.json`): not assigned yet, see deferred log
- Browser uploads (Storage create rules): the task that adds uploads (D-16)
- Onboarding write (uses the create rule above): NF-P1-022
- Account deletion (backend): NF-P1-023
- Full security audit: NF-P4-004
