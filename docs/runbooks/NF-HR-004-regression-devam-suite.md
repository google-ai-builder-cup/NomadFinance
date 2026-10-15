# NF-HR-004 — Full regression bug bash, Devam suite

## Summary

Contract Shield, Financial Identity and the Financial Coach were tested end to end on a phone and a desktop, on Slow 3G, in each of the six languages, by hand-driven scripts against the real API and frontend on the Firebase emulators, and by new tests that now run in CI. The test sheet and the bug log are in **`docs/evals/regression-suite-a-v2.md`**.

| Result | |
|---|---|
| Bugs found | **1 P1, 6 P2, 2 P3**, no P0 |
| Fixed here, each with a test that fails without the fix | The P1 (QA-A-01) and four P2 (QA-A-02 to QA-A-05) |
| Filed with repro steps | QA-A-06, QA-A-07 (P2, NF-HR-009), QA-A-08, QA-A-09 (P3); D-277 to D-281 |
| Open P0 or P1 from this suite after the merge | **0** |

What each fix is, in one line:

| ID | Fix |
|---|---|
| QA-A-01 **P1** | A contract from another country than the worker's profile was checked under the profile's country with no warning. The report now says so and offers one tap to check it again for the contract's country |
| QA-A-02 | A photo with no document in it said "Something went wrong"; it now says it does not look like a contract |
| QA-A-03 | A Financial Identity PDF row could split across a page break (value on one page, label on the next); each row is now one unit |
| QA-A-04 | After a release, a tab opened before it could not leave a page it had not shown; "Try again" now reloads the page when the cause is a missing page file |
| QA-A-05 | An income, bill or savings entry had no upper limit (one slipped finger zeroed the income stability score); 1,000,000 (yen and won 100,000,000), in the form and in the API |

## Files

| File | Change |
|---|---|
| `docs/evals/regression-suite-a-v2.md` (new) | The test sheet and the bug log |
| `docs/api/endpoints.md` | The amount limit in the log endpoints' errors |
| `frontend/e2e/contract-shield.spec.ts` (new) | 11 browser tests: upload to report, language switch, unclear photo, busy AI service and Try again, refused files, history, another worker's number, no signal, the country notice (upload and history), no document |
| `frontend/e2e/identity.spec.ts` (new) | 19 browser tests: empty and filled dashboard, income validation, savings, a bill and sorting, bill photo, export |
| `frontend/e2e/regression-languages.spec.ts` (new) | Each of the six languages on the screens of the three pillars: language, no raw key, no placeholder, no sideways scroll |
| `frontend/e2e/support/contractApi.ts`, `fibApi.ts`, `firestoreRest.ts`, `i18n.ts`, `tap.ts` (new) | The two backends' stand-ins (they answer the calls and write the Firestore documents the real ones write), the Firestore writer, the translation reader, a tap that clears the fixed bottom bar |
| `backend/tests/integration/api/test_cross_pillar_regression.py` (new) | One worker through the three pillars on the emulator: contract → verified income → Coach offer → profile → feed → account deletion |
| `frontend/src/components/contract/CountryMismatchNotice.tsx` (+ test), `ReportView.tsx`, `pages/contract/ContractUpload.tsx`, `ContractReport.tsx`, `hooks/useContract.ts`, `services/contractService.ts`, `types/enums.ts` | QA-A-01 |
| `frontend/src/utils/pipelineProgress.ts` (+ test), `pages/contract/ContractUpload.tsx` | QA-A-02 |
| `backend/app/services/fib/report_html.py`, `backend/tests/unit/services/test_fib_report_html.py` | QA-A-03 |
| `frontend/src/utils/chunkError.ts` (+ test), `components/common/RouteError.tsx` (+ test) | QA-A-04 |
| `frontend/src/utils/fibForm.ts` (+ test), `backend/app/schemas/fib.py`, `backend/tests/integration/api/test_fib_log.py` | QA-A-05 |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `contract.report.countryMismatch.*`, `contract.upload.errors.notAContract`, `fib.log.errors.amount.tooLarge` |

No shared file (`package.json`, lockfile, `Dockerfile`, workflows, rules, `firebase.json`, `tsconfig*`) was touched, and no dependency was added.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | There is no staging | Everything ran on the emulators. The only production contact was read-only (`gcloud` reads, public pages, unauthenticated API calls) |
| 2 | Gemini | A stand-in, so runs repeat and use no quota (the free-tier day was used up). What the model says is not tested |
| 3 | PDFs | WeasyPrint cannot load on this Windows PC, so the PDFs were rendered by the production image built from `backend/Dockerfile` and run locally (approved before it was done). The image and container were removed afterwards |
| 4 | Fix or file | Your choice: fix the P1 and the tiny P2; file the rest. The country fix is a notice with a button, frontend only, not an automatic switch (the worker's choice stays theirs) |
| 5 | The amount limit | 1,000,000 per entry, 100,000,000 for yen and won (no minor unit), the same in the form and the API. A product number: change `MAX_AMOUNT` in `frontend/src/utils/fibForm.ts` and `backend/app/schemas/fib.py` together |
| 6 | The browser tests' backends | They write the Firestore documents themselves rather than reuse `docs/mocks/` (which only has the v2 routes); they are not drift-tested against the backend (D-280) |
| 7 | Bugs "filed" | In the sheet; no GitHub issues were opened |

## Checks (2026-10-10)

Run as CI runs them, locally on Windows, on clean emulators.

| Check | Result |
|---|---|
| Frontend `eslint`, `prettier --check` on the changed files, `tsc -b`, `tsc -p e2e` | clean |
| Frontend unit with coverage floors | **139 files, 1,645 passed** (before: 135 and 1,615); floors held |
| Frontend rules tests (Firestore and Storage emulators) | 3 files, **186 passed** |
| Frontend browser tests (emulator build, desktop and phone projects) | **148 passed** (the existing 64 plus 84 new). One run had a single first-load timeout and passed on the rerun |
| Backend `ruff`, `black --check`, `mypy app`, `mypy --strict app/services` | clean |
| Backend, no emulators | **3,712 passed**, 198 skipped, 0 failed in the last run |
| Backend integration on the emulators | **727 passed**, 99 skipped (live Gemini), **1 failed**: `test_scam_history.py`, the intermittent Windows-clock test (D-279); it also failed twice in the first baseline and passed in the second |
| Backend coverage gate | `app` 97.5% (needs 93%); `app/schemas` 99.4%, `app/services` 98.3% (need 70%) |
| Each new test fails when its fix is removed | shown for the notice, the upload message, the amount limit (form and API), the reload, the PDF rows (in the production image), and the verified-income link |

**Not run at the end:** `pnpm build` in normal mode (the type-check and the emulator-mode build both passed), and the CI workflows themselves. The test image `nf-qa-backend:hr004` (583 MB) built for the PDF checks may still be in Docker's store: `docker rmi nf-qa-backend:hr004` once Docker Desktop is running again.

## Manual test

The browser tests and the chain test (the same ones CI runs):

```bash
# backend/ with the emulators running (firebase emulators:start --only firestore,auth --project demo-nomadfinance, from frontend/)
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 \
  FIREBASE_PROJECT_ID=demo-nomadfinance GCLOUD_PROJECT=demo-nomadfinance \
  python -m pytest tests/integration/api/test_cross_pillar_regression.py tests/integration/api/test_fib_log.py -q
cd ../frontend
VITE_API_BASE_URL=http://127.0.0.1:4173 pnpm exec vite build --mode emulator
pnpm exec tsc -p e2e
firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm test:e2e"
```

**Windows PowerShell:** set the variables with `$env:NAME = "value"` first, and use `npx playwright test` if `pnpm` is blocked. Stop anything on ports 4173, 8085 and 9099 first. The PDF render test of QA-A-03 skips itself where Pango is not installed; to run it on Windows: `docker run --rm -u 0 -v "<repo>/backend:/work" -w /work --entrypoint sh <image built from backend/Dockerfile> -c "pip install -q pytest && python -m pytest tests/unit/services/test_fib_report_html.py -q"` (in Git Bash prefix `MSYS_NO_PATHCONV=1`).

By hand (the country notice): sign in as a worker whose profile country is Singapore, upload a contract that is plainly from Korea with the selector left on Singapore, and read the notice at the top of the report; press its button and the report is made again for Korea.

## Definition of Done (Test-only / QA task)

- [x] **A test fails when the behaviour is broken**: each new test was run against its broken code once and failed (the notice, the upload message, the amount limit, the reload, the PDF rows, the verified-income link, the API limit); the restored code passes. See `docs/evals/regression-suite-a-v2.md`
- [x] **Passes in CI**: the same chains CI runs were run locally (above); not yet seen on GitHub
- [x] Bugs found are filed with severity and repro steps (P0 none; P1 and four P2 fixed; the rest logged for later)
- [x] Report committed under `docs/evals` (`regression-suite-a-v2.md`)
- [ ] Tracker finish line "all P0 / P1 bugs found are filed with repro steps": met in the files; the P1 is closed only when this branch is merged
- [ ] A signed-in run on production (D-274)
- [ ] Wording read by native speakers (D-275)
- [ ] Reviewed by a teammate (Aditya)

## Commit

Branch: `fix/regression-suite-a` (already checked out).

```
test(regression): add regression suite A and fix its five bugs
Refs: NF-HR-004
```

The header is 65 characters (the limit is 72). To keep each fix easy to review or drop, the same work can go in six commits, all with `Refs: NF-HR-004`:

```
fix(contract): warn when a contract is from another country
fix(contract): say when an upload is not a contract
fix(fib): keep a PDF row's label and value on one page
fix(frontend): reload a page whose code file is gone
fix(fib): refuse an entry over the amount limit
test(regression): add regression suite A and its test sheet
```

## For teammates

- **Aditya:** D-279 (two Scam history tests are intermittent on Windows) and D-278 (contrast) are yours; the browser tests now include `regression-languages.spec.ts`, which any new screen of these pillars can be added to.
- **Anyone adding a screen that reads Firestore:** `frontend/e2e/support/firestoreRest.ts` is how a browser test plays the backend's part.
- **Anyone writing a test that edits `config/feature_flags`:** put back what was there (see the fixture in `test_cross_pillar_regression.py`); the document is shared by every test and by a long-lived emulator.
