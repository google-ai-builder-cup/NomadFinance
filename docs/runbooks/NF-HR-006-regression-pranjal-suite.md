# NF-HR-006 — Full regression bug bash, Pranjal suite

## Summary

Exploitation Radar, the Remittance → Coach handoff and the installed app (install offer, offline, push) were regression-tested in three browser engines (Chromium, Firefox, WebKit), each as a desktop window and as a phone. One P1, one P2 and one P3 were found and fixed with tests; three P2 are filed with the fix to make. The test sheet and bug log are `docs/evals/regression-suite-c-v2.md`.

| Part | What it is | Where |
|---|---|---|
| **Test sheet and bug log** | 23 Radar cases in six engine/viewport columns (and 5 more in Chromium), 37 API checks, 8 handoff cases, about 30 PWA, install and push cases, six bugs QA-C-01 to QA-C-06 | `docs/evals/regression-suite-c-v2.md` |
| **Browser tests** | Radar and the installed app had none: 11 and 6 tests, on the `desktop` and `mobile` projects | `frontend/e2e/radar.spec.ts`, `e2e/pwa.spec.ts`, `e2e/support/radarApi.ts` |
| **Fixes** | See the table below | `frontend/src/services/authService.ts`, `lib/messaging.ts`, `pages/radar/RadarReport.tsx`, `backend/app/services/radar/intake.py` |

**What this task could not do:** deliver a real push to a real phone, or run on a real iPhone or Android phone (D-327). Playwright's Chromium has no push service, so a device token cannot be had in it; everything after a push reaches the page or the worker was run for real.

## Bugs found

| ID | Sev | What | Fix |
|---|---|---|---|
| QA-C-05 | **P1** | Signing out left the browser's push token on the profile: on a shared phone the last worker's alerts and Coach reminders kept arriving for the next | `releasePushToken` in `lib/messaging.ts`, `removeFcmToken` in `userService.ts`, called by `signOut` |
| QA-C-01 | P2 | Two quick taps on Send report stored two reports | A guard held for the call in `RadarReport.tsx` |
| QA-C-06 | P3 | A business name with no letters or digits was accepted, stored with an empty slug and never shown | The API answers 422 (`intake.py`) |
| QA-C-02 | P2 | Reports at the same instant lose count updates | Filed, D-328 |
| QA-C-03 | P2 | A transfer is dated by the UTC day | Filed, D-329 |
| QA-C-04 | P2 | Cold open offline: "could not load your profile" everywhere; the offer says "works offline" | Filed, D-330 (a decision) |

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Severity of QA-C-05 | P1: one worker's alerts reach the next person on the phone, and the product says phones are shared. It affects only workers who turned push on, and the text shown is generic, which is why it is not P0 |
| 2 | Fixing QA-C-05 in the frontend only | The server already drops a token FCM reports gone and the rules let a worker write their own `fcm_tokens`; nothing else had to change. Tokens left before the fix stay until FCM drops them (D-332) |
| 3 | The time sign-out may wait | At most 3 s for the push service, then signs out anyway: signing out comes first |
| 4 | QA-C-03 and QA-C-02 not fixed | Each needs two sides to change together (the date) or a transaction (the count): more than a regression task should do on the quiet. Filed with the exact fix |
| 5 | QA-C-04 left as a decision | Persistent Firestore cache changes what a phone keeps after sign-out; rewording needs six languages and a native read. It is a product call |
| 6 | The frontend sends no date for the Radar report | Nothing to change there; the report's own time is the server's |
| 7 | Push in the browser tests | Not in the default projects: they block service workers (so a mocked API is not bypassed). The push cases are in the sheet and the unit tests |

## Files

| File | Change |
|---|---|
| `frontend/src/lib/messaging.ts`, `messaging.test.ts` | `releasePushToken` |
| `frontend/src/services/authService.ts`, `authService.signOut.test.ts`, `userService.ts` | Sign-out releases and removes the token; `removeFcmToken` |
| `frontend/src/pages/radar/RadarReport.tsx`, `RadarReport.send.test.tsx` (new) | One report per tap |
| `backend/app/services/radar/intake.py`, `tests/unit/services/test_radar_intake.py` | A name with no letters or digits is refused |
| `frontend/e2e/radar.spec.ts`, `e2e/pwa.spec.ts`, `e2e/support/radarApi.ts` (new) | Browser tests |
| `docs/evals/regression-suite-c-v2.md` (new), this file (new), `docs/deferred-items.md` | Docs, D-327 to D-332 |

No shared file was touched, no dependency was added, and no rule, index or workflow changed.

## Checks run (2026-10-13)

| Check | Result |
|---|---|
| Backend: `ruff check app tests`, `black --check`, `mypy --strict` on the changed file | clean |
| Backend unit (`pytest tests/unit`) | **3,236 passed**, 1 skipped |
| Backend integration, Radar, emulators | **40 passed** |
| Frontend `pnpm lint`, `format:check`, `tsc --noEmit`, `tsc -p e2e` | clean |
| Frontend unit (`pnpm test`) | 147 files, **1,699 passed** |
| End-to-end, default projects (`vite build --mode emulator`, as CI) | **246 passed** |
| End-to-end, `firefox` and `webkit-iphone`, Radar and PWA specs | **31 passed**, 3 skipped by design |
| Break check | Each fix undone once, its tests failed, then restored: the Radar send guard (unit and browser: the second report is sent), the sign-out release (`signOut` no longer calls it; `releasePushToken` without `deleteToken`), and the symbol-only name (accepted again, 3 cases fail) |
| Run against the stack | The sheet's scripted cases (Radar ×6 columns, API, handoff ×4, PWA ×6, install ×6, push ×2) ran against the emulators and the real API; the names check was repeated against the fixed API (422 for `???` and `💸💸💸`) |

**Not verified:** a real push to a real device (D-327); the sign-out fix against real FCM; the flagged parties on a contract report; the CI run on GitHub.

## Manual test (about 15 minutes)

Needs the local stack (emulators, the API, the frontend) as in NF-HR-004's runbook.

1. **One report per tap (QA-C-01).** `/radar/report`, fill the four steps, then double-tap **Send report**. Open the business: one new report.
2. **A name with no letters (QA-C-06).** Report a business called `???`. You are told to add a business name; nothing is stored.
3. **The handoff.** Open `/coach` → **View my plan** → **Compare in Remittance X-Ray**: the route and amount are filled and one comparison runs. Log a transfer with **I used this**, then start a new interview (`POST /api/v2/coach/sessions` with `restart: true`, or start over from the Coach): "Money you send home" shows the new monthly average.
4. **Install offer.** In DevTools run `window.dispatchEvent(Object.assign(new Event("beforeinstallprompt",{cancelable:true}),{prompt:async()=>{},userChoice:Promise.resolve({outcome:"accepted"})}))`: the offer appears after about three seconds; **Install** closes it; the close button keeps it away for 14 days.
5. **Sign-out and push (QA-C-05), on a real phone.** With FCM configured: Profile → turn on browser notifications; check `fcm_tokens` on the profile has one entry; sign out; the entry is gone and an alert no longer arrives. (D-327.)
6. **Browser tests.**

   bash:

   ```bash
   cd frontend
   VITE_API_BASE_URL=http://127.0.0.1:4173 pnpm exec vite build --mode emulator
   firebase emulators:exec --only auth,firestore --project demo-nomadfinance \
     "pnpm exec playwright test e2e/radar.spec.ts e2e/pwa.spec.ts"
   ```

   Windows PowerShell:

   ```powershell
   cd frontend
   $env:VITE_API_BASE_URL = "http://127.0.0.1:4173"; pnpm exec vite build --mode emulator
   firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm exec playwright test e2e/radar.spec.ts e2e/pwa.spec.ts"
   ```

## Definition of Done (Test-only / QA task)

- [x] **A test fails when the behaviour is broken**: each new test was run against its broken code once and failed (see the break check above)
- [x] **Passes in CI**: the same chains CI runs were run locally (above); not yet seen on GitHub
- [x] Bugs found are filed with severity and repro steps (P0 none; the P1, a P2 and a P3 fixed; three P2 in `docs/deferred-items.md`)
- [x] Report committed under `docs/evals` (`regression-suite-c-v2.md`)
- [x] Cross-browser: Chromium, Firefox and WebKit run on Radar, the handoff and the installed app (limits in the sheet)
- [ ] Tracker finish line "all P0 / P1 bugs found are filed with repro steps": met in the files; the P1 is closed only when this branch is merged
- [ ] Push and the installed app on real devices (D-327)
- [ ] A decision on offline (D-330)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `fix/regression-suite-c` (already checked out).

```
test(regression): add regression suite C and fix its bugs
Refs: NF-HR-006
```

## For teammates

- **Aditya:** D-328 (a transaction for the business profile), D-329 (the local date; the Coach's window is Devam's) and D-327 (the real-phone check) are yours; `frontend/e2e/support/radarApi.ts` is how a browser test plays the Radar API.
- **Devam:** QA-C-05 changed `signOut` (`services/authService.ts`), which every sign-out goes through, and D-329 touches `known_details.py`: worth a second read.
- **Pranjal (demo):** D-330 (offline) and D-331 (the demo Radar data never matches a price survey firm, so the flagged badge is invisible in the seeded demo) are product calls before 18 October.
