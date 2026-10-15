# NF-SA-017 — Explainer, next steps and read-aloud

## Summary

Under the verdict card on `/scam-check`, the plain stop-gap of NF-SA-016 (`ExplainerInterim`) is replaced by a real explanation, numbered steps and a read-aloud button. For a scam, from top to bottom:

| Part                  | What it shows                                                                                                                                                                                                                                         |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Listen to this**    | A full-width button (44 px high). It speaks the whole explanation in the worker's language with the phone's own voice, and turns into **Stop listening** while it speaks. It is not on the page at all when the device has no voice for that language |
| Why this is a scam    | One entry per trick the message uses: the trick's name, then the explainer's own words for this message                                                                                                                                               |
| What the sender wants | One plain sentence, in its own block                                                                                                                                                                                                                  |
| What to do now        | The three steps as a numbered list: a large number in a circle, the step beside it. A screen reader hears "Step 1." before each (the drawn digit is hidden from it)                                                                                   |

For a message that is not a scam: the reassurance and the tip under "Good to know", and the same button. When the explanation could not be written (`explainer: null`), the notice from 016 stays and there is no button. The explainer's text carries `lang="hi"` (or its own language), so a screen reader pronounces it right even under a screen in another language.

Not in this task: the history and "Warn other workers" (NF-SA-018), the axe pass and the translation audit (NF-SA-019). No backend change: it reads the `explainer` that `POST /api/v2/scam/analyze` already returns.

## How read-aloud decides

| Question                      | Answer                                                                                                                                                                                                                                                                            |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Which language does it speak? | The language the explainer is **written in** (`explainer.language`), not the screen's. They are the same unless the worker switches the screen language while looking at a result                                                                                                 |
| Which voice?                  | The best installed voice whose language matches: a voice stored on the phone first (it works with no signal), then the system default. `hi-IN` and Android's `hi_IN` both mean Hindi; Tagalog also accepts `fil` (Filipino) and Indonesian also accepts `in` (Java's code for it) |
| When is the button shown?     | Only once the browser has listed its voices (Chrome does it after the page loads, so the hook waits for `voiceschanged`) and one of them matches. No speech engine, or no voice for the language: nothing is rendered                                                             |
| What does it say?             | The "why" texts, what the sender wants, then the steps, **one utterance per piece**, so the voice pauses between ideas and no browser cap on one long utterance applies                                                                                                           |
| Headings and "Step 1"?        | Spoken only when the screen's language equals the explainer's. Otherwise a heading in one language would be read by a voice chosen for another, as noise. The mock for the high-risk case is a Hindi explanation under an English screen, which is exactly this case              |
| Controls                      | Play and stop only. Pause is unreliable on Android Chrome, where most of our workers are                                                                                                                                                                                          |
| When does it stop?            | On **Stop listening**, when the result goes away (check another message, leave the page), and by itself at the end                                                                                                                                                                |
| When the voice fails          | If the engine reports an error of its own (not a stop), a line says "We could not play the voice. Check your phone's sound and try again." and the button lets them try again. A stop is never reported as a failure                                                              |

## Files

| File                                                                                                                   | Change                                                                                                                |
| ---------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/utils/speech.ts` (new)                                                                                   | `pickVoice`: language to installed voice (underscore tags, `fil`, `in`, local voice first)                            |
| `frontend/src/utils/explainerSpeech.ts` (new)                                                                          | What to say, one piece per breath; headings only when they are in the same language                                   |
| `frontend/src/hooks/useSpeech.ts` (new)                                                                                | The Web Speech API: voices, speak a queue, stop, stop on unmount, failure flag                                        |
| `frontend/src/components/scam/ExplainerSection.tsx`, `NextSteps.tsx`, `ReadAloudButton.tsx` (new)                      | The section, the numbered steps, the button                                                                           |
| `frontend/src/components/scam/ScamResult.tsx`                                                                          | Shows `ExplainerSection`. `ExplainerInterim.tsx` is removed                                                           |
| `frontend/src/i18n/scam/{en,hi,tl,id,ne,bn}.json`                                                                      | 6 new keys each under `result`: `stepLabel`, `whyTitle`, `benignTitle`, `readAloud`, `stopReading`, `readAloudFailed` |
| `frontend/src/mocks/fakeSpeech.ts` (new)                                                                               | A fake speech engine for the tests (jsdom has none)                                                                   |
| Tests: `speech.test.ts` (8), `explainerSpeech.test.ts` (4), `useSpeech.test.ts` (10), `ExplainerSection.test.tsx` (16) | See below                                                                                                             |

No shared files (`package.json`, the lockfile and the workflows are untouched), no new dependency.

## Decisions

| #   | Decision                                                                              | Why                                                                                             |
| --- | ------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 1   | One button reads the whole section, and the benign answer gets it too                 | A worker who finds reading hard needs the steps most; the benign tip is short and costs nothing |
| 2   | The button is hidden, not disabled, when there is no voice                            | The task says it hides itself. A greyed button asks the worker to work out why                  |
| 3   | Voice by the explainer's language, headings only when the screen matches              | Never read a heading in one language with a voice for another                                   |
| 4   | Short utterances, one per piece                                                       | A pause between ideas, and Chrome cuts off long single utterances                               |
| 5   | Play and stop only                                                                    | Pause does not work reliably on Android Chrome                                                  |
| 6   | A voice stored on the phone is preferred                                              | A worker abroad with no data still hears their next steps                                       |
| 7   | The number in the circle is hidden from a screen reader and "Step N." is added for it | A list with its default numbering removed is not announced with numbers by every screen reader  |
| 8   | Strings are written in all six languages now                                          | `scripts/check-i18n.mjs` requires every key in every language. They need a native read (D-157)  |

## Manual test

Dev server with the emulators and the API as in `NF-F0-005-backend-feature-flags.md`, signed in, with the `scam` flag on for the test user. Without a Gemini key the check answers 5xx; to see the section without the backend, use the tests.

1. Check a scam message in English. Under the card: **Listen to this**, "Why this is a scam", "What the sender wants", "What to do now" with 1 to 3 in circles.
2. Press **Listen to this**. It speaks the headings, the explanation and "Step 1." to "Step 3.", and the button reads **Stop listening**. Press it: the voice stops at once and no error line shows.
3. Press it again and click **Check another message** while it speaks: the voice stops.
4. Switch the app to Hindi (header) and check a message. If the browser has no Hindi voice, there is **no** button. With a Hindi voice installed, the button appears and speaks Hindi.
5. A message that is not a scam: "Good to know", the reassurance and the tip, and the button.
6. DevTools, device toolbar at 360 px: no sideways scroll, every button 44 px high.
7. On a real Android phone: D-156.

## Checks run (2026-10-07)

| Check                                                                                                                       | Result                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm lint` (`--max-warnings 0`), `tsc -b`, `pnpm build`                                                                    | clean (the build's chunk-size warning was there before)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `node scripts/check-i18n.mjs`                                                                                               | OK: 3 namespaces, 6 languages, 908 English keys                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `prettier --check`                                                                                                          | The new files pass. The edited files that were already in the repo (`ScamResult.tsx`, the six `scam/*.json`) are flagged only because this Windows checkout has CRLF line endings (git `autocrlf`); an untouched file such as `VerdictCard.tsx` is flagged the same way, and all of them pass with `--end-of-line crlf`                                                                                                                                                                                                                                                                                                          |
| New tests                                                                                                                   | **38 passed** in 4 files (8 + 4 + 10 + 16)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `pnpm test`, all of `src`                                                                                                   | **61 files, 546 tests: 544 passed, 2 failed.** The two failures are in `ScamCheckHome.msw.test.tsx` ("sends it as a form to the same route", "explains an unreadable screenshot"): the screenshot upload through the mock server never answers in this environment. They fail identically on a clean copy of `HEAD` taken with `git archive` (2 failed, 13 passed there too), so they are not from this task (see "Noticed" below)                                                                                                                                                                                               |
| Mutation checks                                                                                                             | Breaking the underscore tags (`hi_IN`) fails 4 tests; removing the stop on unmount fails 2; showing the button with no voice fails 3. Each was restored                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **Real browser** (the in-app Chromium with its real speech engine, from the mock JSON on a temporary page that was removed) | English: the button shows; pressing Enter on it makes `speechSynthesis.speaking` true, the button reads "Stop listening", and the engine is handed 9 pieces (3 headings, 2 reasons, what the sender wants, 3 steps with "Step N.") with the voice _Microsoft David_ and `lang: en-US`; a second press stops it (`speaking` false, no error line). Hindi: the whole section is in Hindi with `lang="hi"` on the text, and there is **no button** because the machine has no Hindi voice. Benign: "Good to know" and the button. **360 px**: page width 360, no element past the right edge, every button 44 px, no console errors |

## Not done, and why

- **Not tried on a real Android phone, so "works for EN / HI / ID on Android Chrome" is not yet confirmed** (D-156). The browser available here had English voices only. The Hindi and Indonesian paths are tested against a fake engine, and the handling of Android's tags is based on what its engine reports, not on a device.
- **A screenshot of the new section** could not be captured: the in-app browser's capture came back tiled or at the top of the page when emulating a phone. The layout was checked by measuring the page instead.
- **The five other languages were written by the team, not by native speakers** (D-157).
- **No axe run** (NF-SA-019).

## Noticed, not fixed

- `ScamCheckHome.msw.test.tsx`: the two screenshot-upload tests fail on a clean `HEAD` in this environment (Node 24.13.1, jsdom 29.1.1, msw 2.15.0). The request is still pending when the test's one-second wait ends. It looks like the `File` and `FormData` of jsdom meeting the mock server's multipart reading, but that is a guess; nobody has found the cause. CI may be fine (a different Node), so check the last CI run on `main` before spending time.
- `node_modules` in this checkout had no `jsdom`, `msw`, `@testing-library/*` or `@playwright/test`, so no jsdom test could run until `pnpm install --frozen-lockfile` was run (no lockfile change).

## Definition of Done (frontend feature)

- [x] Tailwind and the existing UI primitives (`Button`, `card-surface`); mobile responsive, **checked at 360 px**
- [x] The empty and error states: `explainer: null` keeps its notice and shows no button; no voice shows no button; a voice error shows a line
- [x] Keyboard navigable (the button is a real button; Enter tested in the browser), semantic headings and lists, `lang` on the explainer's text
- [x] Colour is never the only signal (icon and words on the button; the failure is words)
- [x] All strings through i18n keys, six languages, parity check green
- [x] Tests, lint, types, build
- [ ] Read-aloud confirmed for EN / HI / ID on Android Chrome (D-156)
- [ ] A native-speaker read of the new strings (D-157)
- [ ] An axe pass (NF-SA-019)
