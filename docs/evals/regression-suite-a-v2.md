# Regression suite A (Devam) — Contract Shield, Financial Identity, Financial Coach

Task NF-HR-004, run 2026-10-10 on `fix/regression-suite-a`. This is the test sheet and the bug log. The task document is `docs/runbooks/NF-HR-004-regression-devam-suite.md`.

**Verdict.** One P1 found and fixed (a contract from another country was checked under the worker's profile country with no warning). Four P2 found and fixed with their tests. Two P2 filed (NF-HR-009 and NF-HR-002 follow-ups). No P0. After this branch merges there are **no open P0 or P1** from this suite. Nothing was run against a signed-in production account (see "Not covered").

## How it was run

| Part | What |
|---|---|
| Stack | Firebase Auth, Firestore and Storage **emulators**; the **real API** (`create_app()`, real routes, services, repositories, middleware, rate limiter); the **real frontend** (dev server for the sweeps, a production build for Slow 3G and the browser tests) |
| Gemini | **A stand-in**, so the runs repeat and cost no quota (Contract Shield: the repo's own scripted scenarios; Financial Identity: canned categories, bill reader and narrative; Coach: a small rule-based reader of the worker's answer, in all six languages). Real Gemini was not used: the free-tier daily quota ran out earlier the same day (D-267). What the model *says* is therefore not tested here |
| PDFs | Rendered by the **production image** (`backend/Dockerfile`, built and run locally): WeasyPrint cannot load its GTK libraries on this Windows PC, so every PDF below came from the container, with the real code |
| Data | The three demo workers of NF-P3-021 / NF-HR-003 (Priya SG→IN `hi`, Rajesh KR→IN `hi`, Miguel JP→PH `tl`), plus a new account per flow |
| Browsers | Chromium (Playwright). Viewports 360×740, 412×915, 768×1024, 1280×800 |
| Slow 3G | Chrome's network emulation, 400 kbit/s both ways, 400 ms latency, gzip, cold cache, on the production build |
| Languages | `en`, `hi`, `tl`, `id`, `ne`, `bn` |
| Production | Read-only: `gcloud` reads, public pages, unauthenticated API calls. No sign-in, no writes |

## Baseline (before any change on this branch)

| Suite | Result |
|---|---|
| Frontend unit | 135 files, **1,615 passed** |
| Backend, no emulators | **3,705 passed**, 193 skipped, **2 failed** (`test_scam_history.py`, Aditya's suite; see QA-A-08) |

## Test sheet

`P` = passed, `F` = failed (bug in the last column), `—` = not run in that column. "Auto" cases are in the repo and run in CI; "Scripted" cases were run by a throwaway script against the local stack (the script is not committed, the steps are the repro).

### Configuration (Firebase and Google Cloud, read-only)

| ID | Check | Result | Notes |
|---|---|---|---|
| CFG-01 | Every Firestore query of the three pillars against `frontend/firestore.indexes.json` | P | Only single-field indexes are used, plus the `coach_plans.departure_date` collection-group override that exists. No composite index is missing (the emulator does not enforce indexes, so this was read from the code) |
| CFG-02 | The same, against the **deployed** indexes of `nomadfinance-prod` | P | `departure_date` (collection and collection group) and `scam_checks.created_at` are deployed. Three composite indexes exist in production that are not in the repo file (`read`+`created_at`, `corridors`+`report_count`, `corridor_id`+`created_at`): Radar's, not these pillars' |
| CFG-03 | Cloud Scheduler `fib-recompute` and `coach-checkins` | P | Both enabled, last run status empty (= OK), next runs 2026-10-11 02:00 UTC |
| CFG-04 | The backend service account can sign download links; the APIs the three pillars need | P | `roles/iam.serviceAccountTokenCreator` on itself is granted; `iamcredentials`, `firestore`, `storage`, `cloudscheduler`, `secretmanager`, `run` are enabled |
| CFG-05 | The Dockerfile's PDF stack | P | The image builds; WeasyPrint loads; `fonts-noto-core` has Devanagari and Bengali; PDFs in six languages rendered (below) |
| CFG-06 | `firestore.rules` and `storage.rules` for these pillars | P | Owner reads `contracts`, `income`, `bills`, `savings`, `financial_profile`, `coach_sessions`, `coach_plans`, `scam_checks`; nothing is browser-writable but the profile fields (`signal_sharing` is a checked boolean pair); `extraction/current` is denied; Storage allows owner reads of `contracts`, `bills`, `exports` only. Rules tests: see "Checks" |
| CFG-07 | Hosting headers | P / see QA-A-04 | Service workers `no-cache`; `/assets/` immutable; every other path `no-cache`. A missing `/assets/…` file is answered with `index.html`, 200, **immutable** (what QA-A-04 builds on) |
| CFG-08 | Public API | P | `/health` 200; every signed-in route answers 401 with no or a bad token (v1: `{"detail"}`, v2: the standard envelope) |
| CFG-09 | Cloud Run service (revision, env names, min instances) | **Not checked** | `gcloud run services describe` was refused by the permission classifier; not retried. D-276 |
| CFG-10 | The storage bucket | note | `asia-south1`; **soft delete keeps deleted files 7 days**, so "delete my account" removes files from the app at once but not from the bucket for a week (D-280) |

### Contract Shield (Chromium, English unless a column says otherwise)

Scripted cases C-01…C-13 ran at 360, desktop, 412 and 768 in English and at 360 in `hi`, `tl`, `id`, `ne`, `bn`; see "Languages" for the last five.

| ID | Case | 360 | Desktop | Notes |
|---|---|---|---|---|
| C-01 | Valid PDF uploads, the steps show live, a report appears | P | P | Gauge, counts, summary, clause list, complaint letter |
| C-02 | Report content: score, counts 3/2/3, clauses, summary, letter, copy and print buttons | P | P | |
| C-03 | Switching the report language translates once; switching back asks for nothing | P | P | One `POST …/reports/tl` |
| C-04 | The same file again is reused, one contract in the history | P | P | |
| C-05 | A Korean contract with the worker's own country (SG) left selected | **F** | **F** | **QA-A-01** (checked under Singapore law, no warning). Fixed |
| C-06 | A photo with no document in it | **F** | **F** | **QA-A-02** ("Something went wrong"). Fixed |
| C-07 | A text file, and a file over 10 MB, refused before sending | P | P | |
| C-08 | A photo too unclear: asks for a better one, does not analyse | P | P | |
| C-09 | AI service busy: the failing step is shown, Try again finishes, the file is not uploaded twice | P | P | |
| C-10 | Copy letter says so; Download as PDF opens the print view with no pop-up warning | P | P | |
| C-11 | History lists every check; a report opens from its link and from a reload | P | P | |
| C-12 | Another worker's contract number shows "could not be found" | P | P | Also checked on the API (A-02) and in Firestore rules (A-02d) |
| C-13 | No signal during an upload: a plain message; the next try works | P | — | |

### Financial Identity

| ID | Case | Result | Notes |
|---|---|---|---|
| F-01 | A new worker's dashboard: calm empty states, no error | P | |
| F-02 | Logging income shows "Logged." and the entry reaches the activity feed | P | |
| F-03 | Income `''`, `abc`, `-5`, `0`, `1e3` refused with the right message, nothing stored; `1,000.50` stored as 1000.50; no category refused; JPY `10.5` refused | P | `10.555` was read as 10,555 (dot-grouped thousands, D-281); since 2026-10-15 it is refused as too many decimals |
| F-03h | Income `99999999999999` | **F** | **QA-A-05** (stored). Fixed: refused as "too large" in the form and by the API |
| F-04 | A bill typed in with no category waits; "Sort my bills" sorts it | P | |
| F-05 | Savings in and out | P | |
| F-06 | The Transfer tab explains and links to Remittance X-Ray | P | |
| F-07 | Bill photo: not a bill, unreadable, readable, wrong file type | P | |
| F-08 | Export with no score yet is explained, no PDF offered | P | |
| X-01…05 | A worker with a profile: dashboard (score, four indicators, chart), Generate PDF, Download (a real PDF), Preview, Generate again | P | |
| PDF-1 | The report in `en`, `hi`, `tl`, `id`, `ne`, `bn` (production image) | **F** in 3 languages | **QA-A-03**: in `tl`, `hi` and `bn` a value was left at the foot of page 1 and its label at the top of page 2. Fixed |
| PDF-2 | Holder name `Priya Test & <Co>` | P | Printed as text, not as markup |

### Financial Coach

| ID | Case | Result | Notes |
|---|---|---|---|
| K-01 | A worker with no plan sees the start screen (and "What we already know" when the profile has answers) | P | |
| K-02 | The interview, 11 questions, to the review | P | |
| K-03 | The review lists every answer; "Yes, that is right" goes to the score | P | |
| K-04 | The score screen: score 90, band, "not financial advice" | P | |
| K-05 | "Make my 90-day plan" shows progress, then the plan opens | P | |
| K-06 | The plan: header, warnings, budget, remittance, weeks | P | |
| K-07 | The plan PDF | P | From the production image, in `en`, `hi`, `tl`, `bn`, for Priya, Miguel and Rajesh. Not downloadable on this PC (no Pango) |
| K-08 | Reloading mid-interview: "Welcome back", answers kept; Continue; start-over asks first | P | |
| K-09 | The Coach language switch keeps the answers and the step | P | |
| K-10 | An off-topic message is turned back; nothing is stored from it | P | |
| K-11 | "Ignore all previous instructions…" in an answer: no prompt leaks | P | |
| K-12 | A reply that fails before it starts, and one that fails half way: plain words, the answer is kept, Try again works | P | |
| K-13 | Offline: the answer is kept on the phone with a notice and goes when the signal returns | P | |

### Dashboard, tour, flags (360 px)

| ID | Case | Result |
|---|---|---|
| D-01…05 | The tour opens once; Next/Back; Tab stays inside and the page does not scroll; Escape and Skip end it for good, a tap inside does not | P |
| D-06 | Both modules off: no tour, `/coach` and `/scam-check` leave, the API answers 404 in the standard envelope, the dashboard still renders | P |
| D-07 | Dashboard height at 360×740, six languages | **F** in `tl` | **QA-A-06**: `en` 1,455, `hi` 1,449, `id` 1,455, `ne` 1,432, `bn` 1,452, **`tl` 1,506** against the 1,480 limit of NF-HR-002 |

### Screens × languages × viewports (sweep)

12 screens (dashboard, contract upload, history, report, identity, log, export, Coach home, plan, two check-in states, profile) × 6 languages × 4 viewports = **288 page loads**, one worker, light theme. Each load was checked for: sideways overflow, raw translation keys, `{{…}}` / `undefined` / `NaN`, an error screen, failed API calls, console errors, the page's `lang`, and axe (WCAG A and AA, serious and critical).

| Check | Result |
|---|---|
| Sideways overflow, any viewport | **0** |
| Raw translation keys, empty placeholders | **0** |
| Error screens | **0** |
| Failed API calls | only the expected `GET /fib/report/export` 404 when nothing has been exported yet (it also prints one console line each time, QA-A-09) |
| Console errors | none other |
| axe serious or critical | colour contrast only, three families: QA-A-07 |
| Static i18n audit (6,623 strings) | placeholders identical in every language; no empty value; no string left in English |

### Slow 3G (production build, cold)

| Check | Result |
|---|---|
| All 11 screens × `en`, `hi` | P. The first screen (dashboard) is usable in **11.5 s** cold; later screens about 2.8 s from cache |
| Upload and analysis, Financial Identity logging, a Coach interview, all on Slow 3G | P (the few scripted failures were fixed waits shorter than a 3G page, not product failures) |

### API and data (scripted, A-01…A-08)

| ID | Case | Result |
|---|---|---|
| A-01 | 21 signed-in routes × 4 bad credentials: always 401, never 5xx | P |
| A-02 | A second worker cannot analyse, translate, read or answer another's contract, plan, PDF, session, check-in or messages; nor read the contract from Firestore (403) | P |
| A-03 | Bad input never gives a 5xx: empty/wrong/oversize/garbage uploads, unknown country (UAE refused), language, job, income edge cases, markup in a name, Coach bodies | P. Findings: amounts without a limit (QA-A-05) |
| A-04 | A single odd entry and the profile | note: `income_stability` 67 → 0 with one entry of SGD 99,999 (D-281) |
| A-06 | Opt-in signals in the profile, the activity feed, opt-out removes the section from the next export | P |
| A-07 | A new Coach interview offers the contract's salary with its source | P |
| A-08 | `DELETE /users/me` removes contracts, income, bills, savings, profile, Coach and scam data | P |

### Other

| ID | Case | Result |
|---|---|---|
| S-01 | A tab opened before a release asks for a page file that no longer exists | **F** QA-A-04 (a dead end: "Try again" cannot recover). Fixed |
| CHAIN | One worker through the three pillars (contract → verified income → Coach offer → profile → feed → deletion) | P, now automatic (`test_cross_pillar_regression.py`) |

## Bugs

Severity: **P0** blocker (a main path is broken, data is lost or exposed, a wrong legal or money answer is shown with no sign), **P1** major (a feature's main path gives a wrong result or fails for a real group of workers), **P2** minor. Filed in this file; no GitHub issues were created.

| ID | Sev | Where | What | Repro | Status |
|---|---|---|---|---|---|
| **QA-A-01** | **P1** | Contract Shield | The upload form always sends the profile's country, which wins over the country the contract shows. A Korean contract from a worker whose profile says Singapore is checked under Singapore law, the report says so only in a small field, and nothing tells the worker. The "Finding where you work" step has no effect on the web app | Profile `host_country` SG. Upload a contract whose detected country is Korea, leave the country selector as is. The stored contract has `host_country: SG`, `detected.host_country: KR` | **Fixed**: a notice on the report ("This contract looks like it is from South Korea, but it was checked against Singapore labor law") with a button that checks it again for the detected country; on the upload result and on a past check. Tests: 3 browser, 3 unit |
| QA-A-02 | P2 | Contract Shield | A photo with no document in it (the reader answers 422) shows "Something went wrong. Please try again." Trying again with the same file cannot help | Upload a photo of something that is not a contract | **Fixed**: "That doesn't look like a contract. Upload a PDF or a clear photo of the whole contract." (6 languages). Tests: 1 browser, 5 unit |
| QA-A-03 | P2 | Financial Identity PDF | Rows are laid out as a grid, so a page break could split one: the value at the foot of page 1, its label at the top of page 2 (seen in `tl`, `hi`, `bn`, in the shared-activity section) | Export a profile with shared activity in Hindi, Bengali or Tagalog; read the end of page 1 | **Fixed**: each row is its own unit that cannot break. Tests: HTML rule (always) and a render test over 14 page-end positions × `en`, `hi`, `bn` (needs Pango: it failed on the old layout in the production image and passes on the new) |
| QA-A-04 | P2 | All pages | A tab opened before a release fails on every page it has not shown yet ("Something went wrong") and **Try again does not recover** (the browser keeps the failed file until the page is loaded again). Only a manual reload helps. Mostly tabs with no service worker, but a phone's installed app can stay open for days | Open the dashboard; remove `assets/ContractUpload-*.js` (or answer it with `index.html`); open Contracts; press Try again | **Fixed**: when the failure is a missing page file, Try again reloads the page. Tests: 9 unit |
| QA-A-05 | P2 | Financial Identity | No upper limit on an entry: `99999999999999` is stored; the API takes `1e15`. One entry of SGD 99,999 took the income stability of a worker with three steady months from 67 to 0 | Log income `99999999999999` | **Fixed**: 1,000,000 per entry (100,000,000 for yen and won), refused in the form ("That amount is too large…", 6 languages) and by the API (422). Tests: 5 unit, 4 API, 2 browser |
| QA-A-06 | P2 | Dashboard | In Tagalog the 360 px home is 1,506 px against the 1,480 px (two screens) of NF-HR-002; the other five languages are within it. D-269 already warned a long language might pass it | Open `/dashboard` at 360×740 in Tagalog with a populated worker | **Filed** (D-277): not a tiny fix without a native read of shorter Tagalog |
| QA-A-07 | P2 | Several screens | Text colour contrast below WCAG AA: (1) the grey `text-subtle` on small labels, 3.0:1 (sidebar "Menu", the dashboard cards' headings); (2) the contract report's "What the contract says" label on the caution tint, 4.3:1; (3) the green status text "Good", 3.3:1 on the Financial Identity screens | Run axe on `/dashboard`, `/contract/{id}`, `/identity` | **Filed** (D-278): NF-HR-009 owns the app-wide pass |
| QA-A-08 | P3 | Tests | `test_scam_history.py` (2 tests, Aditya's suite) is intermittent on Windows: the clock ticks every ~15 ms, so five checks made in a row can share one `created_at` and the newest-first order cannot be told. Failed in 2 of 3 local runs; passes on Linux | Run the file twice on Windows | **Filed** (D-279) |
| QA-A-09 | P3 | Financial Identity | The export screen asks for the latest report on every visit and the 404 "nothing exported yet" is also printed in the browser console | Open `/identity/export` with no export | Noted, harmless (D-281) |

## Not covered

- **Real phones and real mobile networks.** Everything above is emulation (D-72 still stands).
- **A signed-in production run.** Sign-in cannot be done on someone's behalf: D-274 is the checklist (a contract upload and report, the Financial Identity PDF in `hi`, `bn`, `ne`, a Coach plan PDF, the tour).
- **What the model writes.** The stand-in answers for it, so the quality of the explanation, the narrative and the plan text in each language, and the Coach's reading of free text, are for the live evals (D-267, NF-FC-024).
- **The Cloud Run service** (CFG-09, D-276).
- **Safari and Firefox, Radar, Remittance, Scam Analyzer, PWA install and push**: NF-HR-005 and NF-HR-006.

## Checks

See the task document: it carries the results of the CI chains run for this branch.
