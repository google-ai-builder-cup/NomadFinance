# NF-SA-019: Scam module i18n and accessibility pass

## Summary

Two things, as the tracker asks: every scam string exists in all six languages, and `axe` reports nothing serious or critical on any scam screen. Both hold. The pass also found and fixed six faults that `axe` cannot see, which are the larger part of the work.

| Part                       | Result                                                                                                                                                                                                                                                                                                                                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **i18n**                   | Already complete: 959 keys in 6 languages, parity script green, no key used in code that English lacks, no key unused, no hard-coded English in a scam screen. What was missing was a guard for what the parity script cannot see: a string left in English, a string in the wrong script, a string that would show as a raw key on a screen. Those are now tests |
| **axe, in a real browser** | Every rule on, including colour contrast and tap-target size. 17 screens and states in English, Hindi and Bengali, plus four states of the report sheet, in the light and the dark theme: **0 violations**. Each of the 17 alone (English, light): 0 violations of any severity                                                                                   |
| **axe, in CI**             | Every scam screen state in six languages (82 tests, each a screen state) fails the build on a serious or critical finding. It runs in jsdom, which has no layout, so colour contrast and tap-target size are not judged there (see below)                                                                                                                         |
| **Contrast**               | 402 texts per theme measured in the browser, worst case over every gradient: **4.89:1 light, 5.71:1 dark** (4.5:1 needed). The colour pairs the scam screens use are also tested from `tokens.css` in both themes, in CI                                                                                                                                          |
| **Fixed**                  | A text box outline at 1.29:1, error text at 2.5:1 on dark, four buttons under 44 px, a Tab order that jumped up the screen, a choice shown by colour alone, and focus lost in five places                                                                                                                                                                         |

No backend change. **Shared files: `package.json` and `pnpm-lock.yaml`** (the `axe-core` dev dependency, below).

## What was found and fixed

| #   | Fault                                                                                                                                                                                                                                                                          | How it was found                                                                                                                                                                        | Fix                                                                                                                                                                                                                                                                                                                                     |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **The outline of the message box was 1.29:1 against its card (1.61:1 in dark).** A text box is found by its outline, and WCAG 1.4.11 asks for 3:1. `axe` does not test this                                                                                                    | Measured in the browser                                                                                                                                                                 | The box in the check screen and in the report sheet uses `muted-foreground` at 80%: **3.98:1 light, 5.9:1 dark**                                                                                                                                                                                                                        |
| 2   | **Error text and error icons were the `destructive` colour: 2.5 to 2.9:1 on dark surfaces.** That is the fill of a danger button, not a text colour. The states that show it (a message too long, a rejected file, a failed "Show more") were not on screen in the browser run | The new colour-token test failed on 3 pairs                                                                                                                                             | `danger-ink`, the token made for text, in seven places in five files. A test records why: `destructive` is 2.6:1 as text on a dark card                                                                                                                                                                                                 |
| 3   | **Four buttons under 44 px**, which the 016 runbook says every control on these screens is: "Check this message" (40 px), "Try again" in an error notice (32 px) and on the history and stored-check error states (36 px)                                                      | The first two measured in the browser (in Bengali, where it showed first); the two on the history and stored-check error states by their size class (`h-9`, 36 px)                      | `min-h-11` on each. No control on the 17 screens is under 44 px now (measured)                                                                                                                                                                                                                                                          |
| 4   | **Tab order jumped up the screen in the report sheet.** On a phone the two buttons were stacked in reverse, so Tab went from Cancel (y 835) to Send (y 783). WCAG 2.4.3                                                                                                        | A script comparing every control's position with its place in the tab order                                                                                                             | The buttons are in the order they are drawn: Cancel, then Send, stacked or side by side                                                                                                                                                                                                                                                 |
| 5   | **The chosen mode (Paste text / Screenshot) was told by colour alone** (a pink border and tint). `aria-pressed` tells a screen reader, not a person who cannot tell the colours apart                                                                                          | Reading the markup against "colour is never the only signal" (016)                                                                                                                      | A tick beside the chosen mode                                                                                                                                                                                                                                                                                                           |
| 6   | **Focus was lost in five places.** The button the worker pressed is replaced by something else, and focus falls back to the top of the page: the keyboard user starts again from the header, and a screen reader says nothing about what happened                              | Reading each flow for the element that holds focus and then unmounts. **Not seen in a browser before the fix**; the tests below pin the new behaviour and were shown to fail without it | Focus now goes to: the progress while a check runs; the verdict's heading when it finishes; the error notice when it fails; the confirmation after "Send warning"; the first new row after "Show more" (on the last page the button vanishes). A stored check opened from the history takes no focus. One small hook, `useFocusOnMount` |

## How it was measured

**Real browser.** The in-app Chromium at 360 px, on a temporary page that rendered the real pages and components (check screen in each state, five results, the report sheet in four states, history, empty history, a stored check, the Radar block) from the mock answers, with their data put straight into the query cache so no backend was needed. `axe-core` 4.14.0 ran with every rule on, in the light theme and in the dark one, in English, Hindi and Bengali. The page was removed afterwards.

**Why a second contrast audit.** `axe` cannot read a background that is a gradient and marks the text "needs review". There were 14 such texts in light and **205 in dark**, because dark cards have a faint white gradient. Those are not passes. A second audit takes every visible text, walks up its backgrounds, and takes the worst case over every gradient stop and every translucent layer. It was checked first with a planted fault: faint grey text at 2.07:1 was flagged, grey at 4.54:1 passed, and a grey over a gradient that goes dark was flagged.

**Landmarks.** The one finding `axe` made when the 17 views were stacked on one page was `landmark-unique` (moderate): six results with identical headings in one page have the same region names. Each view alone: 0 violations of any severity.

**Counted as passing only in a browser:** contrast, tap-target size (`target-size`), what is visible and where (the Tab-order script). The dark-theme gradient, the sticky bar of the sheet and the 44 px buttons were all found this way.

## The checks that stay in CI

| Test                                                                                                  | What it does                                                                                                                                                                                                                                                                                                                                                                                                 |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/mocks/axe.ts` (the helper) and `axe.test.tsx` (8)                                                | Runs `axe` on a screen and returns what is serious or worse. The test proves it **can fail**: an unnamed button (critical), a field with no label, an image with no alternative, a dialog with no name, a bad list. Also finds an i18n key shown as it is, as text or as an accessible name                                                                                                                  |
| `scamParts.a11y.test.tsx` (44)                                                                        | The result (five states) in six languages, the sheet in six, the Radar block in six, a tactic opened, the read-aloud button shown and speaking                                                                                                                                                                                                                                                               |
| `scamPages.a11y.test.tsx` (38)                                                                        | The check screen, the history and a stored check in six languages; the check screen in screenshot mode, with a file chosen, waiting, after a long wait, with the answer, with three kinds of error, with a message too long, with a rejected file; the history empty, failed and with a failed "Show more"; a stored check gone, failed and not a scam. Each asserts no serious `axe` finding and no raw key |
| `tokens.contrast.test.ts` (50)                                                                        | Reads the real `tokens.css`. 16 text pairs at 4.5:1 and 7 graphics at 3:1, in both themes. It also shows it can fail                                                                                                                                                                                                                                                                                         |
| `scamStrings.test.ts` (22)                                                                            | Nothing is left in English unless listed on purpose (the Tagalog loan-words and the counter format); Hindi, Nepali and Bengali are in their script and Tagalog and Indonesian are in none of those; the three Radar labels are translated                                                                                                                                                                    |
| `useFocusOnMount.test.tsx` (4); added to `ScamCheckHome`, `ReportButton` and `ScamHistory` tests (11) | Where focus goes, the sheet's order, the tick, and 44 px on the buttons that were short                                                                                                                                                                                                                                                                                                                      |

Nine deliberate breaks were each caught by the right test and restored: the progress, the verdict, the sent message and "Show more" not taking focus; the sheet buttons reversed again; a Hindi string left in English and a Bengali one in Latin letters; the muted text made too light; the Close button losing its name; the message box losing its label.

## Shared files

`frontend/package.json`, one line in `devDependencies`:

```diff
     "@types/react-dom": "18.3.7",
+    "axe-core": "4.14.0",
```

`frontend/pnpm-lock.yaml`: 9 added lines (the importer entry, the package with its integrity hash, and its snapshot), no line removed. `pnpm install --frozen-lockfile` accepts it. Dev-only: nothing of it reaches the app. `axe-core` has no dependencies and ships its own types. I did not run `pnpm add`: with the pnpm on this machine (9.15.9) it also deletes 14 `libc:` lines that a newer pnpm wrote into the lockfile.

## Decisions

| #   | Decision                                                                                                                                           | Why                                                                                                                                                 |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | The tracker's bar is "0 serious or critical"; CI holds to it. A survey at the lowest severity, run in jsdom before the fixes, found nothing either | Stricter than asked costs nothing here, but a gate that fails on a moderate best-practice finding in a screen shown without its page would be noise |
| 2   | The text box got a darker outline in these two places, not a new `--input` token                                                                   | `--input` is every field in the app; changing it is a design-system decision for the owner of the tokens                                            |
| 3   | Error text uses `danger-ink`                                                                                                                       | It is the token made for text; `destructive` stays for fills                                                                                        |
| 4   | Focus moves to the progress, the verdict, the error and the confirmation, and not to a stored check opened from a list                             | Where the control the worker used has gone, focus must go somewhere; opening a page from a list is the router's job                                 |
| 5   | D-155 (a green tick on a low-risk scam) is left as it is                                                                                           | A design decision about a shared component, not an accessibility fault: the words say "Low risk" and the title says scam                            |
| 6   | Strings were not rewritten                                                                                                                         | They are consistent and complete; whether they are good is for native speakers (D-154, D-157, D-159)                                                |

## Manual test

1. `pnpm exec vitest run src/pages/scam/scamPages.a11y.test.tsx src/components/scam/scamParts.a11y.test.tsx`: the `axe` runs.
2. With the keyboard only, on the check screen: Tab reaches "Your checks", the two modes, the box, "Check this message". Submit a message: focus lands on "Checking the message…", then on the verdict's heading. Press Tab: the next stop is the first control after it, not the header.
3. Open "Warn other workers": Tab stays in the sheet, in the order of the screen; Escape closes it and focus returns to the button. Send: focus lands on "Thank you…".
4. History with more than 20 checks: "Show more" puts focus on the first new row.
5. Switch the app to dark and look at the message box, an error, and the chosen mode: all visible without relying on colour.
6. To repeat the real-browser run: open a screen in `pnpm dev`, paste `frontend/node_modules/axe-core/axe.min.js` into the console, then `await axe.run(document)`. Texts on gradients come back as "needs review": compute those by hand.
7. With a screen reader: D-161.

## Checks run (2026-10-07)

| Check                                                              | Result                                                                                                                                                               |
| ------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm lint`, `tsc -b`, `pnpm build`, `node scripts/check-i18n.mjs` | clean (959 keys, 6 languages)                                                                                                                                        |
| `prettier --check`                                                 | New files pass; existing files that were edited pass with `--end-of-line crlf` (this Windows checkout has CRLF)                                                      |
| `pnpm test`, all of `src`                                          | **74 files, 794 tests: 792 passed, 2 failed.** Same two as before: the screenshot-upload tests in `ScamCheckHome.msw.test.tsx`. 177 more tests than before this task |

## Not done, and why

- **No real screen reader and no real phone** (D-161, D-156, D-158). Whether a notice that is both an alert and focused is read once or twice is a guess until someone listens.
- **Colour contrast and tap-target size are not in CI.** jsdom has no layout. The token test covers the pairs; the screens themselves were measured by hand (D-163).
- **Tagalog, Indonesian and Nepali were not looked at in the browser**, only in jsdom. Contrast does not depend on the language; line breaks and long words do. Hindi and Bengali, the two with the tallest letters, were looked at and nothing overflowed.
- **The real pages were drawn from data put in the query cache**, not from a running backend. A live check in the browser is the E2E's job (NF-SA-020).
- **Native-speaker read of the strings** (D-154, D-157, D-159) stays open.

## Noticed, not fixed

- No page has its own title (D-162), in any module.
- A result has seven named regions, so a screen reader's landmark list is longer than ideal. It is not a violation and nothing was changed.
- The dropzone's dashed border is about 2:1 against its card. It has a text label and an icon, which identify it, so it is not a fault; a stronger border would be a design change.
- The two screenshot-upload tests still fail in this environment (see the NF-SA-017 runbook).

## Definition of Done (frontend feature)

- [x] Missing-key check green (959 keys, 6 languages)
- [x] `axe` reports 0 serious or critical issues on the scam screens, in a real browser (both themes) and in CI (six languages)
- [x] Contrast, focus order and labels fixed where they were wrong (the table above)
- [x] Mobile, checked at 360 px; keyboard navigable; colour is never the only signal
- [x] Tests, lint, types, build
- [ ] A real screen reader and a real phone (D-161, D-156, D-158)
- [ ] A native-speaker read of the strings (D-154, D-157, D-159)
