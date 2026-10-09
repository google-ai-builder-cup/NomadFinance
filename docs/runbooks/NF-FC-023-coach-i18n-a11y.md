# NF-FC-023 — Coach translations and accessibility pass, with the fixes found while testing it

## Summary

The tracker row is "fill the coach namespace for 6 languages, axe audit, live-region announcements". The namespace was already complete in all six languages (268 keys each, the check was green), so the task's own work was the **axe audit, the announcements and the checks that keep them true**. While testing the Coach, Devam reported four faults and asked for one feature; they are done in the same branch. All of it is the Coach module (`coach` flag), nothing outside it except one line of the shared header (below).

| Part | What a worker sees or what the task holds |
|---|---|
| **Bug 1: the message box was tiny after finishing** | The finished screen is now a page that grows: the score first, then the whole conversation in a box 32 rem tall (at most 70% of the window), then "Back to home" and "New interview". Before, the conversation was squeezed to 4 rem (`max-h-16`) and the score scrolled inside a fixed-height page |
| **Bug 2: no way to start over** | "New interview" sits on the step line at every point of the interview and beside "Back to home" at the end. It asks first ("closes this one and its answers"), and a plan already made is left alone. The old buttons (the welcome-back banner, the error notice) stay |
| **Bug 3: blank space at the foot of the page** | A real cause, found in the browser: each chat bubble has a hidden "You said:" / "Coach:" label (`position: absolute`), and the scrolling log was not a positioned box, so the labels were placed against a box outside it, below the visible part. A 20-line talk made a 1,986 px page in a 768 px window. One class (`relative`) on the log fixed it (858 px, which is the footer). A test holds it |
| **Bug 4: the recap was a block of prose** | At the review the screen shows **a table** (question, answer, a Change button on each row) built from the saved answers, under a short line from the coach. The coach's own sentence (reply prompt v2) no longer repeats the answers, so the figures on screen are exactly the stored ones |
| **New: what the Coach already knows** | Before the first question a card lists what the profile, the latest contract and Financial Identity already answer (country, kind of work, pay, money sent home, savings, bank or wallet), each with where it came from and a date. **Use these answers** keeps the rows not marked Change; **Ask me every question** keeps none. A changed row is asked as usual. Edits stay in the Coach: the profile and Financial Identity are never written |
| **Accessibility** | axe on every Coach screen in all six languages in CI; the same rules plus colour contrast and tap size in a real browser at 360 px and on desktop, light and dark; each finished coach message is read once (the hidden copy leaves the page after 4 s); one alert, not two, for a failed answer; focus goes to the card and to the table when they appear |
| **Translations** | The new strings in all six languages (`recap.*`, `known.*`, `chat.newInterview`, `confirmed.conversation`), the missing-key check green (1,304 English keys), and **a test that reads the six real files** to prove the sentences the helpers send are still ones the server reads (D-236) |

## How the card works (the one new route)

```
new session ──► backend reads users/{uid} and the income, savings and transfers entries
            ──► session.known = { items: [{ slot, value, source, as_of }] }   (nothing is an answer yet)
screen      ──► shows the card; the opening turn WAITS
worker      ──► Use these answers / Ask me every question
            ──► POST /api/v2/coach/sessions/{id}/known  { keep: [slots] }
backend     ──► keeps the named rows as confirmed answers (source profile_prefill, contract_prefill or identity_prefill),
                settles the stage, ends the contract-salary offer of NF-FC-015, writes once with the revision it read
screen      ──► opens the interview with a turn that has no text: the first question still open is asked
```

| Answer | Worked out from |
|---|---|
| Country, kind of work | `users/{uid}.host_country`, `.job_type` |
| Pay | The newest analysed contract (NF-FC-015); else the newest income entry of category `salary`, **taken as one month's pay**, shown with its date |
| Money sent home | The transfers of the last 90 days in the currency used most: their sum over the number of calendar months that have one |
| Savings | Deposits minus withdrawals in the currency used most; not offered at zero or less |
| Bank or wallet | The `account_type` of the savings entries (`bank`, `mobile_wallet`, both); `cash` or none is not offered |

**Not offered, always asked:** the leaving date, dependents, the fee paid, the debt and its interest. Financial Identity holds no debt (D-255).

## Files

**Backend**

| File | Change |
|---|---|
| `backend/app/services/coach/known_details.py` (new) | The rules above as pure functions (`collect_known`, `kept_slots`), the Firestore finder, `UnknownKnownSlotError`. Under `mypy --strict` |
| `backend/app/services/coach/session_service.py`, `session_document.py` | A new session stores the offer (`known`); `apply_known` writes the kept answers once, refuses an unknown slot, is safe to repeat, never overwrites an answer given in the chat, and ends the contract offer |
| `backend/app/api/v2/coach.py`, `app/dependencies.py` | `POST /coach/sessions/{id}/known` (flag-guarded like every coach route), and the finder wired in |
| `backend/app/schemas/coach_session.py`, `coach_profile.py` | `CoachKnown`, `CoachKnownItem`, `CoachKnownRequest`; `known` left out of the answer when there is none (so every earlier sample and client is unchanged); three new `source` values |
| `backend/app/prompts/coach/reply.v2.yaml` (new), `reply.v1.yaml` (removed), `turn_prompt.py`, `summarise.v1.yaml` | The reply at `review` is one short line that repeats no answer and no number; a change of language is said only when there is no worker message (D-225 of NF-FC-018). v1 removed, as for every earlier version bump |
| tests (7 files, new and changed) | 111 new: the rules (31), the session flow (19), the API (12), the helper sentences against the six real translation files (49); 3 against the Firestore emulator; the prompt and mock tests extended |

**Frontend**

| File | Change |
|---|---|
| `components/coach/RecapTable.tsx`, `utils/coachRecap.ts` (new) | The review table; the words for each answer (dates with digits 0 to 9 in every language, money as the helpers write it) |
| `components/coach/KnownCard.tsx` (new), `hooks/useCoachChat.ts`, `utils/coachChatState.ts`, `services/coachService.ts`, `types/coach.ts` | The card; the chat waits for it before its opening turn; the reducer takes the kept answers |
| `components/coach/NewInterviewButton.tsx`, `hooks/useNewInterviewAsk.ts` (new), `StageStepper.tsx`, `common/StepProgress.tsx` | The button and its question; the step line can carry a control |
| `components/coach/CoachChat.tsx`, `pages/coach/CoachHome.tsx`, `ChatLog.tsx` | Three layouts (the interview fits the window; the review and the finished screen are pages that grow); the `relative` fix |
| `components/common/ChatBubble.tsx` | A failed line need not be an alert of its own |
| `components/layout/Header.tsx` | The brand link had no name on a phone (the visible name is hidden below 640 px): `aria-label="NomadFinance"`. Found by the browser axe run; it was on every page |
| `i18n/coach/<lang>.json` (6) | `recap.*`, `known.*`, `chat.newInterview`, `confirmed.conversation` |
| `mocks/axe.ts`, `mocks/coachTurns.ts` | The raw-key check knows the Coach's key roots (and ignores a file name such as `chat.png`); `replayKnown` |
| tests (11 files) | 97 new in 6 files, plus the reducer, the service, `ChatLog`, `ChatBubble` and `StepProgress` tests extended |

**Docs:** `docs/api/v2-coach.md` (the route, `known`, the sources), `docs/data-model/collections/coach.md`, `docs/mocks/coach/` (4 samples) and its README, `docs/mermaid/financial-coach-pipeline.mmd`, `docs/ui-kit.md`, `docs/deferred-items.md`, this file.

**No shared file was touched** (`package.json`, the lockfile, `firebase.json`, the rules, `tsconfig*`, workflows). Devam ran `pnpm install` so that `axe-core`, already in the lockfile, is in `node_modules`.

## Firestore, Firebase and Google Cloud: what was checked

| Thing | Result |
|---|---|
| `frontend/firestore.rules` | `coach_sessions` is read-only from the browser; the backend writes with the Admin SDK. The new field lives inside the session document and the profile and entry reads are the backend's, so **no rule changes** |
| `frontend/firestore.indexes.json` | The reads are `users/{uid}` and a whole subcollection each (`income`, `savings`, `transfers`): automatic single-field indexes only. **No index changes** |
| Feature flag `coach` | The route is on the same flag-guarded router: with the flag off it is the 404 of an unknown path (tested) |
| CORS and headers | A `POST` with `Authorization` and `Content-Type`: already allowed. No `Idempotency-Key` is needed (the route is safe to repeat) |
| Cloud Run service account | Already reads and writes Firestore. No new variable or secret |
| Firebase Hosting, PWA cache, CSP | Unchanged. The Coach chunk is 83 kB (23.7 kB gzip) |
| Cost | A new session now makes four small reads more; no Gemini call is added (the reply at `review` is shorter) |

## Choices that were not in the task text

| # | Choice | Why |
|---|---|---|
| 1 | **The review table is built from the saved answers, and the prompt got a v2**, not a table parsed out of the coach's prose | No free-text parsing (the project rule); a table of figures must be the stored ones; and the coach no longer has numbers to get wrong |
| 2 | **The review and the finished screen are pages that grow**; the interview still fits the window | A fixed-height window cannot hold a ten-row table and a score on a phone. The interview needs the fixed height so a streamed reply moves nothing |
| 3 | **"New interview" is on the step line**, not a row of its own | A row of its own took 56 px from a conversation that has 140 px on a 360 × 740 phone |
| 4 | **One card, not a question for each answer** | Chosen by the product owner. One tap in the common case and no extra model call (the contract prefill's way costs a turn for each answer) |
| 5 | **A kept answer is stored with its own source** (`profile_prefill`, `contract_prefill`, `identity_prefill`) and `confirmed: true`; a changed one is not stored | The plan and the score can tell where a figure came from; "Change" never leaves a half-answer |
| 6 | **The contract's salary wins over a logged one, and ends the NF-FC-015 chat question** | Two sources for one slot would otherwise ask twice |
| 7 | **Change at the review sends a sentence** that names the answer, read by the review model | No new route and no change to the review contract; a misreading only asks "which answer?" |
| 8 | **The hidden copy of a reply leaves the page after 4 seconds** | D-238: a reader browsing by line met each reply twice. The log is still `aria-live="off"` |
| 9 | **The "Not sent" label is plain text; the notice is the alert** | D-238: two alerts for one failure |
| 10 | **`reply.v1` was deleted, not kept** | Every earlier prompt bump kept one file (`contract/detect.v2`, `scam/classify.v2`) |

## Results

**Checks (2026-10-10)**

| Check | Result |
|---|---|
| Backend: `pytest tests/unit tests/integration` | **3,550 passed**, 190 skipped (the live ones) |
| Backend: the emulator tests | 13 passed (`test_coach_known_details.py`, 3 new, and `test_coach_session_repo.py`) |
| Backend: `ruff`, `black --check`, `mypy app`, `mypy --strict` on the three services | clean |
| Frontend: `vitest run src` | **1,561 passed in 131 files**, none skipped. The 5 suites that could not load before (no `axe-core`) now do |
| Frontend: `eslint --max-warnings 0`, `tsc -b`, `prettier --check`, `check-i18n`, `vite build` | clean (1,304 English keys in 3 namespaces × 6 languages) |
| `frontend/tests/rules` | Not run here: they need the emulators (`pnpm test:rules`); no rule changed |

**Breaking each rule on purpose** (a check that cannot fail proves nothing): overwriting a chat answer, leaving the contract offer open, and counting a zero balance each failed a test; an icon button with no name failed axe in 6 languages; a translation that lost its currency word failed the helper-sentence test; each was put back.

**axe, in a real browser** (the pane's Chromium with `axe-core` 4.14.0, all rules including contrast and target size; the emulator banner excluded): the interview, the card, the review and the finished screen at **360 × 740 and at desktop width, light and dark: 0 violations.** Three real findings on the way, all fixed: the table's heading skipped a level (`h3` after `h1`), the header's brand link had no name on a phone, and a first dark-theme reading of 2.4 : 1 on the Change buttons that was a half-finished colour transition in the pane (with transitions off the same buttons pass).

**Looked at in the browser** (a throwaway page with the API stubbed, removed afterwards): the card, the review table and the finished screen at 360 px and on desktop; no sideways scroll; the whole page is the footer's height taller than the window and no more; the card in Nepali. The first run kept the table's top under the sticky header (fixed with `scroll-mt-20`).

**Not verified**

- **A real screen reader and a real phone** (D-252). axe finds structure, names and contrast; whether 4 seconds is the right time for a hidden reply, and how the table is read, needs a listener.
- **The new reply prompt with the live model** (D-253). It is checked by tests that read the prompt and by recorded replies; no Gemini key was used. The "12 of 12 personas" and the injection suite the Definition of Done asks for after a prompt change belong to NF-FC-024, which does not exist yet.
- **The card with a worker who really used the app** (D-254): it was tried against the Firestore emulator with a made-up worker and in a browser with the answers stubbed.
- **The wording in hi, tl, id, ne and bn** (D-251), written by the team.
- **Slow 3G**: the browser pane has no throttle. The new code is a `POST` and 8 kB.

## Manual test

**1. The tests.** From `backend/`:

```bash
.venv/Scripts/python.exe -m pytest tests/unit tests/integration -q
```

Expect `3550 passed`. From `frontend/`:

```bash
npx vitest run src
```

Expect `1561 passed`. PowerShell takes the same commands.

**2. The offer against the Firestore emulator.** From `backend/`:

```bash
firebase emulators:exec --only firestore --project demo-nomadfinance --config ../frontend/firebase.json "F:\\NomadFinance\\backend\\.venv\\Scripts\\python.exe -m pytest tests/integration/repositories/test_coach_known_details.py -v"
```

Expect `3 passed`. On Windows the emulator's `java.exe` can stay running and hold port 8085 (D-34); stop it before the next run.

**3. In the app** (the emulators, the API with the `coach` variables, `frontend-emulator`, the `coach` flag on for you). Sign in as a worker with onboarding done, then in the emulator UI add under `users/{uid}`: an `income` entry (`category: "salary"`, `amount`, `currency`, `entry_date`), a `savings` entry (`direction: "deposit"`, `account_type: "bank"`) and two `transfers` (`send_amount`, `send_currency`, `entry_date` in the last 90 days).

1. **The card.** Open `/coach`. Before any question: "What we already know", six rows, each with its source. Open DevTools, Network: no `/messages` call yet.
2. **Keep.** Press **Use these answers**: one `POST .../known` with the six slots, then the coach opens by asking the first question still open (the leaving date). In the emulator the session has the six slots with `confirmed: true`, and `known.state` is `resolved`.
3. **Change.** Start a **New interview**, mark **Change** on "Your pay", press the button: the coach asks for the pay as usual and never asks about the contract's salary again.
4. **Ask every question.** With every row marked Change the first button is disabled; **Ask me every question** sends `keep: []`.
5. **No records.** A worker with nothing logged sees no card and the interview starts as before.
6. **The review.** Answer to the end: a table of the answers under a one- or two-line message, a Change button on each row; press one and the coach goes back to that question. Say yes: the score, then the conversation in its own box, **Back to home** and **New interview**.
7. **The page.** On the finished screen scroll to the bottom: the footer follows the conversation at once, with no blank band.
8. **A phone.** At 360 × 740: no sideways scroll; the card and the table read in two lines a row; the buttons are 44 px tall.
9. **New interview.** Press it in the middle of an interview: it asks first; "No, keep going" returns focus to the button; "Yes, start over" gives a new interview and a new card.

## Definition of Done (Frontend feature; Backend endpoint; prompt change; Feature-flagged module)

- [x] Components built with Tailwind and the existing shadcn `Button`; fully responsive (360 × 740 and desktop, no sideways scroll)
- [ ] Works on a slow network (throttled 3G): not run, no throttle in the browser pane
- [x] Loading, error and empty states: the card (saving, the notice with its retry and its "new interview"), the table (a value it cannot read shows a dash), no records (no card)
- [x] i18n keys for every string, 6 languages, `check-i18n` green; **missing-key check green**
- [x] **axe 0 serious or critical**, in jsdom in 6 languages and in a real browser in both themes
- [x] **Each completed coach message is announced once** (tests: two turns in a row, the hidden copy leaves the page, one alert for a failed answer)
- [ ] A real screen reader (D-252); the wording read by native speakers (D-251)
- [x] Endpoint with Pydantic models, token check, specific status codes (404, 409, 422), rate limit (API-wide), Firestore emulator test
- [x] API contract, data model, mocks and the drift test updated; the mocks agree with the rules of keeping
- [x] Prompt version bumped (`coach/reply.v2`), versions recorded on the session; every figure on screen is from the saved slots
- [ ] The live-model check of the new prompt and the personas (D-253)
- [x] Route and nav stay behind the `coach` flag; the Coach chunk is still its own (83 kB, 23.7 kB gzip); rollback is the flag
- [x] Strict types, lint and format clean; no shared file touched; no secrets
- [ ] Screenshots added to the PR (take them from step 3 above)
- [ ] Reviewed by a teammate (Aditya owns the task)

## Commits, branch and PR

Branch: `feature/NF-FC-023-coach-i18n-a11y` (already checked out). The change is larger than the 400-line guideline (about 1,150 changed lines and about 2,600 new, most of them tests and translations). It splits in this order:

```bash
# 1. backend/, docs/api/v2-coach.md, docs/data-model/collections/coach.md, docs/mocks/, docs/mermaid/
git commit -m "feat(coach): offer what the profile and Financial Identity already know" -m "Refs: NF-FC-023"

# 2. frontend/src/components/coach/ (the layout, the review table, new interview, the card), pages/, hooks/, utils/, services/, types/, mocks/coachTurns.ts, i18n/coach/
git commit -m "feat(coach): review table, new interview button and card of known answers" -m "Refs: NF-FC-023"

# 3. the accessibility pass: components/common/, components/layout/Header.tsx, mocks/axe.ts, pages/coach/coachScreens.a11y.test.tsx, backend/tests/unit/services/test_coach_helper_sentences.py, test_coach_question_bank.py
git commit -m "feat(coach): accessibility pass and translation checks" -m "Refs: NF-FC-023"

# 4. docs/runbooks/NF-FC-023-..., docs/deferred-items.md, docs/ui-kit.md
git commit -m "docs(coach): add NF-FC-023 task doc and update deferred items" -m "Refs: NF-FC-023"
```

Or as one commit: `feat(coach): coach i18n and accessibility pass, review table, known answers` with `Refs: NF-FC-023`.

PR title: `feat(coach): translations, accessibility pass, review table and known answers (NF-FC-023)`

PR description:

```
The Coach's translations were already complete, so this task is the accessibility audit
and the announcements, plus the faults found while testing the Coach and one feature.

Faults fixed
- The page left a blank band at the foot: each chat bubble's hidden speaker label was
  placed against a box outside the scrolling log, so a long talk stretched the page
  (1,986 px in a 768 px window). One class on the log fixes it.
- After the answers were confirmed the conversation was squeezed to 4 rem. The finished
  screen is now a page: the score, then the whole conversation in a box that can be read.
- There was no way to start over except in the welcome-back banner. "New interview" is on
  the step line and on the finished screen; it asks first.
- The recap was a block of prose. The review is now a table of the saved answers with a
  Change button on each row, under a one-line message (reply prompt v2).

Feature: what the Coach already knows
A new session reads the profile, the latest contract and Financial Identity and offers
country, kind of work, pay, money sent home, savings and bank or wallet in one card, each
with its source. The worker keeps or changes each row (POST /api/v2/coach/sessions/{id}/known);
a changed row is asked as usual. Nothing is used until the worker agrees, and edits never
reach the profile or Financial Identity. Debt, fees, dependents and the leaving date are
not in Financial Identity and are always asked.

Accessibility
axe on every Coach screen in six languages in CI, and in a real browser at 360 px and on
desktop in both themes (0 violations; two real ones fixed: a heading level and the header's
brand link, which had no name on a phone). A finished reply is read once, a failed answer
is one alert, and a test now keeps the sentences the helpers send readable by the server.

Config: no Firestore rule, index, flag, CORS or deploy change. No shared file touched.
Rollback: turn the coach flag off.

Not done / to check: a real screen reader and phone (D-252), the new prompt with the live
model (D-253), the card with a real worker's records (D-254), native-speaker review (D-251).

Checks: backend 3,550 tests, frontend 1,561 tests, ruff, black, mypy, eslint, tsc, prettier,
check-i18n and build clean.

Refs: NF-FC-023
```

## Noticed, not fixed

- **D-247:** a Coach reminder still shows as "Exploitation Radar" on the dashboard card (the Radar widget is another task's).
- **D-248 (1):** `test_scam_history.py::test_the_history_pages_with_a_cursor_and_no_repeats` is flaky (ties in `created_at`).
- **D-256:** other screens may have the same hidden-label stretch as the chat had.
- **D-255:** Financial Identity has no debt, so debt cannot come from it.
- The tracker row for NF-FC-023 still says "Not Started"; the owner updates it after the merge.
