# NF-HR-005 — Full regression bug bash, Aditya suite

## Summary

Remittance X-Ray and the Scam Analyzer were regression-tested in three browser engines (Chromium, Firefox, WebKit), each as a desktop window and as a phone. One P1 and four P2 were found and fixed with tests; nothing else was left open. The test sheet and bug log are `docs/evals/regression-suite-b-v2.md`.

| Part | What it is | Where |
|---|---|---|
| **Test sheet and bug log** | 32 Remittance cases, 23 Scam Analyzer cases, 63 API checks, Slow 3G, a compatibility audit, five bugs QA-B-01 to QA-B-05 | `docs/evals/regression-suite-b-v2.md` |
| **Browser tests** | Remittance X-Ray had no browser test at all; now eight, on the `desktop` and `mobile` projects | `frontend/e2e/remittance.spec.ts`, `frontend/e2e/support/remittanceApi.ts` |
| **Firefox and WebKit** | Two opt-in Playwright projects, off by default so CI does not change | `frontend/playwright.config.ts` |
| **Five fixes** | See the table below | `frontend/src/utils/`, `components/remittance/`, `pages/remittance/`, `services/scamService.ts` |

**What this task could not do:** run on a real iPhone or a real Android phone (D-321). WebKit with an iPhone 13 profile is a stand-in for Safari on iOS, and Chromium with a Pixel 5 profile for Chrome on Android.

## Bugs found

| ID | Sev | What | Fix |
|---|---|---|---|
| QA-B-04 | **P1** | The Scam Analyzer threw before sending anything on a browser with no `AbortSignal.timeout` (Safari before 16, so an iPhone 7 or older) | `utils/timeoutSignal.ts`, used by `scamService.ts` |
| QA-B-01 | P2 | Amounts typed with Hindi, Nepali, Bengali, Arabic-Indic or full-width digits were refused in the Remittance, Financial Identity and Coach forms | `utils/digits.ts`, called by the three parsers |
| QA-B-02 | P2 | A failed written advice said "…while checking your contract" | `adviceFailureKey` in `utils/corridors.ts`, used by `RecommendationCard.tsx` |
| QA-B-03 | P2 | Two taps in the same instant on "I sent this" stored two transfers | A flag in `RemittanceCompare.tsx` held for the length of the call |
| QA-B-05 | P2 | `Array.prototype.at` in `flaggedParties.ts` broke a contract report on Safari 15.0 to 15.3 | `words[words.length - 1]` |

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Firefox and WebKit in CI | Not added. Two more engines roughly double the end-to-end minutes and need an install step in a workflow file (a shared file). They are opt-in projects (`CROSS_BROWSER=1`) and a run before the demo is D-323 |
| 2 | WebKit as Safari on iOS | Stated as a stand-in everywhere it is used. The suite does not claim Safari passes |
| 3 | The model | A stand-in with four modes (ok, busy, wrong provider, blank), so every run repeats and costs no quota. The advice text is for the live evals (D-324) |
| 4 | Where to fix a native-digit bug | One `toAsciiDigits` before the existing parsing, not a rewrite of three parsers: their separator rules (a comma may be thousands or a decimal) stay as they were |
| 5 | A digit script that is not in the list | Left as it is and still refused. A guess about an unknown script could turn a letter or a symbol into a number |
| 6 | Severity of QA-B-01 | P2, not P1: the worker gets a clear message and 500 in ordinary digits works. It is on three screens, which is why it was fixed here |
| 7 | QA-B-05 is in Contract Shield | Found by the audit of the browser APIs, a one-line fix; the pillar belongs to NF-HR-004 |
| 8 | The 13 API "failures" | A wrong assumption of mine about each corridor's limits (a quarter of the lower survey amount, ten times the upper). The API was right; the sheet says so |
| 9 | `dvh` fallbacks | Filed (D-325), not fixed: a layout is poor on an old browser, not broken |

## Files

| File | Change |
|---|---|
| `frontend/src/utils/digits.ts`, `digits.test.ts` (new) | `toAsciiDigits` |
| `frontend/src/utils/corridors.ts`, `fibForm.ts`, `coachInput.ts` and their tests | The three parsers read native digits; `adviceFailureKey` |
| `frontend/src/components/remittance/RecommendationCard.tsx` | Uses `adviceFailureKey` |
| `frontend/src/pages/remittance/RemittanceCompare.tsx`, `RemittanceCompare.log.test.tsx` (new) | One log per tap |
| `frontend/src/utils/timeoutSignal.ts`, `timeoutSignal.test.ts` (new), `services/scamService.ts` | A timeout signal for browsers without `AbortSignal.timeout` |
| `frontend/src/utils/flaggedParties.ts` | No `.at` |
| `frontend/e2e/remittance.spec.ts`, `e2e/support/remittanceApi.ts` (new) | Eight browser tests for Remittance X-Ray |
| `frontend/playwright.config.ts` | The `firefox` and `webkit-iphone` projects, opt-in |
| `docs/evals/regression-suite-b-v2.md` (new), this file (new), `docs/deferred-items.md` | Docs, D-321 to D-326 |

No shared file other than `frontend/playwright.config.ts` was touched. **That file is not in the shared list of `CLAUDE.md`** (`tsconfig*.json`, `package.json`, workflows and the others are); the change is additive and off unless `CROSS_BROWSER=1`. No dependency was added: Playwright's Firefox and WebKit are downloaded with `playwright install`, not through `package.json`.

## Checks run (2026-10-13)

| Check | Result |
|---|---|
| `pnpm lint` | clean (0 warnings) |
| `pnpm format:check` | clean |
| `pnpm exec tsc --noEmit` | clean |
| `pnpm test` (unit) | 146 files, **1,689 passed** |
| `tsc -p e2e` | clean |
| End-to-end, default projects (`desktop`, `mobile`) | **212 passed** |
| End-to-end, `firefox` and `webkit-iphone`, six specs (remittance, scam-check, scam-history, scam-screenshot, smoke, dashboard) | **66 passed** |
| Break check | Each fix was undone once and its tests run: `toAsciiDigits` as the identity fails `digits.test.ts` (8 cases); a 502 treated as a generic error fails `adviceFailureKey`; no log guard fails both log tests; `AbortSignal.timeout` called unconditionally fails the "browser without it" test. QA-B-05 cannot fail under Node (which has `.at`), so it has no test of its own |
| Backend | Not run: no backend file changed |

**Not verified:** a real iOS Safari or Android Chrome (D-321); Remittance in five languages (D-322); the CI run on GitHub.

## Manual test (about 10 minutes)

Needs the local stack: the Firebase emulators, the API on 8080 and the frontend. The repo's `docs/runbooks` for earlier tasks (NF-HR-004) describe it.

1. **Native digits (QA-B-01).** Sign in, open `/remittance`, type `५००` (Devanagari five-zero-zero) in the amount, press **Compare services**. A ranked comparison appears and no message says "Enter the amount as a number". Also try `৫০০`. Then `500 SGD` and `abc`: both are refused with that message and send nothing.
2. **Advice that fails (QA-B-02).** Make the model fail (the e2e test does it with a stubbed answer: `pnpm test:e2e e2e/remittance.spec.ts -g advice`). The card shows "Our server had a problem. Please try again in a moment." and does not mention a contract (before the fix: "Something went wrong while checking your contract").
3. **One tap, one transfer (QA-B-03).** In a comparison, double-tap **I sent this** on a provider. The row says Logged and the history lists one transfer.
4. **No `AbortSignal.timeout` (QA-B-04).** Open `/scam-check`, run `delete AbortSignal.timeout` in the console, paste a message and press **Check**. A verdict appears (before the fix: an error and no request).
5. **Firefox and WebKit.** The browser tests run against the production build served by `vite preview` and sign in through the Auth and Firestore emulators, as CI does.

   bash:

   ```bash
   cd frontend
   pnpm exec playwright install firefox webkit      # once
   pnpm build
   CROSS_BROWSER=1 firebase emulators:exec --only auth,firestore --project demo-nomadfinance \
     "pnpm exec playwright test --project=firefox --project=webkit-iphone"
   ```

   Windows PowerShell:

   ```powershell
   cd frontend
   pnpm exec playwright install firefox webkit
   pnpm build
   $env:CROSS_BROWSER = "1"
   firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm exec playwright test --project=firefox --project=webkit-iphone"
   ```

   Expect all to pass. One Firestore-emulator page error is shown by WebKit when a test checks for uncaught errors (D-326); it is not the app's.

## Definition of Done (Test-only / QA task)

- [x] **A test fails when the behaviour is broken**: each new test was run against its broken code once and failed (see the break check above). QA-B-05 is the exception, with a reason
- [x] **Passes in CI**: the same chains CI runs were run locally (above); not yet seen on GitHub
- [x] Bugs found are filed with severity and repro steps (P0 none; P1 and four P2 fixed; limits and open items in `docs/deferred-items.md`)
- [x] Report committed under `docs/evals` (`regression-suite-b-v2.md`)
- [x] Cross-browser: Chromium, Firefox and WebKit run on Remittance and the Scam Analyzer
- [ ] Tracker finish line "all P0 / P1 bugs found are filed with repro steps": met in the files; the P1 is closed only when this branch is merged
- [ ] Real devices: Safari on iOS and Chrome on Android (D-321)
- [ ] Remittance screens in five languages and the flagged badge (D-322)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `fix/regression-suite-b` (already checked out).

```
test(regression): add regression suite B and fix its five bugs
Refs: NF-HR-005
```

## For teammates

- **Devam:** QA-B-05 is in Contract Shield's flagged-parties section (a one-line change) and QA-B-01 changed the amount parsers of Financial Identity and the Coach (`fibForm.ts`, `coachInput.ts`): worth a second read.
- **Anyone adding a browser API:** check it against the table in `docs/evals/regression-suite-b-v2.md` ("Compatibility audit") and guard it with `typeof … === "function"` the way `idempotency.ts` and `timeoutSignal.ts` do.
- **Anyone writing a browser test for Remittance:** `frontend/e2e/support/remittanceApi.ts` stubs the `/api/v1/remittance/**` calls; `route.fallback()` leaves everything else to the real API.
