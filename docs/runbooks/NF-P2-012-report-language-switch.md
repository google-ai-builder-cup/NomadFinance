# NF-P2-012 — Contract Shield: Language Switcher on Report

## Summary

A worker can now read the Contract Health Report in any of the six languages (en, hi, tl, id, ne, bn) without uploading the contract again. A language selector sits above the report; choosing one shows that language.

- A language that is already stored (listed in the analysis' `report_languages`) is read from Firestore, `reports/{language}`.
- A language that is not stored yet is asked of the backend, `POST /api/v1/contracts/{id}/reports/{language}`. The backend translates the English report once (a few seconds), stores it and returns it. The next visit finds it stored.
- A language already seen in this visit comes from the app's cache: no request at all.
- Only the report changes. The app language and the profile's `preferred_language` stay as they are (D-40).

No backend change, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `frontend/src/services/contractService.ts` | `switchReportLanguage()`: `POST .../reports/{language}`, no body |
| `frontend/src/hooks/useContract.ts` | `reportQueryOptions()` (Firestore or backend, one cache key per language), `retryReportLoad()`, `reportPlaceholder()`; `useContractReport()` now takes the stored languages |
| `frontend/src/components/contract/ReportLanguageSwitcher.tsx` (new) | Labelled native `<select>` with the six languages in their own scripts |
| `frontend/src/components/contract/ReportView.tsx` (new) | The report block: switcher, loading, errors, "translating" note, `ReportCard`; owns the chosen language |
| `frontend/src/pages/contract/ContractUpload.tsx` | The report block replaced by `<ReportView>` (293 to 267 lines, which also settles D-61) |
| `frontend/src/utils/reportLanguage.ts` (new) | `reportFailureKey()`: which message a failed report load shows |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `contract.report.language`, `languageHint`, `switching`, `switchOutOfDate` |
| `frontend/src/hooks/useContract.test.ts`, `frontend/src/utils/reportLanguage.test.ts` (new) | 11 tests |
| `docs/api/endpoints.md` | How the app uses the reports endpoint; a section on switching the language |

`package.json`, `pnpm-lock.yaml`, the workflows, `firebase.json` and the rules files are unchanged.

## Decisions

1. **One hook, two sources.** `useContractReport` reads Firestore for a stored language and the backend for any other, under one query key per language. The page does not need to know which. A stored language whose document is missing stays `null` ("not ready yet", NF-P2-011's message); it is never translated by accident.
2. **The report language is independent of the app language.** Switching the report does not change the interface or the profile (D-40). A worker can read the report in Nepali inside an English screen.
3. **A query, not a mutation, for the translation.** The endpoint is idempotent (a stored report is returned at once), and a query gives the per-language cache and the placeholder below for free.
4. **No automatic retry of a backend answer.** The backend already tries Gemini three times, so a second automatic try would only delay the message. The worker taps Try again. A failed Firestore read is still retried once, as elsewhere.
5. **The previous language stays on screen while a new one loads**, dimmed, with "Translating your report…" (`role="status"`, `aria-busy`). Only for the same contract: another contract's report is never used as a stand-in.
6. **A `409` has no Try again.** It means the analysis is not current, and repeating the call cannot fix that: the message asks the worker to check the contract again.
7. **The switcher is disabled while a language loads**, so a second choice cannot start a second translation.
8. **The position of a language in `report_languages` is never used.** The list is sorted alphabetically, not source-first (D-60); the code only asks whether a language is in it.
9. **`lang` on the report block**, so a screen reader speaks the report in its own language (the same reason as D-39).
10. **The report block moved to `ReportView.tsx`.** `ContractUpload.tsx` was over the ~300-line guideline (D-61). Keeping the chosen language inside `ReportView` also resets it when the worker checks another contract, without extra code.
11. **The query options are a plain function**, `reportQueryOptions`, so the behaviour is tested without React. The repo has no jsdom or Testing Library, and adding them would edit `package.json`, a shared file.

## Flow

```
Report shown in analysis.report_language (Firestore: reports/{language})
Worker picks a language in the selector
  in report_languages?  yes -> getDoc reports/{language}                (instant)
                        no  -> POST /api/v1/contracts/{id}/reports/{language}   (a few seconds)
  cached this visit?    yes -> no request
  while loading         -> previous language of this contract, dimmed, "Translating your report…"
  success               -> ReportCard in the new language, block lang="{language}"
  failure               -> message by status, Try again (except 409), selector stays usable
```

## All commands, in order

From `frontend/`. PowerShell and bash are the same.

### 1. The checks CI runs (`.github/workflows/frontend-ci.yml`)

```bash
pnpm install --frozen-lockfile
pnpm lint
pnpm format:check
pnpm build
pnpm test:rules
```

`pnpm build` needs the Firebase values CI uses; the placeholders are enough:

```bash
VITE_FIREBASE_API_KEY=ci-placeholder VITE_FIREBASE_AUTH_DOMAIN=nomadfinance-prod.web.app \
VITE_FIREBASE_PROJECT_ID=nomadfinance-prod VITE_FIREBASE_APP_ID=ci-placeholder pnpm build
```

```powershell
$env:VITE_FIREBASE_API_KEY="ci-placeholder"; $env:VITE_FIREBASE_AUTH_DOMAIN="nomadfinance-prod.web.app"
$env:VITE_FIREBASE_PROJECT_ID="nomadfinance-prod"; $env:VITE_FIREBASE_APP_ID="ci-placeholder"; pnpm build
```

`pnpm test:rules` needs Java 21 and `firebase-tools` (CI installs both).

### 2. The unit tests (not run by CI, D-46)

```bash
pnpm exec vitest run src
```

### 3. Try it by hand

Needs the backend and Firebase emulators running as in `docs/runbooks/NF-P2-010-contract-processing-animation.md`, and a signed-in worker.

1. Upload a contract, with Hindi (`hi`) as the report language, and wait for the report.
2. Choose **English** in the selector above the report. `reports/en` is stored, so it appears at once, with no network call to the backend (browser Network tab).
3. Choose **नेपाली**. The report stays, dimmed, with "Translating your report…", then shows in Nepali after a few seconds (one `POST .../reports/ne`).
4. Choose **हिन्दी**, then Nepali again. Both appear at once, with no request.
5. Reload the page and repeat step 3 for a language that is now stored: it comes from Firestore.
6. Stop the backend, choose a language not yet seen: the error message and Try again appear, and the selector still works.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `pnpm install --frozen-lockfile` | Passes; `package.json` and `pnpm-lock.yaml` unchanged |
| `pnpm lint` (`--max-warnings 0`) | Passes |
| `pnpm format:check` | Passes |
| `pnpm build` (`tsc -b` and Vite) | Passes; the chunk-size warning is D-45, as before |
| `pnpm test:rules` | 100 passed |
| `vitest run src` | 51 passed (11 new) |
| `pnpm audit --prod --audit-level high` (as `security-scan.yml`) | Exit 0; 2 moderate advisories, unchanged by this task |
| Render check of the switcher in all six languages (temporary test, removed) | Six options, the selected one marked, no untranslated key, disabled state works |
| Whole flow in a browser with a signed-in worker, real backend and Gemini | **Not run**: it needs sign-in, the backend and reasoning-tier Gemini quota (D-58). Step 3 above is yours |
| Mobile emulator and throttled network | Not run |

What the new tests prove: a stored language is read from Firestore and never calls the backend; a missing language calls the backend and never Firestore; going back to a language already seen makes no second request; a backend failure is not retried by itself; another contract's report never stands in as the placeholder; each failure status maps to the right message.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "The AI service is busy" after choosing a language | The translation call got 503. Try again after a minute; reasoning and classification quotas are shared (D-58) |
| "This report is out of date" | The backend answered 409: the analysis is not current. Check the contract again (analyze), then switch |
| The first report loads through the backend, not Firestore | `report_languages` was missing on the contract document. The backend returns the stored report at once, so it is correct, only one call slower |
| A language never loads and there is no error | Offline: the query waits for the connection. Reconnect; it resumes |
| The translation call fails everywhere but the upload works | `VITE_API_BASE_URL` missing in the build (D-44); stored languages still show |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind (native `<select>`, matching the upload form; no new package)
- [ ] Fully mobile responsive: `w-full` on a phone and `sm:w-64` above, but not tested in the DevTools emulator
- [ ] Works on slow network: not tested throttled; a translation shows its own progress note
- [x] Loading state: skeleton on first load, dimmed report with a status note while switching
- [x] Error states: busy, too slow, offline, out of date, and a failed Firestore read, each with Try again where it can help
- [x] i18n keys for all user-facing strings, all six languages
- [ ] Screenshots added to the PR: take them when opening it (selector, switching state, error state)
- [x] Accessibility: labelled `<select>` with a hint, `role="status"`, `aria-busy`, `lang` on the report, `role="alert"` on errors

## Commit and PR

Branch: `feature/contract-report-lang-switch` (already checked out).

Suggested commit message, one line plus the reference:

```
feat(contracts): switch the contract report between languages
Refs: NF-P2-012
```

PR title:

```
feat(contracts): switch the contract report language without re-uploading (NF-P2-012)
```

The PR description is in the section below.

## PR description

```markdown
## Summary

Contract Shield report language switcher (NF-P2-012). A worker can read the report in any of the six languages (en, hi, tl, id, ne, bn) without uploading the contract again.

- A stored language (listed in `report_languages`) is read from Firestore.
- A language not stored yet is translated once by the existing `POST /api/v1/contracts/{id}/reports/{language}`, then stored.
- A language already seen in the visit comes from the app's cache: no request.
- Only the report changes. The app language and `preferred_language` do not (D-40).

Refs: NF-P2-012

## Changes

- `contractService.switchReportLanguage()` and `reportQueryOptions()` / `useContractReport()` (`hooks/useContract.ts`): one query key per language, Firestore or backend as needed.
- New `ReportLanguageSwitcher` (labelled native `<select>`) and `ReportView` (switcher, loading, errors, report). `ContractUpload.tsx` now renders `<ReportView>` (293 to 267 lines; D-61).
- The previous language of the same contract stays on screen, dimmed, with a "Translating your report…" note while a new one loads. Another contract's report is never used as a stand-in.
- Failure messages by status; a `409` (analysis out of date) asks the worker to check the contract again, without a Try again button.
- 4 new i18n keys in all six languages; `lang` on the report block for screen readers.
- Docs: `docs/api/endpoints.md`, runbook `docs/runbooks/NF-P2-012-report-language-switch.md`.

## CI / CD

No change to `package.json`, `pnpm-lock.yaml`, workflows, `firebase.json` or the rules files, and no new dependency. The checks below are the ones in `frontend-ci.yml` and `security-scan.yml`, run locally in the same order:

| Workflow step | Result |
|---|---|
| `pnpm install --frozen-lockfile` | Pass, lockfile unchanged |
| `pnpm lint` (`--max-warnings 0`) | Pass |
| `pnpm format:check` | Pass |
| `pnpm build` (`tsc -b`, Vite) | Pass |
| `pnpm test:rules` | 100 passed |
| `pnpm audit --prod --audit-level high` | Exit 0 (2 moderate, not caused by this PR) |

Not part of CI (D-46), run by hand: `pnpm exec vitest run src`, 51 passed (11 new).

Merging to `main` triggers `frontend-deploy.yml` (build, Firebase Hosting deploy, live-site check). Nothing manual is needed after the merge. The translation call uses `VITE_API_BASE_URL`, already passed by that workflow (D-44).

## Not verified

- The whole flow in a browser with a signed-in worker, the real backend and Gemini. It needs reasoning-tier quota (D-58). The manual steps are in the runbook.
- Mobile emulator and throttled network.
- The hi, tl, id, ne and bn texts were written without a native speaker (same caveat as D-41).

## Screenshots

To add: the selector, the switching state, the error state.
```

## Not covered here

- Expand/collapse, risk-score tooltip, sticky columns, mobile tuning: NF-P2-023.
- Complaint letter preview and download: NF-P2-013.
- Listing and reopening earlier contracts (`ContractList.tsx` and `ContractReport.tsx` are empty stubs): no task covers it yet, so the report is only reachable right after an analysis.
- A component-level test of `ReportView` (no jsdom or Testing Library in the repo).
- Running the frontend unit tests in CI: D-46.
