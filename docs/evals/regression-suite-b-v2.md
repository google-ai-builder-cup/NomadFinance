# Regression suite B (Aditya) — Remittance X-Ray, Scam Analyzer, cross-browser

Task NF-HR-005, run 2026-10-13 on `fix/regression-suite-b`. This is the test sheet and the bug log. The task document is `docs/runbooks/NF-HR-005-regression-aditya-suite.md`.

**Verdict.** One P1 found and fixed (the Scam Analyzer could not start on a browser with no `AbortSignal.timeout`, such as Safari before 16). Four P2 found and fixed with their tests (native digits refused in three forms, a failed advice that talked about a contract, a transfer logged twice by two quick taps, a render error on Safari before 15.4). No P0. After this branch merges there are **no open P0 or P1** from this suite. Nothing was run against a signed-in production account, a real iPhone or a real Android phone (see "Not covered").

## How it was run

| Part | What |
|---|---|
| Stack | Firebase Auth and Firestore **emulators**; the **real API** (`create_app()`, real routes, services, repositories, middleware, rate limiter); the **real frontend**, as a production build served by `vite preview` for every cross-browser run (the dev server gives Firefox module-loading artefacts that are not in the build) |
| Gemini | **A stand-in** (the repo's latency client with the delay at 0), so runs repeat and cost no quota. The recommendation has four modes (`ok`, `busy`, `wrong` provider, `blank`) switched from outside. What the model *says* is not tested here |
| Rates | The World Bank survey data in the emulator seed (39, 29, 35, 42, 44 and 32 providers for SG→PH, SG→IN, AU→IN, MY→ID, JP→PH, AU→PH) |
| Engines | Chromium, Firefox and WebKit, each as a desktop window (1280×800) and as a phone (Chromium: the Pixel 5 profile; WebKit: the iPhone 13 profile; Firefox has no mobile emulation, so its "phone" is a 393×727 window) |
| Slow 3G | Chrome's network emulation, 400 ms latency, 50 KB/s, cold cache, on the production build |
| Languages | `en`, `hi`, `tl`, `id`, `ne`, `bn` |
| Production | Not touched |

## Baseline and after

| Suite | Result |
|---|---|
| Frontend unit, after | **1,689 passed** (the new files: `digits`, `timeoutSignal`, `RemittanceCompare.log`; cases added to `corridors`, `fibForm`, `coachInput`) |
| Frontend end-to-end, default projects (`desktop`, `mobile`), after | **212 passed** (8 new in `e2e/remittance.spec.ts`, on both projects) |
| Frontend end-to-end, opt-in `firefox` and `webkit-iphone`, on the remittance, scam, dashboard and smoke specs | **66 passed** |
| Backend | Not run: no backend file changed |

## Test sheet

`P` = passed, `F` = failed (bug in the notes). "Auto" cases are in the repo and run in CI (`e2e/remittance.spec.ts`, `e2e/scam-*.spec.ts`); "Scripted" cases were run by a throwaway script against the local stack (the script is not committed; the steps are the repro). The six columns of the per-engine tables are Chromium desktop and phone (C, C📱), Firefox (F, F📱) and WebKit (W, W📱); each shows the result of the final run, after the fixes, and a bug id in the notes says where a case failed before one.

### Remittance X-Ray (scripted R-01…R-14, six engine × viewport columns)

| ID | Case | C | C📱 | F | F📱 | W | W📱 | Notes |
|---|---|---|---|---|---|---|---|---|
| R-01 | Opens on the worker's own corridor with an empty state | P | P | P | P | P | P | SG→IN for the test worker |
| R-02 | 500 on the default corridor: a ranked comparison, best first | P | P | P | P | P | P | Auto |
| R-03 | Every corridor compares at its survey amount (shortcut button) | P | P | P | P | P | P | All six |
| R-04a | `1,000` | P | P | P | P | P | P | Read as 1000 |
| R-04b | `645,50` (European decimal) | P | P | P | P | P | P | Superseded: a comma is no longer read as a decimal; `645,50` is refused with a "use a dot" message. |
| R-04c | `1 000` (space-grouped) | P | P | P | P | P | P | |
| R-04d | `५००` (Devanagari digits) | P | P | P | P | P | P | **QA-B-01**. The old parser refused it |
| R-04e | `৫০০` (Bengali digits) | P | P | P | P | P | P | QA-B-01 |
| R-04f | `٥٠٠` (Arabic-Indic digits) | P | P | P | P | P | P | QA-B-01 |
| R-04g | `５００` (full-width digits) | P | P | P | P | P | P | QA-B-01 |
| R-04h | `500 SGD` | P | P | P | P | P | P | Refused: "Enter the amount as a number, for example 500." Nothing sent |
| R-04i | `-5`, R-04j `0`, R-04k letters, R-04n `1e3` | P | P | P | P | P | P | Same message, nothing sent |
| R-04l | `500.123` (three decimals) | P | P | P | P | P | P | Read as 500,123 (dot-grouped thousands by design, as in D-281), so refused as over the limit |
| R-04m | A number above the limit | P | P | P | P | P | P | "Enter at most SGD 6,450." |
| R-04o | Paste with a newline and a tab | P | P | P | P | P | P | |
| R-05 | Double-click on Compare: one comparison, no error | P | P | P | P | P | P | |
| R-06 | An amount outside the survey shows the "estimated" notice | P | P | P | P | P | P | |
| R-07 | Log a transfer: the row says Logged, exactly one transfer stored | P | P | P | P | P | P | Counted in Firestore |
| R-07b | A new comparison starts with nothing logged | P | P | P | P | P | P | |
| R-07c | Two taps on "I sent this" in the same instant store one transfer | P | P | P | P | P | P | **QA-B-03**. Added with the fix. Auto |
| R-08-ok | Advice, model answers | P | P | P | P | P | P | Auto |
| R-08-busy | Advice, model busy (503) | P | P | P | P | P | P | The shared "busy" wording, no mention of a contract |
| R-08-wrong | Advice names a provider other than the ranked one (502) | P | P | P | P | P | P | **QA-B-02**. The card used the contract pipeline's wording. Auto |
| R-08-blank | Advice with no text (502) | P | P | P | P | P | P | QA-B-02 |
| R-09 | Trend chart and period buttons | P | P | P | P | P | P | |
| R-10 | A link from the plan (`?corridor=SG-IN&amount=500`) fills and runs once | P | P | P | P | P | P | Auto |
| R-11 | A bad link (`corridor=XX&amount=-1`) is ignored | P | P | P | P | P | P | Auto |
| R-12 | An out-of-range link amount is not run | P | P | P | P | P | P | Auto |
| R-13 | No sideways scroll | P | P | P | P | P | P | Auto, 360 px |
| R-14 | No uncaught page errors during the run | P | P | P | P | note | note | WebKit only: the Firestore emulator's streaming channel is refused by CORS under WebKit; nothing in the app. D-326 |

Not in the sheet: the flagged-provider badge, the savings callout and the six languages of the comparison page were not walked in this run (see "Not covered").

### Scam Analyzer (scripted S-01…S-16, six columns)

All 23 cases passed in all six columns.

| ID | Case | Result | Notes |
|---|---|---|---|
| S-01 | Opens with an empty form and the privacy note | P | |
| S-02 | A scam message gets a verdict, the tricks and next steps | P | |
| S-03 | The same message again is answered at once | P | 51 ms (the stored check) |
| S-04 | A harmless message is not called a scam | P | |
| S-05 | Empty and whitespace-only cannot be sent | P | |
| S-06 | 4,000 characters is accepted | P | |
| S-07 | 4,001 characters is refused in the form, not by a server error | P | Button disabled |
| S-08 | A phone number and a link are masked in the result | P | |
| S-09 | A screenshot (PNG) is read and judged | P | |
| S-10a-d | A text file called `.png`; an empty file; a PDF; an image over 5 MB: each refused with a message | P | "Use a JPEG, PNG or WebP screenshot…", "…under 5 MB" |
| S-11 | The share link fills the box and does not send it | P | |
| S-12 | History lists the checks, opens one and comes back | P | |
| S-13 | Warn other workers: reported once, then it says it is done | P | |
| S-14 | Read aloud: the control does not break when the browser has no voice | P | |
| S-15 | The verdict in `hi`, `tl`, `id`, `ne`, `bn`: no raw key, no sideways scroll | P | |
| S-16 | No uncaught page errors | P | 42 Firestore-emulator channel errors were ignored in the run that printed them (see R-14) |

The only Scam Analyzer defect (QA-B-04) is not in this table because it needs a browser with no `AbortSignal.timeout`, which none of the three installed engines is. It was found by the compatibility audit and has its own unit test.

### API and data (scripted A-R01…, 63 checks)

| Group | Result |
|---|---|
| Compare: no body, `{}`, unknown corridor, a UAE corridor, amount 0, negative, string, `null`, list, bool, huge, tiny, invalid JSON, `text/plain` | 422 each, never 5xx (A-R02…R21) |
| Compare: a numeric string `"500"`, an extra field | 200 (the model is lenient by design) |
| Compare: no token, a junk token | 401 |
| Compare: six corridors × five amounts (1, 200, 500, 5,000, 100,000) | 200 inside the corridor's limits (a quarter of the lower survey amount to ten times the upper) and 422 outside them, with `estimated` true only away from the survey amounts. 13 cells first read as "failed" were my wrong range assumption, e.g. 200 JPY for JP→PH is below its 4,250 minimum and 100,000 SGD is above the 6,450 maximum for SG→PH; the refusal is right |
| Trends: days 7, text, 0, no or bad corridor | 422; 365 → 200 |
| Savings: months 0, 1,000, negative or huge amount, no parameters | 422 |

### Slow 3G (production build, cold)

| Step | Time |
|---|---|
| Remittance page, cold, until the form can be used | 11.4 s |
| Compare → ranked results | 1.9 s |
| Results → advice | 2.3 s |
| Scam Analyzer page (app already loaded) → form usable | 5.9 s |
| Paste → verdict | 1.7 s |

The first screen is the cost of the app's code on 50 KB/s; the later steps wait on the API only. This is in line with suite A's 11.5 s dashboard.

### Compatibility audit (read from the code, 2026-10-13)

| API | Where | Needed from | Finding |
|---|---|---|---|
| `AbortSignal.timeout` | `scamService.ts` | Safari 16, Chrome 103, Firefox 100 | **QA-B-04**, fixed by `timeoutSignal` |
| `Array.prototype.at` | `flaggedParties.ts` | Safari 15.4, Chrome 92 | **QA-B-05**, fixed |
| `\d` in amount parsing | three parsers | — | **QA-B-01**: ASCII-only in JS |
| `crypto.randomUUID` | `idempotency.ts` | Safari 15.4 | Guarded, falls back |
| `requestIdleCallback` | `main.tsx` | not in Safari | Guarded |
| `navigator.share` with files | `coachPdf.ts` | Safari 15, Chrome 89; not in desktop Firefox | Guarded with `canShare`; the button falls back to a download |
| `navigator.clipboard` | copy buttons | secure contexts | Tested in the three engines |
| `speechSynthesis` | read aloud | all three, voices differ | S-14 (no voice) passes |
| `SpeechRecognition` / `webkit…` | `voiceInput.ts` | not in Firefox | Feature-detected; the microphone is not offered |
| `replaceAll` | six components | Safari 13.1 | Fine |
| `dvh` units | `AppShell`, `Sidebar`, `CoachChat`, `HeatmapMap` and more | Safari 15.4, Chrome 108 | The seven full-height pages write `min-h-screen` before `min-h-dvh`; the Sidebar's height and the Coach log's two heights have no fallback: D-325 |

## Bugs

Severity: **P0** blocker (a main path is broken, data is lost or exposed, a wrong money or legal answer is shown with no sign), **P1** major (a feature's main path fails for a real group of workers), **P2** minor. Filed in this file and in `docs/deferred-items.md`; no GitHub issues were created.

| ID | Sev | Where | What | Repro | Status |
|---|---|---|---|---|---|
| **QA-B-04** | **P1** | Scam Analyzer | `analyzeScam` called `AbortSignal.timeout`, which does not exist before Safari 16, Chrome 103 and Firefox 100. The call threw before any request was made, so on an iPhone 7 or older (which stop at iOS 15) the Scam Analyzer showed an error for every message and screenshot | Open `/scam-check` in a browser without `AbortSignal.timeout` (remove it in the console first), paste any message, press Check | **Fixed**: `timeoutSignal(ms)` uses it when present and an `AbortController` with a timer otherwise, and aborts with the same `TimeoutError`. Tests: 2 unit |
| QA-B-01 | P2 | Remittance, Financial Identity, Coach | The amount parsers used `\d`, which matches only 0 to 9. `५००`, `৫০০`, `٥٠٠` and `５００`, which a Hindi, Nepali, Bengali or Arabic keyboard types, were refused with "Enter the amount as a number". The same in the income, bill and savings forms and the Coach's money answers | Type `५००` in the amount of `/remittance`, press Compare | **Fixed**: `toAsciiDigits` reads Unicode decimal digits (12 blocks, and the Arabic decimal and thousands marks) as 0 to 9 before the existing parsing, in all three parsers. Tests: a new unit file, cases added to the three parsers' tests, 1 browser |
| QA-B-02 | P2 | Remittance | A failed written advice (the model named a provider other than the ranked one, or wrote nothing: 502) said "Something went wrong while checking your contract". The wording came from the contract pipeline | Set the model to answer a wrong provider, open a comparison, press Get advice | **Fixed**: `adviceFailureKey` gives the server-problem wording for 502 and keeps the shared busy and slow wording for 503 and 504. Tests: unit, 1 browser |
| QA-B-03 | P2 | Remittance | Two taps on "I sent this" in the same instant logged two transfers: the "Logged" state only arrives after the response, and the second tap passed the check. The worker's history and savings counted the transfer twice | Double-tap the log button of a provider (or two fast taps on a phone) | **Fixed**: a flag held for the length of the call; the end of the call (done or failed) releases it, so a failed log can be tried again. Tests: unit (two synchronous taps → one call; a failure allows a retry), 1 browser |
| QA-B-05 | P2 | Contract Shield report (found in the audit) | `flaggedParties.ts` used `Array.prototype.at`, which Safari 15.0 to 15.3 lacks. The flagged-parties section of a contract report threw while rendering and the error screen replaced the report | Open a contract report in a browser without `Array.prototype.at` | **Fixed**: `words[words.length - 1]`. Existing tests cover it. Not reproduced on a real old Safari |

## Not covered

- **Real phones.** No Android phone and no iPhone: **Safari on iOS was stood in for by WebKit with an iPhone 13 profile** (same engine and a touch device, not the same browser: no iOS keyboard, share sheet, install flow, address-bar resizing or 100 vh quirks). Chrome on Android was stood in for by Chromium with a Pixel 5 profile. The firefox "phone" column is a narrow window only.
- **Screens not walked in this run:** the flagged-provider badge, the savings callout, the trend chart in each language, and Remittance in `hi`, `tl`, `id`, `ne`, `bn` (the Scam Analyzer verdict was walked in all six, S-15).
- **What the model writes.** The stand-in answers for it, so the advice text in each language, and what the model says about a message, are for the live evals.
- **A signed-in production run** (D-274), and the Cloud Run service.
- **Radar, the Remittance → Coach handoff, PWA install, offline and push**: NF-HR-006. Contract Shield, Financial Identity and the Coach: NF-HR-004.
- **Browsers older than the ones above.** Firefox ESR and Samsung Internet were not run; the audit above is a reading of the code, not a test on those.

## Checks

See the task document: it carries the results of the chains run for this branch.
