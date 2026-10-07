# NF-SA-016 — Verdict card: risk meter, type, tactics, highlights

## Summary

The result of a scam check on `/scam-check` is now a real verdict card (it replaces the plain interim result of NF-SA-015). From top to bottom:

| Part | What it shows |
|---|---|
| Header | A shield icon and "This looks like a scam" (or "This does not look like a scam"); a note when the worker has checked this message before |
| Risk | For a scam: the existing `RiskMeter` (three segments, the level in words, an icon). For a message that is not a scam: a "No scam found" badge, no meter |
| Kind of scam | The type, in the worker's language ("Illegal recruitment fee") |
| Not sure | A note when the verdict's confidence is below 0.7: "We are not fully sure about this one. Be careful and check it with someone you trust." |
| How it tries to trick you | One chip per tactic. **Tap a chip to see how that trick works**: the explainer's own words for this message when it was written, else a short general line, so a tap always answers |
| The message | The checked message with the wording that gave it away **bold and underlined** (and announced to a screen reader); each hidden value (`[PHONE]`, `[URL]`, ...) a small labelled chip ("phone number hidden") |
| Contacts in the message | Each link, number, address, chat account or sender, as **plain text, never a link**, with what is wrong with it (shortened link, look-alike letters, copies the real site `mom.gov.sg`, an expensive number, a number from outside the route) and how often workers reported it |
| Looks like scams we know | The kinds of scam the message resembles, and "Workers on your route sent N reports like this one" (10 or more at the cap) |

Under the card, `ExplainerInterim` keeps "what the sender wants" and "what to do now" (or the reassurance and tip) so no worker loses their next steps until NF-SA-017 replaces it, and a "Check another message" button.

Not in this task: the full explainer section, numbered steps and read-aloud (NF-SA-017), the history and the "Warn other workers" button (NF-SA-018), the accessibility and translation audit (NF-SA-019). No backend change: the card reads what `POST /api/v2/scam/analyze` already returns.

## Colour is never the only signal

Every state has an icon and words: the title has a shield, the meter has the level in words and a badge icon, each flag and "reported" line is a badge with an icon, the giveaway wording is bold, underlined and read out ("Suspicious words:"), and a hidden value is a labelled chip. A test checks the icon next to the words for the warnings.

## What a stranger wrote is never HTML and never a link

The message is whatever a scammer wrote. It is rendered only as text nodes (a test puts an `<img onerror>`, a `<script>` and an `<a href>` in it and checks none becomes an element), and a contact point is never an anchor or a button: the only buttons on the card are the tricks, which explain. A test fails if any `<a>` or `[href]` appears, and it was shown to fail when a contact point was made a link on purpose.

## Files

| File | Change |
|---|---|
| `frontend/src/components/scam/VerdictCard.tsx` (new) | The card |
| `TacticChips.tsx`, `HighlightedMessage.tsx`, `IndicatorList.tsx` (new, same folder) | Tap-to-explain chips; the message with its highlights; the contact list |
| `ScamResult.tsx`, `ExplainerInterim.tsx` (new) | The result view: card, stop-gap explanation, check another. `InterimResult.tsx` is removed |
| `frontend/src/utils/scamHighlight.ts` (new) | Cuts the message into plain, highlighted and token pieces: case-insensitive, every occurrence, overlapping phrases merged, Indic scripts safe (13 tests) |
| `frontend/src/pages/scam/ScamCheckHome.tsx`, `src/types/scam.ts` | Shows `ScamResult`; the response type gains `similar` |
| `frontend/src/i18n/scam/{en,hi,tl,id,ne,bn}.json` | About 60 new keys per language: kinds of scam, tricks (name and general explanation), flags, kinds of contact, hidden values, counts with plural forms |
| `frontend/src/mocks/scamResult.ts` (new) | The mock answers as typed values, for tests |
| Tests: `VerdictCard.test.tsx` (19), `TacticChips.test.tsx` (9), `ScamResult.test.tsx` (6), `scamHighlight.test.ts` (13), `src/i18n/scamCard.test.ts` (30) | See below |

No shared files (`package.json`, the lockfile, the workflows are untouched), no new dependency. The page's own test (`ScamCheckHome.msw.test.tsx`) passes unchanged.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The `RiskMeter` that already exists is reused as is | One risk scale across the app (`utils/risk.ts`) |
| 2 | A message that is not a scam gets a badge, not a meter | A meter reading "Low risk" under "this is not a scam" would say two things |
| 3 | A tap on a chip uses the explainer's words, else a general line per trick | The explainer can be unavailable (the contract), and the chips must still work |
| 4 | Contacts are text, not links | A scammer's address must not be one tap from being opened |
| 5 | Tap targets are 44 px (the chips and "Check another"), measured in the browser | A phone, a thumb, a worker in a hurry |
| 6 | Strings are written in all six languages now | `scripts/check-i18n.mjs` requires every key in every language, so a key cannot ship in English only. They need a native read (D-154) |
| 7 | A stop-gap `ExplainerInterim` stays | NF-SA-017 owns the explainer section; until it lands, the next steps must not vanish |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `pnpm lint`, `tsc -b`, `pnpm build` | clean (the build's chunk-size warning was there before) |
| `node scripts/check-i18n.mjs` | OK: 6 languages, 902 English keys |
| `pnpm test` (all of `src`) | **57 files, 507 tests passed**; 77 of them are new (the five files above) |
| The four mock cases | Each renders: high (meter High, two flagged contacts, five-times-reported number, both highlights, tokens as chips), medium, low (with the "not sure" note) and benign (no meter, no highlights). Also the "explainer unavailable" mock |
| Every id has a label | A test reads the taxonomy (8 kinds of scam, 6 tactics) and the contract's flags, contact kinds and tokens, and requires a string in each of the six languages, with the plural forms each language uses |
| **360 px** | Rendered in the browser pane at 360 px width from the four mocks' real JSON, in English, Hindi and Bengali: **no horizontal overflow** (page width 360, the widest element ends at 360) in any case, and the card reads in one column. Screenshots were checked by eye for high, low and benign |
| Tap targets | Measured in the browser: every chip and "Check another message" is 44 px high |
| Tap to explain | Clicked in the browser: `aria-expanded` goes true, the panel it controls shows the explainer's text for that trick, a second click closes it; no `<a>` on the page |
| Mutation check | Turning a contact point into a link fails the "never a link" test; restored |

The temporary preview page used for the browser check was removed.

## Not done, and why

- **The five other languages were written by the team, not by native speakers** (D-154).
- **No axe run** (the tool is not in the project; NF-SA-019 does it), and no test on a real Android phone: the 360 px check is the browser's emulation.
- **A scam of low risk shows a green tick** in the meter's badge (the meter reuses the "safe" badge icon for the low level). The words say "Low risk" and the title says scam, but a tick could read as "fine" (D-155).
- **The explanation is the stop-gap** (NF-SA-017), and the report button and history are NF-SA-018.

## Definition of Done (frontend feature)

- [x] Tailwind and the existing UI primitives; mobile responsive, **checked at 360 px**
- [x] The empty and error states of the screen are unchanged; the card handles an unavailable explainer, no tactics, no contacts and no similar scams
- [x] Keyboard navigable (the chips are buttons: Tab, Enter and Space tested), semantic headings and regions, `aria-expanded` on the chips, a named meter
- [x] Colour is never the only signal (icon and words)
- [x] All strings through i18n keys, six languages, parity check green
- [x] Tests, lint, types, build
- [ ] A native-speaker read of the new strings (D-154)
- [ ] An axe pass and a real-phone check (NF-SA-019)
