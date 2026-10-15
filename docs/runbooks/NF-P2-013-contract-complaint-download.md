# NF-P2-013 — Contract Shield: Complaint Letter Download

## Summary

When a report's `complaint` is not null (NF-P2-006 wrote a letter because a clause broke the law), the report card now shows it: a preview, a reminder to fill in the bracketed blanks, and two actions — download as PDF and copy to clipboard.

- **`ComplaintPreview`** (was a stub): renders after the clause list in `ReportCard.tsx`, only when `report.complaint !== null`. Naturally absent when there is no violation, and while `complaint_pending` is true (the letter failed for a passing reason and hasn't been written yet — `ReportCard`'s existing pending note still covers that case).
- **Preview vs. what gets sent.** The preview shows `worker_copy` (or `letter_text` when that's null, i.e. the letter is already in the worker's language) — the pipeline owner's own handoff note was explicit about this split. Download and Copy always act on `letter_text`, the version actually addressed to the authority, whichever language that reads in. When the two differ, a small note under the preview says so and names the letter's language (`languageName()`, a new `Intl.DisplayNames` helper mirroring `countryName()`).
- **No PDF library, no backend change.** "Download as PDF" opens a blank window, writes the letter as plain text with a light print stylesheet, and calls `window.print()` — the worker picks "Save as PDF" in the browser's own dialog. Chosen over adding a client-side PDF dependency (bundle size, D-45) or a new backend endpoint (out of scope for a 3h frontend task); confirmed with you before building it.
- **Copy to clipboard** uses `navigator.clipboard.writeText`, with a toast on success or failure (asks the worker to copy it by hand if the browser refuses).
- **Where to send it:** every `channels` entry (web/email/phone/post, with an icon and its `note` if any) plus `authority_url`, each linked (`mailto:`, `tel:`, or the URL itself) except `post`, which has no link.
- The two DOM-touching actions live in `utils/complaintActions.ts`, not the component, so they can be unit-tested without a browser (this project has no jsdom/happy-dom — every other test here is pure-logic, in the default Node environment).
- All texts in the 6 languages (`contract.complaint.*`).

## Files

| File | Change |
|---|---|
| `frontend/src/types/contract.ts` | `LetterLanguage` (`en`/`ko`/`ms`/`ja`), tightened from `ContractComplaint.letter_language: string` (typed loosely in NF-P2-011, before anything read it) |
| `frontend/src/utils/format.ts` | `languageName()`: language display name in a UI language, mirrors `countryName()` |
| `frontend/src/utils/complaintActions.ts` (new) | `openPrintableLetter()`, `copyLetterToClipboard()` — the two browser actions, kept out of the component so they're testable |
| `frontend/src/utils/complaintActions.test.ts` (new) | 5 tests: popup blocked, letter written and printed, window closes after printing, clipboard resolves, clipboard rejects — each with a hand-built fake `window`/`navigator` (`vi.stubGlobal`), no DOM environment needed |
| `frontend/src/components/contract/ComplaintPreview.tsx` (was a stub) | The preview, the blanks reminder, the two action buttons, the channels list |
| `frontend/src/components/contract/ReportCard.tsx` | Renders `<ComplaintPreview>` after the clause list when `report.complaint` is present |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `contract.complaint.*`: heading, subtitle, blanks reminder, send-note, download, copy, copied, copy-failed, pop-up-blocked, where-to-send |

## Decisions

1. **Print-to-PDF, not a PDF library or a backend endpoint.** You chose this after I flagged that nothing in the repo generates a PDF for this letter (NF-P3-014's `weasyprint` is server-side, for a different pillar, and Contract Shield's `/contracts/complaint` endpoint only ever returns text). Zero new dependencies, no shared-file diff, no new backend work blocking this task on someone else.
2. **The printable window is a genuinely separate document**, built with `document.createElement`/`textContent` (never `innerHTML`, since the letter is plain text, not markup to trust) — not a hidden `print:` region of the app's own page. That would have meant marking the whole `AppShell` (header, sidebar, bottom nav, the rest of the report) `print:hidden`, a much bigger, shared-layout change for a self-contained feature.
3. **Download and Copy both operate on `letter_text`, never `worker_copy`,** even though the on-screen preview may show `worker_copy`. Sending the read-for-yourself translation to a labor authority that doesn't work in that language would defeat the letter's purpose; the UI says so explicitly whenever the two differ.
4. **`openPrintableLetter`/`copyLetterToClipboard` are plain functions in `utils/`, not inlined in the component,** specifically so they could be unit-tested against a hand-built fake `window`/`navigator` via `vi.stubGlobal` — this project has no jsdom or happy-dom dependency (every existing frontend test is pure-logic), and adding one just for two functions would be a shared-file, test-infra change out of scope here.
5. **No in-app form for the `[bracketed]` blanks.** tasks.md's description (preview, PDF, copy) doesn't ask for one, and the letter's placeholders (name, contact, start date) are the same ones NF-P2-006 already documented as filled in by the worker before sending.

## Manual test steps

No backend or Gemini needed: `report.complaint` is a plain field on the report document this task only reads.

**PowerShell / bash** (same commands, from `frontend/`)

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check --end-of-line auto src
pnpm exec vitest run src
pnpm build
```

**In the browser**, the fastest way to see it is against a seeded report (same emulator setup as the NF-P2-010/011 runbooks): write a `users/{uid}/contracts/{id}/reports/{language}` document whose `complaint` is not null (see `docs/data-model/collections/contracts.md` for the shape — `template_type`, `authority_name`, `authority_url`, `channels`, `letter_language`, `letter_text`, `worker_copy`, `violation_count`), then open that contract's report.

1. The complaint section appears under the clause list, with the preview text, the blanks reminder, and the two buttons.
2. When `worker_copy` is set, the small "this preview is for you to read…" note appears under it, naming the letter's real language; when `worker_copy` is `null`, the note does not appear.
3. Click **Copy letter**: a "Letter copied to clipboard." toast appears, and pasting elsewhere gives `letter_text` (not `worker_copy`, if they differ).
4. Click **Download as PDF**: a new window opens with the letter as plain text and the browser's print dialog appears; choose "Save as PDF". If your browser blocks the pop-up, a toast asks you to allow it and try again.
5. Check the channels list: a `web` or `email` or `phone` entry is a working link (`mailto:`/`tel:`/the URL); `post` is plain text; `authority_url` (if present) is a separate linked line.
6. DevTools → phone width (375 px): no sideways scroll, buttons wrap onto their own line if needed.
7. Keyboard only: Tab reaches both buttons and every link; Enter/Space activates them.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `tsc -b` | Pass |
| `pnpm lint` (max warnings 0) | Pass |
| `prettier --check --end-of-line auto` | Pass |
| `vitest run src` | 56 passed (5 files; 5 new in `complaintActions.test.ts`) |
| `pnpm build` | Pass (PWA precache 33 entries) |

**Live, in the browser** — a temporary route rendered `<ComplaintPreview>` directly with two fixtures (a translated case, `worker_copy` in Hindi with the letter in English; a same-language case, `worker_copy: null`), then the route and its fixture file were removed before committing:
- Both cases rendered the heading, subtitle (with `count`/`authority` interpolated), blanks reminder, letter text, buttons and channels list correctly (via `get_page_text`); the "this preview is for you to read…" note appeared only for the translated case.
- **Copy letter:** clicking it triggered the failure path — "We couldn't copy the letter. Please copy it by hand." — because this browser pane's sandbox denies clipboard-write permission to automated clicks; no console error was logged, confirming the `catch` branch (not a bug) fired as designed. The success path is covered by the unit test (mocked `navigator.clipboard.writeText` resolving).
- **Download as PDF:** clicking it triggered "Please allow pop-ups for this site, then try downloading again." — this pane's automation also blocks `window.open`. This is the exact fallback path the feature is meant to have for a real blocked popup, so seeing it fire correctly (and not silently do nothing) confirms that branch; the window-writing itself (title, stylesheet, body text, `focus`, `print`, `onafterprint` → `close`) is covered by the unit tests instead.

**Not run:** a real "Save as PDF" pass in a normal (non-sandboxed) browser window, and a real clipboard paste — both blocked by this session's browser-pane sandbox rather than anything in the code. Worth 30 seconds in a normal Chrome tab before the PR screenshots.

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Button`, lucide icons)
- [x] Fully mobile responsive (buttons wrap, no fixed widths)
- [ ] Works on slow network: not applicable — no network call (Firestore already delivered `report.complaint`; both actions are local browser APIs)
- [x] Loading states: not applicable, nothing async is awaited before paint (the copy action's own pending state is short enough that no spinner was added, matching the rest of this pillar's buttons)
- [x] Error states: clipboard refusal (toast, "copy by hand") and a blocked pop-up (toast, "allow pop-ups")
- [x] i18n keys for all user-facing strings (6 languages)
- [ ] Screenshots added to PR: take them when opening the PR, ideally from a normal (non-sandboxed) browser given the note above
- [x] Accessibility: `<section aria-labelledby>`, native `<button>`s with icon + text (not icon-only), every link has visible text (the URL or the channel value), keyboard-reachable

## For teammates

- **Anyone building the FIB PDF export (NF-P3-014):** that one is a real backend-generated PDF (`weasyprint`), a different pattern from this task's browser print — don't assume this task's approach generalizes there.
- **Anyone touching `ReportCard.tsx` again:** `ComplaintPreview` is the last section, guarded by `report.complaint &&` — keep it after the clause list so the clause-by-clause read comes first.

## Not covered here

- Editing the letter's bracketed blanks in-app.
- A backend-generated, branded PDF (would need a new endpoint; flagged above for whoever picks that up later, no follow-up entry added since nothing here is broken, just a possible future upgrade).
