# NF-FC-025 — Coach end-to-end tests (Playwright)

## Summary

Five Playwright specs drive the Coach in a real browser, on a desktop and on a phone (Pixel 5), for 13 tests and 26 runs:

| Spec | What it shows |
|---|---|
| `e2e/coach-journey.spec.ts` | **Start → interview → score → plan → PDF.** Every question answered through the screen's own helper (country and job chips, the date, amount, count and interest fields, the bank chips), the review table, "Yes", the score, "Make my 90-day plan", the plan page, and a saved file that is a PDF named `nomadfinance-plan-en.pdf`. Also: an answer typed instead of picked; no sideways scroll on the first question, the review, the score or the plan; the Coach page leading back to the plan |
| `e2e/coach-resume.spec.ts` | **Resume after reload.** Six answers in, an amount typed and not sent, reload: "Welcome back", "Step 4 of 6: Debt", the conversation, the same question and the unsent amount are back, and nothing is asked again. "Start a new interview" asks first, and "Yes" begins a new session |
| `e2e/coach-language.spec.ts` | **Language switch.** Choosing Hindi half way sends a turn with no words and `language: "hi"`, the coach asks the same question in Hindi, the answers and the step are kept, and the next answer goes in Hindi. The language is the whole app's |
| `e2e/coach-offline.spec.ts` | **Offline send.** With no signal the answer shows "Waiting for signal", the panel is locked, nothing reaches the server; when the signal returns it is delivered **once** (one turn on the server, one message in the transcript). Also: a waiting answer survives a reload and goes with "Send now" |
| `e2e/coach-known.spec.ts` | **What the Coach already knows** (NF-FC-015, -023). Keep most, change one, and only the rest is asked; ignore the offer; changing every row leaves nothing to keep |

Not in this task: the backend and Gemini (NF-FC-024), the check-in sheet (NF-FC-022), the feature docs (NF-FC-026). No application code was changed, and no shared file (`package.json`, lock file, `playwright.config.ts`, `tsconfig*`, workflows) was touched: the existing `Frontend end-to-end` job in `frontend-ci.yml` runs every spec under `e2e/`, so the new ones run in CI without an edit.

## There is no staging

The tracker says "green on staging in CI". Staging was dropped (`NF-F0-011-ci-staging-env.md`). Like the scam specs (NF-SA-020), these run against the **production build served by `vite preview`**, with sign-in through the **Auth and Firestore emulators** and the backend replaced by a stand-in:

```
browser ──► vite preview (the real app)
   │  sign-in: Auth emulator (e2e/support/emulators.ts)
   └─► /api/**  ──► page.route ──► e2e/support/coachApi.ts
                                      (one interview in memory; the score, the plan and the
                                       sessions are the files of docs/mocks/coach/)
```

`coachApi.ts` behaves like the Coach's routes: `POST /sessions` resumes the open session (200) or starts one (201), a restart abandons the old one, a turn is an SSE stream (`slot_update`, `token`, `done`), the same `Idempotency-Key` replays the same stream, the plan is made once the answers are confirmed, and the PDF comes back with the right headers. It does **not** read the worker's words: whatever is sent fills the next question with the worked example's value (an Australian care worker sending money to India). So the tests prove what the screen sends and how it reacts to the contract; whether the server understands the words is NF-FC-010 and NF-FC-024. Because the answers and the plan come from `docs/mocks/coach/`, a change to the contract there reaches these tests.

## Run it

You need Node and pnpm (`frontend/`), Java 21+ and `firebase-tools` (for the emulators), and a Chromium for Playwright.

PowerShell, from `frontend\`:

```powershell
pnpm install --frozen-lockfile
$env:VITE_API_BASE_URL = "http://127.0.0.1:4173"
pnpm exec vite build --mode emulator           # the app, built for the emulators, calling its own address
pnpm exec playwright install chromium          # once
firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm test:e2e"
```

bash, from `frontend/`:

```bash
pnpm install --frozen-lockfile
VITE_API_BASE_URL=http://127.0.0.1:4173 pnpm exec vite build --mode emulator
pnpm exec playwright install chromium          # once
firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm test:e2e"
```

Only the Coach: add `e2e/coach-*.spec.ts`. One project: `--project=mobile`. To watch: `--headed`. After a failure the report is `frontend/playwright-report/` (`pnpm exec playwright show-report`) and each failed test has an `error-context.md` under `test-results/`.

The build must be made again after any change to the app: the tests run against `dist/`. It must be the **emulator** build with the API address set to the preview's own, as above, or the stand-in never sees a call.

To keep the emulators up between runs (faster): `firebase emulators:start --only auth,firestore --project demo-nomadfinance` in one terminal, `pnpm test:e2e` in another. On Windows `emulators:exec` can leave the Firestore emulator's Java process running; see D-262.

## Files

| File | Change |
|---|---|
| `frontend/e2e/support/coachApi.ts` (new) | The stand-in for the Coach's routes; `coachText()` reads a string of `src/i18n/coach/<language>.json`, so a test in Hindi does not hard-code the words |
| `frontend/e2e/support/coachSteps.ts` (new) | The worker's side: the eleven steps (what each helper must send, how to give it), `answer()`, `expectAsked()`, `panel()`, `conversation()` |
| `frontend/e2e/coach-{journey,resume,language,offline,known}.spec.ts` (new) | The 13 tests |

## Decisions that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Stand-in instead of the mock files one by one | The mock files are single answers; a reload, a switch and a retry need a server that remembers. `coachApi.ts` keeps one interview and takes its data from the mock files |
| 2 | Helpers, not typing, for the main path | The helpers are what a worker on a phone presses and they write the text the server reads; the test checks that text for all eleven questions. One test types an answer instead |
| 3 | Offline is cut twice | The browser is put offline (so `navigator.onLine` and the `online` event change, as in flight mode) **and** the stand-in refuses the calls: a routed request can otherwise be answered while the browser says it is offline |
| 4 | "Exactly once" is counted on the server | The stand-in counts the turns that reached it with the answer and the messages in the transcript; an aborted attempt is not a turn |
| 5 | Questions are looked for inside the conversation | The hidden status line that says each finished reply to a screen reader repeats the text, so a bare text search matches twice |
| 6 | Only the English copy is hard-coded | After a switch to Hindi the words come from `coachText()` |
| 7 | The Hindi lines of the stand-in | The switch sentence and two questions are from `turn-08-language-switch.sse`; any other question gets a generic Hindi sentence |

## Checks run (2026-10-10)

| Check | Result |
|---|---|
| The 13 Coach tests, desktop and phone | **26 / 26 passed** |
| **Repeated 20 times** (`--repeat-each=20`, 2 workers, no retries, so every flake counts) | **520 / 520 passed, 0 flaky, 0 failed** (13 minutes). Flaky rate 0%, against the bar of under 2% |
| **The tests fail when the app is broken** (two breaks made in the app, built, run, then restored and rebuilt) | `shouldQueue` made to refuse an answer sent without a connection: both offline tests failed. The resume banner turned off in `CoachChat.tsx`: both resume tests failed. After restoring, all 8 passed again |
| `tsc -p e2e` | clean |
| `eslint e2e --max-warnings 0` | clean |
| `prettier --check` on the new files | clean (with `--end-of-line auto`, see D-262) |
| The existing e2e specs | not changed; their files were reformatted by a stray `prettier --write` and put back to their original line endings, `git status` shows them unchanged |
| CI | **Not run**: the branch is not pushed. The job is unchanged and runs the new specs; the run here used the installed Google Chrome instead of the Playwright download (D-262) |

**Not verified:** a real backend with Gemini (D-261); the service worker's background send; the Share button; Safari and Firefox; the CI job's total time with the five new specs (about 40 seconds here for the 26 Coach runs on two workers; the job's limit is 15 minutes).

## Definition of Done (Test-only / QA task)

- [x] **The test fails when the behaviour is broken**: shown for the offline queue and the resume banner.
- [ ] **Passes in CI**: not run (not pushed).
- [x] Bugs found are filed with severity: none found in the app; the only issues were in the tests' own selectors. Windows notes are D-262 (P2).
- [x] Tracker finish line, flaky rate under 2% over 20 runs: 0 of 520 runs failed or needed a retry (20 repeats of 26 runs, locally; the same measure on CI is still to be taken).
- [ ] Tracker finish line, "green on staging in CI": there is no staging; green locally, CI pending.

## Noticed, not fixed

- D-262: `pnpm format:check` reports every file on a Windows checkout (line endings), and `emulators:exec` can leave the Firestore emulator running.
- `frontend/firestore-debug.log` is rewritten by every emulator run (it is untracked and ignored).

## Commit

Branch: `test/NF-FC-025-test-coach-e2e` (already created).

Commit message:

```
test(coach): add Playwright end-to-end tests for the coach
Refs: NF-FC-025
```
