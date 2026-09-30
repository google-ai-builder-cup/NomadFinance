# NF-P2-023 — Contract Shield: Report Card Interactions & Polish (+ three noticed-but-not-fixed items)

## Summary

NF-P2-023's own scope: clause expand/collapse, a risk-score tooltip, sticky side-by-side columns and mobile tuning on the Contract Health Report (pairs with NF-P2-011). Language toggle wiring, the fourth item in the task description, was already delivered separately in NF-P2-012.

At your explicit request, this PR also covers three items flagged as "noticed, not fixed" across earlier sessions:

- `SavingsCallout.tsx` — the "you would have saved $X" hero moment (backend built by NF-P2-022; no frontend task in the tracker owned its display).
- A working dark-mode toggle anywhere in the app (`tokens.css` had full dark values; nothing ever applied the `.dark` class).
- `FlaggedProviderBadge.tsx` — **not done**. Checked first: the frontend has no employer/agency name anywhere in its contract types (a backend schema gap), and `radar_entities` is always empty (NF-P3-003 doesn't exist yet). You confirmed skipping it rather than building a permanently-invisible component or reaching into two other unbuilt tasks.

No backend change. No new dependency.

## Files

| File | Change |
|---|---|
| `frontend/src/components/contract/ClauseRow.tsx` | Expand/collapse per clause; `danger`/`caution` open by default, `safe` closed |
| `frontend/src/components/contract/ReportCard.tsx` | Owns the expand/collapse state, "Expand all"/"Collapse all", the score tooltip, the sticky column header |
| `frontend/src/components/ui/tooltip.tsx` (new) | `InfoTooltip`: a self-built, click-to-toggle disclosure (not the Radix Tooltip primitive — not a dependency here) |
| `frontend/src/components/remittance/SavingsCallout.tsx` (was a stub) | The hero card, using `GET /remittance/savings` (already built) |
| `frontend/src/types/remittance.ts`, `services/remittanceService.ts`, `hooks/useRemittance.ts` | `RemittanceSavings` types, `getRemittanceSavings()`, `useRemittanceSavings()` |
| `frontend/src/pages/remittance/RemittanceCompare.tsx` | Renders `<SavingsCallout>` right under the result summary |
| `frontend/src/lib/theme.ts` (new) | `Theme`, storage helpers, `resolveTheme()`, `applyTheme()` |
| `frontend/src/components/common/ThemeSync.tsx` (new) | Mounted in `main.tsx`; keeps "system" live while the app is open |
| `frontend/src/components/layout/ThemeToggle.tsx` (new) | Light/Dark/System selector, mirrors `LanguageSelector.tsx`'s pattern |
| `frontend/index.html` | A small inline script applying `.dark` before first paint (no flash of the wrong theme) |
| `frontend/src/components/layout/Header.tsx` | Renders `<ThemeToggle>` next to the language selector |
| `frontend/src/components/layout/LanguageSelector.tsx` | **Not part of the original plan** — fixed alongside `ThemeToggle`, see decision 6 |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | New keys for all of the above |

## Decisions

1. **A safe clause starts collapsed, `danger`/`caution` start open.** A fair contract's boilerplate is rarely what a worker needs to read first; every row is still independently toggleable, and "Expand all"/"Collapse all" override every row at once.
2. **The score tooltip's copy is the exact band arithmetic from `risk_scorer.py`** (0–49 with any danger term, 50–79 with only caution, 100 otherwise) — not a vague restatement. Checked against the backend source directly, not from memory.
3. **A hand-built tooltip, not a new dependency.** shadcn's own Tooltip primitive needs `@radix-ui/react-tooltip`, not installed here. `components/ui/tooltip.tsx` is self-built (the same spirit as this repo's existing `skeleton.tsx`), and click-to-toggle rather than hover-only, so it works the same on a touch phone as on desktop.
4. **The sticky column header uses `top-14`**, matching the app header's own `h-14` sticky height exactly, so the two never overlap.
5. **`SavingsCallout` returns `null`, not an error, when `total_savings <= 0`** or there's no comparable history: a corridor's comparison table already stands on its own, and a "you would have saved $0" card would read as a bug, not a feature.
6. **`LanguageSelector.tsx` needed the same fix as `ThemeToggle.tsx`, and wasn't in the original plan.** Live-checking the new toggle at 375px surfaced that `LanguageSelector` was never width-constrained — sized to its longest option ("Bahasa Indonesia"), 159px wide — and had simply never been tested at a width where the header had one fewer control to spare. Since a fourth header control finally pushed it over the edge, and "a working dark-mode toggle" that visibly breaks the header on every phone isn't done, both selectors now go icon-only below `sm` (`w-9`, `text-transparent`, full text restored at `sm:` and up) — the native picker still lists every option's real label when opened; only the closed control's own visible text is hidden.
7. **Theme storage is `localStorage`, not `sessionStorage`.** Unlike the header's language quick switch (deliberately per-tab, so a shared phone doesn't greet the next person in the wrong language), a light/dark preference isn't personal or sensitive, and a worker reasonably expects it to stick.
8. **FOUC prevented with a small inline script in `index.html`, not solved in React.** A client-rendered SPA has no other way to avoid a flash of the wrong theme before the JS bundle loads and mounts `ThemeSync`. The script and `lib/theme.ts`'s `THEME_KEY` must stay in sync — commented in both places.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `pnpm lint` (`--max-warnings 0`) | Pass |
| `pnpm format:check` | Pass |
| `pnpm build` | Pass |
| `pnpm test:rules` | 100 passed |
| `pnpm audit --prod --audit-level high` | Exit 0; the 2 moderate advisories are pre-existing `react-router`, unrelated |
| `vitest run src` (D-46, not in CI) | 111 passed (unchanged: this task's new logic is component-level, matching the repo's existing pattern of not unit-testing storage-helper wrappers like `lib/languages.ts`, which also has no test file) |
| **Live browser: dark mode** | Real emulator + a signed-in worker. Light → Dark → System all switch correctly; the choice survives a full page reload (confirmed via `document.documentElement.className` immediately after navigation, before any interaction) |
| **Live browser: mobile header, 375px** | Found and fixed a real overflow (decision 6). Confirmed after the fix: `document.body.scrollWidth === document.body.clientWidth` (no horizontal overflow at all), both selectors still fully accessible (`aria-label`, every real option present) |
| **Live browser: SavingsCallout** | Real backend, real 12-month ECB history. SG-PH 645 SGD: "Over the last 12 months / ₱36,307.86 / You would have saved this much by always using InstaReM instead of Maybank," placed correctly under the result summary |
| **Live browser: ReportCard interactions** | See "How this was verified" below — real compiled component, real data shapes, no Gemini spend |
| Two screenshot artifacts investigated, both ruled out | (a) Dashboard pillar cards looked light-gray mid-transition right after a `<select>` change — `getComputedStyle` and a clean re-screenshot both confirmed the real dark colors. (b) The tooltip popover looked white in a screenshot taken right after toggling `.dark` while already open — `getComputedStyle` confirmed the correct dark background and text throughout, and the same `bg-popover` class is already proven correct in `TrendChart.tsx`'s tooltip (verified live in NF-P2-020). Both logged here so they don't get re-investigated as bugs later. |

### How the ReportCard interactions were verified

There is no route to reopen an existing contract (`ContractList.tsx`/`ContractReport.tsx` are still empty stubs — no task owns them yet), and this browser toolkit has no file-upload capability to drive the real dropzone, so a live pipeline run wasn't possible without an unrelated Gemini spend. Instead, the real, Vite-compiled `ReportCard` component was mounted directly into the running page (`react-dom/client`'s `createRoot`, imported from the same resolved module the app itself uses) with realistic, hand-built `analysis`/`report` props spanning all three risk levels. This exercises the true component tree, real Tailwind CSS, real i18n and real click handlers — everything except the surrounding upload flow. Confirmed via a mix of screenshots and direct DOM assertions (`aria-expanded`, tooltip content): default open/closed state per risk level, "Expand all"/"Collapse all", independent per-row toggling after a bulk action, the sticky column header staying pinned while scrolling, and the tooltip's exact text. The scratch mount was removed afterward; nothing was left in the page.

One thing this method could not exercise: the automation tool's simulated mouse clicks didn't register reliably against a component mounted outside the normal app root (a direct DOM `.click()` did, and produced the correct result every time) — noted so it isn't mistaken for a real interaction bug if re-tested the same way.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A header control looks fine on desktop but the header overflows on a phone | Check whether the new control's `<select>`/content has an explicit width; native `<select>` elements size to their longest option by default (decision 6) |
| The tooltip or a stat card looks like the wrong theme in a screenshot right after switching | Check `getComputedStyle`, not the screenshot, if the switch happened moments before the capture — see the two false alarms logged above |
| `SavingsCallout` never appears for a corridor | Check `GET /remittance/savings` directly: 404 means no rate history backfilled yet (same cause as `TrendChart`, NF-P2-020); a real `total_savings <= 0` renders nothing, on purpose |
| Dark mode flashes light for an instant on reload | The inline script in `index.html` and `THEME_KEY` in `lib/theme.ts` have drifted apart; they must use the exact same localStorage key |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind, matching existing conventions; no new dependency
- [x] Mobile responsive: verified at 375×812 in a live browser; a real regression was found and fixed
- [ ] Slow network: not tested throttled
- [x] Loading states: `SavingsCallout`'s own skeleton, matching `TrendChart`'s pattern
- [x] Error states: `SavingsCallout`'s 404/error/retry, matching `TrendChart`'s pattern
- [x] i18n keys for all user-facing strings, all six languages
- [x] Screenshots: captured during live verification (see above); available on request
- [x] Accessibility: `aria-expanded`/`aria-controls` on every clause toggle, `aria-describedby` on the tooltip trigger, both header selects keep real `aria-label`s and full option lists even when visually icon-only

## Commit and PR

Branch: `feature/contract-report-polish` (already checked out; up to date with `main`).

```
feat(contracts): add report card interactions, savings callout and dark mode
Refs: NF-P2-023
```

PR title: `feat: report card polish, savings hero moment and a working dark mode (NF-P2-023)`

## Not covered here

- `FlaggedProviderBadge.tsx` — genuinely blocked on a backend schema change (employer/agency name isn't in `ContractAnalysis`/`ContractReport` today) and NF-P3-003 (empty `radar_entities`). You confirmed skipping it.
- A live, full-pipeline click-through of the report card (see "How this was verified").
- Slow-network testing.
