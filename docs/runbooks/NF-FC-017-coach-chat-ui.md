# NF-FC-017 — Coach chat screen with streamed replies

## Summary

`/coach` is now the interview screen. A worker opens it and the coach speaks first; the reply appears word by word as the server writes it. The worker answers by tapping a chip, filling an amount, picking a date, or typing, and the coach asks the next question. A row of six steps shows where the interview stands. A stream that drops is tried again by itself once and then offered as **Try again**; a half reply is never shown as final. The "Coming soon" placeholder is gone.

The screen is built against the recorded streams in `docs/mocks/coach/` (NF-FC-002) and the real stream route that NF-FC-008 to -013 built. It is behind the `coach` flag, as before, and stays its own lazy chunk.

Out of this task, and still to come: voice and the language switch (NF-FC-018), the resume banner, saved drafts and the offline queue (NF-FC-019), the score screen (NF-FC-020), the plan view (NF-FC-021), the dashboard card (NF-FC-022), the translation and accessibility audit (NF-FC-023) and Playwright (NF-FC-025). A worker who reaches stage `plan` is told the answers are in and is pointed home.

## What the worker sees

| State | Screen |
|---|---|
| Opening | A grey skeleton, then the coach's first question. The coach is always the one who speaks first (a turn with no `text`) |
| A question | The coach's words in a bubble, and under them the helper that fits the question |
| Waiting | Three dots in the coach's bubble, then the words, with a caret, as they arrive. The answer panel is locked (the text box stays editable) |
| Stage | Six numbered steps (Basics, Income, Family, Debt, Savings, Review) and "Step 3 of 6: Family" |
| Review | "Yes, that is right" and "I want to change something" |
| Answers confirmed | "All your answers are in", and a link home. The score and plan come with NF-FC-020 and -021 |
| A turn that failed | The worker's line says **Not sent**, and a notice under it says why, with the one button that can help (Try again, or Start a new interview) |

The helper for each question (from `next_slot`; `utils/coachInput.ts`):

| Question | Helper | What it sends (English) |
|---|---|---|
| Country | 6 chips | `Australia` |
| Kind of work | 7 chips (the onboarding names) | `Care worker` |
| Departure date | A date field, or "I do not know yet" | `2026-12-01` |
| Salary, remittance | Amount, currency, per month / week / year | `4200 AUD per month` |
| Fee paid, debt, savings | Amount, currency, and "None (0)" | `120000 AUD`, `None (0)` |
| People who depend on you | A whole number, 0 to 20 | `3` |
| Interest on the debt | A rate and per month / year | `3% interest per month` |
| Bank or wallet | 4 chips | `Bank account` |
| Any of them | **Type my own answer**: a text box, Enter sends, Shift+Enter adds a line, over 1,000 characters is never cut | what was typed |

## Flow

```mermaid
sequenceDiagram
    autonumber
    participant W as Worker
    participant P as CoachHome and CoachChat
    participant S as streamCoachTurn
    participant A as Coach API

    P->>A: POST /api/v2/coach/sessions (language, one active session)
    A-->>P: the session, with its transcript when resumed
    Note over P: no messages yet: the coach speaks first
    W->>P: taps a chip, or sends a field
    P->>S: turn (text, session language, new Idempotency-Key)
    S->>A: POST /sessions/id/messages, Accept text/event-stream
    loop token and slot_update, ping ignored
        A-->>S: event
        S-->>P: words appended; facts kept aside
    end
    alt done
        A-->>S: done (message id, stage, next slot)
        S-->>P: reply, facts and stage committed together
    else stream ended with no done, or silent for 30 s / 60 s
        S-->>P: CoachStreamDropped
        P->>S: once more, same key, words thrown away first
    else error event or a refusal
        S-->>P: failure: words and facts thrown away, worker's line marked Not sent
    end
```

**Why the words wait for `done`.** A turn is saved by the server only when it is complete (contract, "Everything in a stream is provisional until `done`"). The screen therefore shows the words as they come but commits the reply, the facts and the new stage in one step at `done`. A stream that drops leaves nothing behind.

**Why a retry cannot repeat a turn.** Every retry of one turn carries the same `Idempotency-Key`. If the server had in fact finished the turn, it replays it; if it is still running it answers `409 request_in_progress` and the screen waits `Retry-After` (up to 3 times).

## Files

| File | What it does |
|---|---|
| `src/pages/coach/CoachHome.tsx` | The page: header, loading skeleton, load failure, and the chat keyed by the session id (a new session is a new chat). Replaces the placeholder |
| `src/components/coach/CoachChat.tsx` | The stepper, the conversation, the notice and the answer panel, wired to `useCoachChat` |
| `src/components/coach/ChatLog.tsx` | The scrolling conversation (`role="log"`, not a live region), the "Latest message" button, the status region that reads a finished reply once |
| `src/components/coach/AnswerPanel.tsx` | Chooses the helper for the question; "Type my own answer"; returns focus when a turn ends |
| `src/components/coach/MoneyField.tsx`, `SimpleFields.tsx`, `TextComposer.tsx`, `fieldClasses.ts` | The amount, number, rate and date helpers, and the text box |
| `src/components/coach/StageStepper.tsx`, `CoachNotice.tsx` | The six steps (on the shared `StepProgress`); the failure notice |
| `src/hooks/useCoachChat.ts` | One turn at a time: send, retry with the same key, cancel on leaving the screen, the opening turn |
| `src/hooks/useCoachSession.ts` | Start or resume the interview; start a new one (`restart`) |
| `src/hooks/useStickToBottom.ts` | Follows a growing reply until the worker scrolls up; instant, never animated |
| `src/services/coachService.ts` | `startCoachSession`, and `streamCoachTurn`: `fetch` and a stream reader, 30 s to the first byte and 60 s a turn |
| `src/utils/sse.ts` | The frame parser: split chunks, CRLF, the `: ping` heartbeat, several `data:` lines |
| `src/utils/coachChatState.ts` | The reducer: what is provisional, what is committed at `done`, what a failure throws away |
| `src/utils/coachTurnRunner.ts` | The retry rules (one drop retry, three in-progress retries) |
| `src/utils/coachErrors.ts`, `coachInput.ts`, `idempotency.ts` | Error code to wording and button; which helper and the amount parser; the key |
| `src/types/coach.ts` | The session, stream events and failure, as the contract defines them |
| `src/i18n/coach/{en,hi,tl,id,ne,bn}.json` | 78 strings each (the 4 of the placeholder are gone) |
| `src/mocks/coachTurns.ts` | Test-only: replays the recorded streams and records what the screen sent |
| `docs/mocks/coach/turn-07-redirect.sse` | Now the server's fixed words, word for word (D-225); `src/mocks/coach.msw.test.ts` pins them |
| `docs/api/v2-coach.md`, `docs/deferred-items.md` | Status lines and the log |
| Tests (12 files, 149 new tests) | Below |

Not touched: `package.json`, the lock file, `tsconfig*`, `vite.config.ts`, the router, `CoachRoute.tsx`, `apiClient.ts`, workflows, and everything in `backend/`. No new dependency (the stream parser is 60 lines).

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Language of a turn | The **session's** language, not the app's, so a resumed Hindi interview stays Hindi until NF-FC-018 builds the switch. Chips and messages are in the app's language; the server reads all six (D-237) |
| 2 | Steps | Six (Basics to Review). `plan` is not a step of the interview: it marks all six done |
| 3 | Retry | A dropped or stalled stream is tried once more by itself after a second; a turn that is "still running" (`409`) is asked again after `Retry-After`, up to 3 times. Everything else waits for the worker's **Try again**, with the same key |
| 4 | The failure notice | Lives **inside** the conversation, after the line that failed. A first version sat beside it and squeezed the conversation to 50 px at 360 x 740 |
| 5 | The text box while a reply arrives | Stays editable, only the send button waits. A disabled field gives up focus, the phone's keyboard closes and the screen jumps |
| 6 | Reading a reply out | The log is `aria-live="off"`; a hidden `role="status"` says the finished reply once at `done`. Reading the page by line reads it twice (D-238, NF-FC-023) |
| 7 | Country names | Written in the strings, not taken from the browser's locale data: the server finds a country by the names in its cue lists, and the browser's Hindi name for Hong Kong is not one of them |
| 8 | What a helper sends | Plain digits, the currency code and the period in the worker's language ("4200 AUD प्रति माह"). Never "4,200", which an Indonesian reads as 4.2. `parseAmount` reads what the worker types: `4,200`, `4 200`, `1,50,000`, `1.700,50` |
| 9 | Currency to offer first | The one the worker used last, else the host country's. The menu shows codes only: with names, the closed menu cut a Hindi name in half |
| 10 | The answer panel | At most half the chat's height; it scrolls inside with a soft shadow on the edge that has more (seven kinds of work do not fit at 360 x 740) |
| 11 | Focus | When a turn ends and focus was lost (the chip it was on is gone), it comes to the answer panel, never into a field (that would open the keyboard unasked). Focus the worker put elsewhere, or the notice that takes it, is left alone |
| 12 | "Start a new interview" | Offered for `session_not_active`, `session_full` and `not_found`, which the contract says the screen answers with `restart` |
| 13 | One session query | The interview is fetched once per visit (`staleTime` forever, dropped when the screen is left), so a background refetch can never replace the chat under the worker's hands |
| 14 | React development mode | `StrictMode` sends the opening turn twice and cancels the first. A production build sends it once. The second request gets a new key; a server still busy with the first answers `409` and the screen waits |
| 15 | D-225 | The redirect mock now holds the server's fixed words. The question stays visible in the conversation, so it is not lost |

## Checking the helpers' sentences

The helpers' answers are text, and the server reads them with word lists (`backend/app/services/coach/extraction_cues.py`). If a worker's amount is not recognised, the coach asks again. This was checked for every language, currency and period on 2026-10-09; run it again after changing any `input.compose.*`, `input.none` or `input.country.*` string. From `backend/` (a throwaway file, not committed):

```python
import json, sys
sys.path.insert(0, ".")
from app.services.coach import extraction_cues as c
from app.services.coach.guard_answers import COUNTRY_WORDS

CURRENCIES = "SGD KRW MYR JPY HKD AUD PHP INR IDR NPR BDT".split()
bad = []
for lang in "en hi tl id ne bn".split():
    j = json.load(open(f"../frontend/src/i18n/coach/{lang}.json", encoding="utf-8"))
    comp = j["input"]["compose"]
    for period in ("month", "week", "year"):
        for cur in CURRENCIES:
            text = comp[period].replace("{{amount}}", "4200").replace("{{currency}}", cur)
            if not (c.number_stated(4200, text) and c.currency_stated(cur, text) and c.period_stated(period, text)):
                bad.append((lang, period, cur, text))
    for period in ("month", "year"):
        text = comp["interest"][period].replace("{{rate}}", "3")
        if not (c.number_stated(3, text) and c.percent_stated(text) and c.period_stated(period, text)):
            bad.append((lang, "interest", period, text))
    if not c.zero_stated(j["input"]["none"]):
        bad.append((lang, "none", j["input"]["none"]))
    for code, label in j["input"]["country"].items():
        if not (c.country_stated(code, label) and COUNTRY_WORDS.search(label.casefold())):
            bad.append((lang, "country", code, label))
print(len(bad), "problems")
```

```bash
cd backend
.venv/Scripts/python.exe check.py     # bash on Windows; PowerShell: .\.venv\Scripts\python.exe check.py
```

Expect `0 problems`. This is a check run by hand, not a test (D-236).

## Results (2026-10-09)

| Check | Result |
|---|---|
| `eslint --max-warnings 0`, `node scripts/check-i18n.mjs` | clean (1,047 English keys; 78 of them in the coach file, which had 4) |
| `prettier --check` on the changed files | clean (the whole-repo check reports every file: line endings on this Windows checkout) |
| `tsc -b` | clean for everything except `src/mocks/axe.ts`: `axe-core` is in `package.json` and the lock file but was **not installed** in this checkout, and `pnpm` would not run from the shell used. Run `pnpm install` and it passes (a fault of this machine, not of the repository) |
| `vitest run src` | **933 passed** in 85 files. Three suites that import `axe-core` cannot load here (`axe.test.tsx`, `scamParts.a11y.test.tsx`, `scamPages.a11y.test.tsx`); they failed to load before this task too |
| New tests | 149 in 12 files: parser 8, helpers 30, errors 21, reducer 9, retry rules 14, key 2, stream client against the recorded streams 15, panel and helpers 23, scroll 6, the interview 16, the page 5 |
| Backend `pytest tests/unit/test_coach_mocks.py` | 86 passed after the redirect mock changed |
| `vite build` | passes. `CoachHome` chunk **28.7 KB (9.7 KB gzip)**, `CoachRoute` 0.7 KB, the English coach strings 3.1 KB. The main chunk (582 KB) holds no Coach route string: the screen is only downloaded for a worker whose flag is on |
| Coverage of the new files | 81 to 100% of lines (the scroll hook 81%, the rest above 85%); whole frontend 40.6% (was 16.7%, D-118) |
| Helpers' sentences against the server's cue lists | 0 problems: 6 languages x 11 currencies x 3 periods, the interest sentences, "None", the 6 country names |

**The browser check** (a throwaway page with the stand-in shell of the app, the recorded streams played with delays, deleted afterwards), at **360 x 740**:

| Measured | Result |
|---|---|
| A whole streamed turn, 112 samples every 40 ms (12 while the reply was arriving) | The stepper, the conversation box and the answer panel each kept **one** position and size; the page never scrolled |
| The browser's layout-shift score for the turn | **0** |
| A turn that failed twice, then the notice | The conversation box stayed 182 px, the panel did not move, shift score 0; the notice is inside the conversation, scrolled into view and focused |
| Every button, field and link | At least 44 x 44 px; text fields 16 px; no horizontal scroll (page width 360) |
| After "Try again" | The reply is in the log once, "Not sent" and the notice are gone, 4 requests in all |
| Hindi, dark theme | Renders correctly; the amount helper sends `4200 AUD प्रति माह` with `language: "hi"` |
| `StrictMode` | Two opening requests, one coach bubble |

**Not verified:** a real turn against the backend with a Gemini key (the opening turn needs the reply model); a real phone, and the phone keyboard's behaviour (D-72); a Slow 3G run in DevTools; a screen reader (NVDA, TalkBack) and `axe` on this screen (D-238); Playwright (NF-FC-025).

## Manual test

**1. The tests, no backend** (PowerShell and bash are the same, from `frontend/`):

```bash
pnpm exec vitest run src/components/coach src/pages/coach src/services/coachService src/mocks/coach.msw src/utils/sse src/utils/coach src/utils/idempotency
```

Expect `177 passed` in 12 files.

**2. The real app.** Start the emulators and the API, then the dev server, as in `NF-F0-005-backend-feature-flags.md` (`.claude/launch.json`: `backend-emulators`, `backend-api-emulator`, `frontend-emulator`). The backend needs a `GEMINI_API_KEY` in `backend/.env.local` for a real reply. Sign in, and put the test user's uid in `flags.coach.allow_uids` of `config/feature_flags` in the emulator UI (http://127.0.0.1:4000). Wait a minute (the flag is read once a minute).

1. Open `http://localhost:5173/coach`. The skeleton, then the coach's question appears word by word. With no Gemini key you get "The coach is busy right now" with **Try again**: that is the failure state working.
2. Tap **Australia**. Your answer appears at once; the reply streams in; the buttons are greyed until it ends; then the job chips appear. The step row does not move while the reply arrives.
3. Choose **Care worker**, then a date, then at the salary step type `4,200` and tap **Send**: the bubble reads `4200 AUD per month`. Try `0` at the salary step: it is refused with a red line and nothing is sent.
4. At a debt question tap **None (0)**. At the interest question send `3` per month.
5. Tap **Type my own answer** and send a sentence with Enter. Paste 1,001 characters: the button turns off and the box says it is too long; nothing is cut.
6. **Drop the stream:** DevTools → Network → set **Offline** while a reply is arriving, then back to **No throttling**. The half reply disappears, your line says **Not sent**, and after a second try (automatic) or **Try again** the reply comes whole, once.
7. **Slow 3G:** DevTools → Network → Slow 3G, send an answer. The dots stay until the first word; the screen does not jump.
8. Scroll up in the conversation while a reply streams: it does not pull you back down, and **Latest message** appears.
9. Reload the page mid-interview: the transcript comes back and the question is the same one (NF-FC-019 adds the resume banner and drafts).
10. At 360 px (DevTools device toolbar): everything fits, nothing scrolls sideways, the panel is within thumb reach above the tab bar.
11. Tab through the screen with the keyboard: the log, the helper's controls, **Type my own answer**. After you answer, focus is on the answer panel.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| The page is the dashboard, not the chat | The `coach` flag is off for this user, or older than a minute. `GET /api/v2/flags` shows it |
| "The coach is busy right now" at once | No Gemini key for the backend, or the free tier is limited (D-58). The screen is right; the backend is not ready |
| Every turn says "still working on your last message" | A turn is stuck on the server; it frees itself after 90 s (`turn_in_progress`) |
| The coach asks the amount again after a helper | The sentence the helper sent was not found by the server's word lists. Run the check above; a wording change in `input.compose.*` is the usual cause |
| `tsc -b` fails in `src/mocks/axe.ts` | `axe-core` is not installed: run `pnpm install` |
| Two requests for the opening turn in the dev console | React's development mode, see choice 14 |

## Rollback

Switch the `coach` flag off first (`config/feature_flags`, `flags.coach.enabled` false, and no uid in `allow_uids`): `/coach` redirects to the dashboard, and nothing of the module is downloaded. Reverting the PR is safe: it changes no data and no backend. Interviews already started stay in `users/{uid}/coach_sessions` for 30 days (`docs/data-model/collections/coach.md`).

## Definition of Done

**Frontend Feature**
- [x] Built with Tailwind and the shared UI kit (`ChatBubble`, `QuickReplyChips`, `StepProgress`, `EmptyState` style)
- [x] Mobile responsive: checked at 360 x 740 in the browser pane
- [ ] Slow network (3G throttled in DevTools): the 30 s and 60 s limits and the retries are tested; the throttled run is manual step 7
- [x] Loading states: the opening skeleton, the typing dots
- [x] Error states: every code of the contract, offline, a dropped stream, a refusal, and a session that cannot go on
- [x] i18n keys in all 6 languages (`check-i18n.mjs` clean); native reading is D-236
- [ ] Screenshots in the PR (four were taken in the browser check; attach them)
- [x] Accessibility, partly: real buttons and labels, `role="log"` with a name, `role="alert"` and `role="status"`, focus kept after a turn, the log reachable by keyboard. `axe` was not run (D-238)
- [ ] Reviewed by a teammate

**Streaming (SSE) endpoint (the client's part)**
- [x] Event types `token`, `slot_update`, `done`, `error` read as `docs/api/v2-coach.md` defines them; the heartbeat is ignored
- [ ] First token under 2 s at the 95th percentile: the server's goal (NF-FC-009), not measurable here
- [x] Client disconnect cancels the upstream call: leaving the screen or the page aborts the request (tested)
- [x] The frontend retries a dropped stream and never shows a half-rendered message as final

**Feature-flagged module**
- [x] Route and nav entry hidden when the flag is off (unchanged: `FlagRoute`)
- [x] Production bundle and v1.0 behaviour unchanged with the flag off: no Coach string in the main chunk
- [x] Own lazy-loaded chunk (28.7 KB)
- [x] Rollback path stated (above, and in the PR)

## Commit and PR

Branch: `feature/NF-FC-017-coach-chat-ui` (already checked out).

Commit message:

```
feat(coach): add chat screen with streamed replies and answer helpers
Refs: NF-FC-017
```

PR title: `feat(coach): Coach chat screen with streamed replies (NF-FC-017)`

PR description:

```
## What

/coach is now the interview screen. The coach speaks first; its reply streams in word by word.
The worker answers with chips, an amount and currency field, a date, or text. A step row shows
where the interview stands. A stream that drops is tried again once and then offered as Try
again, and a half reply is never shown as final.

## How it works

- fetch + stream reader (not EventSource), a small SSE frame parser, 30 s to the first byte and
  60 s per turn, as docs/api/v2-coach.md says.
- Words and facts are provisional until `done`; they are committed together. A failed turn leaves
  nothing behind and marks the worker's line "Not sent".
- Every retry of one turn uses the same Idempotency-Key, so a turn the server finished is
  replayed, not repeated. `409 *_in_progress` waits for Retry-After.
- Helpers write their answer as text ("4200 AUD per month"), in the worker's language; checked
  against the server's cue lists for 6 languages x 11 currencies x 3 periods.
- Own lazy chunk (28.7 KB, 9.7 KB gzip); no Coach string in the main chunk.
- docs/mocks/coach/turn-07-redirect.sse now holds the server's fixed words (D-225).

## Out of scope

Voice and language switch (NF-FC-018), resume banner, drafts and offline queue (NF-FC-019),
score screen (-020), plan view (-021), dashboard card (-022), translation and axe audit (-023),
Playwright (-025). At stage `plan` the screen says the answers are in and points home.

## Checks

eslint, prettier (changed files), check-i18n, vite build: clean. vitest: 933 passed (149 new).
tsc -b: clean except src/mocks/axe.ts when axe-core is not installed locally. Backend
test_coach_mocks.py: 86 passed. At 360 x 740 a whole streamed turn moved nothing (layout shift
0), and every control is at least 44 px.

Not verified: a real Gemini turn, a real phone, Slow 3G, a screen reader, axe on this screen.

## Rollback

Turn the `coach` flag off first. No data or backend change, so reverting is safe.

## Notes for review

- The chat sends the session's language, not the app's, until NF-FC-018 (D-237).
- Wording in hi, tl, id, ne and bn was written by the team and needs a native reader (D-236);
  a change to a sentence a helper sends must be re-checked against extraction_cues.py.
- Deferred items updated: D-99, D-112, D-118, D-225; new D-236 to D-239.
```
