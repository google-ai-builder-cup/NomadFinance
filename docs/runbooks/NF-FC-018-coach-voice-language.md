# NF-FC-018 — Coach voice input and mid-interview language switch

## Summary

Two additions to the Coach screen (`/coach`, built by NF-FC-017), plus the two new pillars in the dashboard's welcome band.

| What | Where | How it behaves |
|---|---|---|
| **Voice input** | A microphone in the answer box, and one beside "Type my own answer" on the quick-answer screen | Dictation with the browser's speech recognition. It fills the box as words are heard and **never sends**: the worker reads it and presses send. Offered only in English, Hindi and Indonesian and only where the browser has speech recognition; hidden everywhere else |
| **Language switch** | A "Coach language" selector in the Coach header | One setting with the header's selector: the whole app changes language, and the coach carries on in it. The screen sends a turn with **no text and the new language** (the contract already allows it) once the current turn is over; the server keeps the session, the answers and the stage, says the language changed and asks the same question again |
| **Welcome band** | "Welcome, {name}" on the dashboard | Quick-action buttons for **Plan with the Coach** and **Check a message** (Scam Check), and two more floating pillar icons, each shown only while its flag is on for the worker, like the dashboard cards and the navigation |

## Why the Coach is not visible in production

The Coach tab, the dashboard card, the new welcome-band button and the `/coach` route all depend on the **`coach` feature flag**. In production `config/feature_flags` has only `scam` set, so the app fails closed and shows none of them (and `/coach` sends the worker back to the dashboard). To switch it on, set `flags.coach` to `{ "enabled": true, "allow_uids": [] }` in that document; the backend keeps its own copy for about a minute. A browser that opened the app before the NF-FC-017 deploy can keep the old build until the PWA's "new version" banner is accepted: a hard reload or clearing the site's data fixes it. Nothing is wrong in the route or the build: the deployed bundle contains `/coach` and its chunks load.

## Files

| File | Change |
|---|---|
| `frontend/src/utils/voiceInput.ts` (new) | Which languages offer the microphone, the browser check, the transcript and the meaning of each recognition error |
| `frontend/src/hooks/useSpeechInput.ts` (new) | One dictation run: start, stop, cancel; ends when the language changes or the screen is left |
| `frontend/src/components/coach/TextComposer.tsx`, `AnswerPanel.tsx` | The microphone, a status line (listening, where the voice goes, or why it stopped), and the microphone on the quick-answer screen |
| `frontend/src/components/coach/LanguageSwitch.tsx` (new), `pages/coach/CoachHome.tsx` | The switch in the header |
| `frontend/src/hooks/useCoachChat.ts`, `components/coach/CoachChat.tsx`, `hooks/useUiLanguage.ts` (new) | The chat follows the app's language and sends the switch turn; every later answer goes in the new language |
| `frontend/src/components/dashboard/GreetingBand.tsx` | The two quick actions and two icons |
| `frontend/src/i18n/*.json`, `i18n/coach/*.json` | About 10 voice and switch phrases and 2 dashboard labels, in all six languages |

No backend change and no shared file (`package.json`, lockfile, `firebase.json`, workflows) was touched. An existing `utils/speech.ts` (used by `hooks/useSpeech.ts`) was overwritten by mistake while writing this and **restored from `HEAD`** before anything else; the new code lives in `voiceInput.ts`.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Voice fills the box, no auto-send | The worker checks the words first; the coach checks every figure anyway |
| 2 | One language setting | The Coach switch, the header selector and the coach's language are the same; the switch is for this tab only, never the saved `preferred_language` |
| 3 | A resumed interview in another language | Not switched on opening; the worker's next answer goes in the app's language and the server carries on in it |
| 4 | A change during a turn, or after a failed turn | Sent after the turn ends; never on top of a failed turn (the worker retries that one as it was) |
| 5 | Voice privacy | A note under the box while it listens: the voice goes to the browser's speech service |
| 6 | The new welcome-band buttons | Shown only with their flags on |

## Results

**Offline (2026-10-09):** the frontend suite is 1,083 tests, all passing (94 files), 41 new; `tsc`, `eslint`, `prettier`, the i18n check (1,059 English keys × 6 languages) and the production build are clean.

| Check | Result |
|---|---|
| Speech helpers | The three languages and their tags; the standard and Chrome-prefixed API; every error code mapped (denied, nothing heard, no microphone, network, other; "aborted" says nothing) |
| The microphone | Shown in en/hi/id with the API; hidden in tl/ne/bn and without the API; listens in the coach's language; fills the box as words arrive; adds to what is typed; never sends; stops and keeps the words; dropped when the answer is sent, the language changes or the screen is left; every error says why and typing still works; starts again after a problem |
| On the quick-answer screen | The microphone opens the box already listening; hidden where unavailable; "Type my own answer" opens it without listening; going back returns the quick answers and the microphone |
| The language switch | The six languages by their own names; changes the whole app and is kept for the tab; follows a change made in the header |
| The chat | A change sends a no-text turn in the new language after the opening, after an answer, and after a running turn; the answers and step stay; the next answer goes in the new language; no switch when nothing changed; none on top of a failed turn; a retry goes out unchanged with its key and the switch follows |
| Welcome band | The four v1.0 buttons only when both flags are off; Scam Check and the Coach each added by their own flag; both in navigation order |

**In the emulator (Firebase Auth and Firestore emulators, the backend and Vite running locally, a seeded worker, a real Gemini key):**
- The dashboard's welcome band shows six quick actions and five floating pillar icons; with the coach flag off (as in production) the Coach tab, card, button and route are absent and `/coach` returns to the dashboard.
- With the flag on, the Coach loads, the real model opens the interview, "Singapore" is extracted and confirmed.
- Choosing Hindi in the **Coach language** switch changed the whole app to Hindi and sent one turn with no text; the coach replied in Hindi and asked the same question again. Through the API: session language `hi`, stage `intro`, `destination_country` kept (confirmed), turn count unchanged, messages in both languages.
- The microphone buttons open the box and, with the microphone blocked in this pane, show the Hindi "microphone is blocked" line while typing still works.

**Not verified:** dictation on a real phone (Android Chrome with English, Hindi and Indonesian is the tracker's finish line and still to be tried); how the Hindi, Nepali and Bengali phrases read to native speakers (D-224).

## Manual test

```bash
cd frontend
pnpm vitest run src/utils/voiceInput.test.ts src/components/coach src/components/dashboard/GreetingBand.test.tsx
```

Local run against the emulators (`.claude/launch.json`: `backend-emulators`, `backend-api-live` for a real Gemini key from `backend/.env.local`, `frontend-emulator`): sign in as a seeded worker, set `config/feature_flags.flags.coach.enabled` to true in the Firestore emulator, open `/coach`, answer a question, pick another language in "Coach language", and see the coach continue in it. On a phone, open the deployed app in Chrome, allow the microphone and press the microphone beside "Type my own answer".

## Limits (D-224, D-225)

Voice only in three languages; the audio goes to the browser's speech service; not tried on a phone; the wording was not read by native speakers. Seen but not fixed: the reply model once says "You have changed your language" after an ordinary answer (D-225), and slow free-tier replies end as "Not sent".

## Definition of Done (Frontend)

- [x] Language switch keeps the session and the stage (checked live and in tests)
- [x] Voice hides where the browser or the language does not support it
- [x] All user-facing strings through i18n keys in 6 languages (key check green)
- [x] Types strict, lint and format clean, no shared file touched, tests added
- [x] Checked in the emulator with screenshots
- [ ] Voice works on Android Chrome for EN / HI / ID (needs a phone)
- [ ] Wording reviewed by native speakers (D-224)
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-FC-018-coach-voice-language` (already checked out).

```bash
git commit -m "feat(coach): add voice input, language switch and welcome-band shortcuts" -m "Refs: NF-FC-018"
```

PR title: `feat(coach): voice input, mid-interview language switch and new pillar shortcuts (NF-FC-018)`
