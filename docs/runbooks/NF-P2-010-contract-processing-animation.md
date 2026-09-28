# NF-P2-010 — Contract Shield: Processing Animation

## Summary

While a contract is checked (30 s to 2 minutes, longer when Gemini is slow), the upload page now shows **which step the backend is really on** and a **skeleton of the report** that is coming. Before this, the worker saw one spinner line for up to two minutes.

- **Five steps on screen:** Reading your contract → Finding where you work → Looking up the labor law → Checking every clause → Preparing your report.
- **Driven by the backend, not a timer.** The page listens to `users/{uid}/contracts/{id}` with Firestore `onSnapshot`. A step turns "done" only when the backend has moved past it (NF-P2-007 writes `status` and `step` as it goes).
- **A slow step says so.** After 45 s on one step: "Still working. The AI service is busy right now…" (Gemini hangs at times, D-54).
- **A failure stops at its step,** with a message for the stored `error.code`. It offers "Try again" (analyze again, **no re-upload**) and "Check another contract". There is no "Try again" when retrying cannot help: unreadable photo, not a contract, no law data, no terms.
- **A lost answer still shows the result.** If the phone loses the HTTP answer, the result is rebuilt from the finished contract document.
- Accessible: an ordered list with `aria-current="step"`, hidden state words ("done", "in progress") for screen readers, one polite announcement per new step, the failure as `role="alert"`, and spinners and pulses only under `prefers-reduced-motion: no-preference`.
- All texts in the 6 languages. No backend change, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `frontend/src/utils/pipelineProgress.ts` (new) | Backend step → screen step, `progressView()` (the state of each step), failure message and "can retry" per error code, `requestFailureKey()` (message for a failed request with no stored error), `analysisFromDoc()` (result from the document) |
| `frontend/src/utils/pipelineProgress.test.ts` (new) | 30 tests: every backend step, uploading, failures by step and code, old failures and old results of the same file, messages by code and by HTTP status, result from the document |
| `frontend/src/components/contract/PipelineProgress.tsx` (was a stub) | The step list, stall hint, live announcement, failure box with actions |
| `frontend/src/components/contract/ReportSkeleton.tsx` (new) | Skeleton of the report: score header, risk badge, three counts, three clause rows |
| `frontend/src/components/ui/skeleton.tsx` (new) | shadcn `Skeleton` (`motion-safe:animate-pulse`, hidden from screen readers) |
| `frontend/src/services/contractService.ts` | `watchContractProgress()`: `onSnapshot` on the contract document |
| `frontend/src/hooks/useContract.ts` | Upload hook exposes `contractId` as soon as the upload returns; `useRetryAnalysis()`; `useContractProgress()` |
| `frontend/src/pages/contract/ContractUpload.tsx` | Shows the progress card and skeleton while working or after a failure; "Try again"; result from the document when the answer was lost; upload failures say "AI busy" / "AI too slow" instead of "server problem". The old one-line "analyzing" spinner is gone. 306 lines, accepted over the guideline (D-61) |
| `frontend/src/types/contract.ts` | `PipelineStep` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `contract.progress.*` (title, steps, states, stall hint, announcement, 8 failure messages); the now unused `contract.upload.analyzing` removed |
| `docs/pipelines/contract-shield.md`, `docs/deferred-items.md` | How the app shows progress; D-61, D-62 |

## Decisions

1. **Five screen steps for six backend steps.** The complaint letter and the translation are one step for the worker, "Preparing your report". Upload (step 1) is "Reading your contract".

   | Backend `step` | Screen step |
   |---|---|
   | (upload request running) `extract` | 1 Reading your contract |
   | `detect` | 2 Finding where you work |
   | `law` | 3 Looking up the labor law |
   | `compare` | 4 Checking every clause |
   | `complaint`, `translate` | 5 Preparing your report |

2. **Firestore is the truth, the HTTP request is the backup.** The analyze request stays open for the whole analysis (NF-P2-007, decision 1). The page follows the document for progress and uses the request's answer for the result. Owners can already read their contracts, so no rule changed.
3. **This run versus the last one.** Uploading the same file again reuses the contract, and its document still says `completed` or `failed` from last time. The page treats that as "not started yet" (step 2 running) until it sees this run's `processing`. A live test found this: without it, the old result appeared while the new check was still running.
4. **Retry without re-upload** calls `POST /contracts/{id}/analyze` again. Everything the backend already stored is reused (its cache).
5. **The 45 s stall hint** is per step and per run. Each run gets a fresh progress card (`key={attempt}`), so a hint never carries over to a retry (found in the live test).
6. **Messages by code, not by HTTP text.** The backend's `detail` text is English only (D-10). The page uses `error.code` from the document. With no document error (the upload itself failed, or the network did), it uses the HTTP status: the contract endpoints use 503 and 504 only for Gemini, so those say "AI busy" and "AI too slow"; anything else uses the app-wide mapping (offline, too many requests, server). A live upload that got 503 from Gemini first said "Our server had a problem", which was misleading.
7. **An upload failure goes back to the form** with the file still selected and the message above it. There is no contract yet, so there is nothing to retry without the file.

## Flow

```
Worker taps "Check my contract"
  upload request running         → step 1 running, skeleton                 (no document yet)
  upload returns contract_id     → onSnapshot(users/{uid}/contracts/{id})
  analyze request running
    doc still completed/failed from an earlier check → step 2 running        (not this run yet)
    doc {status: processing, step: detect}           → step 2 running        (this run seen)
    step: law / compare / complaint|translate        → step 3 / 4 / 5 running, earlier ones ✓
    45 s on one step                                 → "Still working…" under it
    doc {status: completed} or analyze 200           → result card
    doc {status: failed, error: {step, code}}        → that step ✗
  analyze error (503/504/network)                    → alert: message for the code
                                                       [Try again] (if it can help) [Check another contract]
  Try again                                          → analyze again, new progress card from step 2
```

## All commands, in order

From `frontend/`. In PowerShell, `pnpm.cmd` if `pnpm` is blocked by the execution policy.

### 1. Checks

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

On Windows with CRLF checkouts, use `pnpm exec prettier --check --end-of-line auto src`.

### 2. Try it on the emulators (real Gemini, never production)

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

Terminal 2, from `data-scripts/` (virtual environment active), load the curated law and templates **into the emulator**:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.ilo_natlex --only SG MY
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.complaint_templates --only SG MY
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m src.loaders.ilo_natlex --only SG MY
python -m src.loaders.complaint_templates --only SG MY
```

Terminal 3, from `backend/` (virtual environment active), the API against the emulators:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 FIREBASE_PROJECT_ID=demo-nomadfinance GCLOUD_PROJECT=demo-nomadfinance uvicorn app.main:app --port 8080
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
$env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GCLOUD_PROJECT = "demo-nomadfinance"
uvicorn app.main:app --port 8080
```

Terminal 4, from `frontend/`:

```bash
pnpm dev --mode emulator
```

Open **http://localhost:5173** (not `127.0.0.1`), sign in with any phone number (the emulator shows the code in Terminal 1), finish onboarding, go to **Check a contract** and upload `backend/tests/fixtures/contracts/sample_contract_sg.pdf`.

**What to look for:**
1. The progress card and skeleton appear at once, step 1 running.
2. Steps tick off as the backend log shows each step; a screen reader announces "Step n of 5: …".
3. If a step takes over 45 s, the "Still working…" line appears under it.
4. On success, the result card replaces the card.
5. On a Gemini failure, that step shows ✗ with the message. "Try again" restarts at step 2 without uploading; there is no stall hint at first.
6. Upload the same file again: step 2 runs, and the old result does **not** appear before the new answer.
7. DevTools → phone size (375 px): no sideways scrolling. Rendering → "prefers-reduced-motion: reduce": spinners and pulses stop.
8. Keyboard only: Tab reaches "Try again" and "Check another contract", Enter works.

**Without Gemini** (quota gone, D-58), you can play the backend's writes into the emulator. Use the Emulator UI (http://localhost:4000 → Firestore → `users/{uid}/contracts/{id}`) and set `status: processing` with `step: law`, then `compare`, then `status: failed` with `error: {step: compare, code: gemini_busy}`. The page follows each change.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `tsc -b` | Pass |
| `pnpm lint` (max warnings 0) | Pass |
| `prettier --check --end-of-line auto` | Pass |
| `vitest run src` | 36 passed (2 files; 30 in `pipelineProgress.test.ts`) |
| `pnpm build` | Pass (PWA precache 33 entries) |

**Live, in the browser on the emulators** (local backend, contract `sample_contract_sg.pdf`):
- **Real Gemini, first runs.**
  - The card and skeleton appeared at once. Extraction took 59.7 s, and the stall hint appeared at 45.5 s on step 1.
  - Step 2 began at 60 s. Detect then timed out 3 times, and the API answered 504 after 91 s.
  - Step 2 showed ✗ with "The AI service took too long…", "Try again" and "Check another contract" (screenshot).
  - "Try again" restarted step 2 without an upload. It showed the stall hint at once, which was a bug, fixed with a fresh card per run (decision 5).
- **Real Gemini, final code (two runs):**
  - Detect got 503 ("high demand") and 30 s timeouts; the API answered 504 after 37 s and 65 s.
  - On the second run, the page showed step 2 running over the old `failed` document, the stall hint at 45.2 s, and step 2 ✗ at 65.4 s with "The AI service took too long…", "Try again" and "Check another contract".
  - **Keyboard:** Tab reached "Try again" (visible focus ring), then "Check another contract"; Enter returned to the form.
- **Success path.** Gemini's extraction tier did not finish a detect all afternoon (D-54), so the success path was verified with the backend's writes played into the emulator:
  - **Success:** the steps advanced 2 → 3 → 4 → 5, each 3 s apart, with each one announced. The result card (score 34, Serious concerns, 2/2/4) replaced the progress card.
  - **Failure at compare (`gemini_busy`) then 503:** steps 1–3 ✓ and step 4 ✗. The alert showed "The AI service is busy…", "Try again" and "Check another contract". Step 4 stayed ✗ in the milliseconds between the document failing and the HTTP answer.
  - **Try again:** a new request, step 2 running, and no stall hint at 43 s. The hint appeared by 47 s. The run then advanced to 5 and showed the result as soon as the document said `completed`, before the HTTP answer. That is the lost-answer path.
  - **Re-upload of the same file** over an old `completed` document: step 2 running, not the old result. Found in this test and fixed (decision 3).
- **Phone width 375 px:** page width 375, no sideways scroll (screenshot).
- **Reduced motion:** the spinner and skeleton use `motion-safe:` classes only.
- **Real Gemini, upload failures (second session):** three uploads of a fresh contract.
  - Upload 1: 503, 503, then a timeout, and the API answered **504 after 109 s**. Step 1 ran, the stall hint appeared at 46 s, and the page went back to the form with an alert that said "Our server had a problem" (misleading). Fixed with decision 6.
  - Uploads 2 and 3: **503 after 11 s and 8 s**. The alert now says "The AI service is busy right now…", the file stays selected and the button is enabled.
- **Slow network**, simulated in the page: the browser pane has no DevTools throttle, so every API answer was delayed 2 s and the upload took 20 s (a 1 MB photo at Slow 3G's ~50 KB/s); the backend's writes were played into the emulator.
  - Step 1 ran for the whole 20 s with no flicker, then step 2.
  - Steps 3 → 5 followed Firestore on time.
  - The result showed at 46.5 s from the document. The held analyze request then failed with a network error (`Failed to fetch`); the page stayed on the result, with no error.
  - Firestore's own connection was not slowed.

**Not run:**
- DevTools "Slow 3G" itself (see the simulation above). Take it with the PR screenshots: DevTools → Network → Slow 3G, then upload.
- A full success run with real Gemini, blocked by D-54 and D-58. Run step 2 above once Gemini answers, and record it here.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Steps stay on "Finding where you work" and nothing moves | The page can't read the contract document. Check you're signed in as its owner. On the emulator, the frontend must use `--mode emulator` |
| Stuck on a step for minutes, the backend log shows `gemini_retry` | Gemini slow or overloaded (D-54); the hint says so after 45 s. The request ends with a failure within the timeouts |
| "Try again" missing | The error code is one where retrying can't help (unreadable photo, not a contract, no law data, no terms). Upload a different file or choose the country |
| Old result shows for a new check | Should not happen any more (decision 3). If it does, check the backend still writes `status: processing` when it claims the contract |
| `127.0.0.1:5173` refuses to open | Use `localhost:5173`; Vite listens on `localhost` |
| `pnpm` not recognized in PowerShell | Use `pnpm.cmd` |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Skeleton`, `Button`, lucide icons)
- [x] Fully mobile responsive (375 px, no sideways scroll)
- [x] Works on slow network: Slow-3G-like delays simulated in the page (20 s upload, 2 s per answer, dropped answer); DevTools' own throttle to be run with the PR screenshots
- [x] Loading states: step list plus report skeleton
- [x] Error states: every stop code, Gemini busy, slow or unavailable, network failure (HTTP status fallback), lost answer
- [x] i18n keys for all user-facing strings (6 languages)
- [ ] Screenshots added to PR: take them when opening the PR (progress, stall hint, failure, phone width)
- [x] Accessibility: ordered list, `aria-current`, state words for screen readers, polite announcement per step, `role="alert"`, native buttons (keyboard), reduced motion respected

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Aditya (NF-P2-011, report card):**
  - The page keeps the small result card for now. Replace it with the report card.
  - `result` in `ContractUpload.tsx` is the `ContractAnalysis` to start from.
  - `ReportSkeleton` should keep roughly the report card's shape; adjust it when the card's layout is final.
  - `ContractUpload.tsx` is 306 lines, over the ~300-line guideline; accepted as it is (D-61).
- **Aditya (NF-P2-013, letter):** `complaint_pending` is on the result as before.
- **Pranjal (NF-P2-012, language switch):** nothing here changes the report language flow.
- **Everyone:** `contract.upload.analyzing` was removed (it had no use left).

## Commit and PR for this task

Branch: `feature/contract-processing-anim` (already checked out).

```bash
git add frontend/src docs/runbooks/NF-P2-010-contract-processing-animation.md docs/pipelines/contract-shield.md docs/deferred-items.md
git status
```

```bash
git commit -m "feat(contracts): show live analysis progress with retry and report skeleton" -m "Refs: NF-P2-010"
```

PR title: `feat(contracts): live processing steps, retry and report skeleton (NF-P2-010)`

## Not covered here

- The full report card, language switch, letter download: NF-P2-011 to NF-P2-013
- Background processing (the analysis still runs inside the request, NF-P2-007)
- A paid Gemini key (D-58)
