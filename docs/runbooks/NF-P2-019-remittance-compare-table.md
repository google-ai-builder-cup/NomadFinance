# NF-P2-019 — Remittance: Comparison Table

## Summary

Every surveyed service of a `/remittance/compare` result, in one sortable table under NF-P2-018's summary card.

- **Sortable columns:** Service, Speed, Fee, Total cost, Your family receives. Each column has its own "best first" direction the first click (cheapest fee, fastest speed, most received, alphabetical for the service name); a second click on the same column flips it. Default sort is by amount received, the same order `/compare` already ranks by.
- **Speed sorts by `speed_order`**, never the text ("Same day", "Next day", …), as the Remittance X-Ray pipeline requires.
- **Best-service highlight.** The rank-1 row has a green tint and a "Best" badge, whichever column the table is sorted by.
- **Savings highlight.** Every other comparable row shows "{{amount}} less than the best" under its received amount (`less_than_best` from the comparison), so the cost of not picking the best service is visible at a glance.
- **Per-row estimate note.** A row whose price was interpolated outside the two surveyed amounts (`estimated`) says so under its fee.
- **Not-comparable services** (paid out in another currency) are listed separately, below the table, with a note explaining why they have no rank.
- **Mobile:** the table scrolls horizontally inside its own card (`overflow-x-auto`, `min-w-[640px]`) rather than squeezing five columns into a phone width; the non-comparable list reflows normally.
- **Accessible:** each sortable header is a real `<button>` with `aria-sort` on its `<th>`, a `<caption>` for screen readers, and a per-row `sr-only` "Ranked N of M" line independent of the current sort.
- All texts in the 6 languages. No backend change, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `frontend/src/utils/remittanceTable.ts` (new) | `sortProviders()`, `nextSortState()` — the sort logic, kept pure and separate from the component |
| `frontend/src/utils/remittanceTable.test.ts` (new) | 8 tests: default order, non-comparable always last, each column's ordering, speed by `speed_order` not text, tie-breaking, direction toggling |
| `frontend/src/components/remittance/ComparisonTable.tsx` (was a stub) | The table |
| `frontend/src/pages/remittance/RemittanceCompare.tsx` | Renders `ComparisonTable` under `ComparisonSummaryCard`; removed the NF-P2-019 TODO |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `remittance.table.*` (12 keys × 6 languages, key parity checked by script) |

`FlaggedProviderBadge.tsx` (NF-P3-022), `SavingsCallout.tsx` (NF-P2-022 UI, unassigned) and `TrendChart.tsx` (NF-P2-020) are still empty stubs, untouched.

## Decisions

1. **Sort logic lives in a pure utility, not the component**, and only that utility is unit-tested. No React component in this codebase has its own test file (`@testing-library/react` is not a dependency); adding it for one component would be a new testing pattern for a hackathon-scale project. Sorting is the one piece of real logic here, so it is the one thing extracted and tested, the same split `corridors.ts`/`corridors.test.ts` already uses.
2. **Non-comparable services always sort last**, whatever column or direction is chosen — `sortProviders` filters them out before sorting the rest, then appends them back in the order `/compare` already gave them. Matches the API's own guarantee.
3. **A tied value keeps a fixed order (by `rpw_id`) regardless of sort direction.** The first implementation let the tie-break flip with `desc`, so clicking a column back and forth reshuffled rows that were never actually reordered; fixed and covered by a test (`breaks a tie by the original rpw_id order, whichever direction is asked for`).
4. **Each column's first click sorts "best first", not always ascending.** Fee/total cost/speed ascending (lower is better), amount received descending (higher is better), service name ascending (A–Z). A second click on the same column flips it.
5. **No shadcn `Table` component and no new dependency.** The repo's `components/ui/` only has `Button` and `Skeleton`; a plain semantic `<table>` with Tailwind matches the project's "shadcn/ui copied in, not a package" convention without adding anything to `package.json` (a shared file).
6. **No dedicated loading skeleton for the table.** It renders only once `compare.data` exists, the same condition the sibling summary card already uses (`RemittanceCompare.tsx`); no remittance-specific processing animation exists as its own task (NF-P2-010 is Contract Shield's), so a new skeleton pattern was not invented for this one component.
7. **Mobile: horizontal scroll, not a card-per-provider layout.** Five columns of numbers do not compress well into a phone width without losing at-a-glance comparability; `overflow-x-auto` on the table's own wrapper keeps the numbers aligned and is a standard, low-effort responsive pattern for data tables. Verified at 375×812 (see "Verified results").
8. **The Gemini recommendation card is out of scope.** The original design mentions it and NF-P2-016's runbook flagged that no task ID owns building it in the UI; the task description here (`.claude/tasks.md`) only asks for "sortable columns, savings highlight, recipient-receives display". Left as a "Noticed, not fixed" item, not silently absorbed into this task.

## Flow

```
RemittanceCompare.tsx
  compare.data (RemittanceComparison) and !compare.isPending
    → ComparisonSummaryCard (NF-P2-018, unchanged)
    → ComparisonTable
         sortProviders(comparison.providers, sort)     comparable, ranked first; non-comparable last
         click a column header → nextSortState(current, column) → re-sort, no re-fetch
         rank-1 row: green tint + "Best" badge, whatever the sort
         other rows: "{{amount}} less than the best" under the received amount
         provider.estimated → "Estimated" tag under the fee
         non-comparable providers → separate card, one line each: firm, fee, payout currency
```

## All commands, in order

### 1. Checks (from `frontend/`; `pnpm.cmd` in PowerShell if `pnpm` is blocked)

```bash
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

### 2. Manual browser check

`/remittance` sits behind Firebase Auth and a completed profile (`ProtectedRoute` → `RequireOnboarding`), so trying the real page needs the Auth and Firestore emulators, a signed-in test user, and `corridors/` loaded — the full setup in NF-P2-018's runbook, section "2. Try it on the emulators".

For this task specifically, verification was done with a temporary, unauthenticated dev-only route (`/_dev/table-preview`, `router.tsx` edited locally) rendering `ComparisonTable` directly against a hand-built `RemittanceComparison` (3 comparable providers with visibly different fee/speed/received amounts, plus 1 non-comparable one), then **fully reverted** before committing (`git status` showed `router.tsx` unchanged and the temp file removed). This is enough to see and interact with the component itself; it does not exercise `/remittance/compare` end to end — that path was already verified live in NF-P2-018's runbook.

To repeat it: temporarily add a route rendering `<ComparisonTable comparison={...} />` with fixture data, open it in the browser, then delete the route and file before finishing.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `tsc -b`, `pnpm lint` (max warnings 0), `prettier --check` | Pass |
| `vitest run src` | 108 passed (8 files; 8 new) |
| `pnpm build` | Pass (pre-existing chunk-size warning, unrelated) |
| i18n key parity | Scripted check: all 12 new keys present, identical, across all 6 locale files |

**Live, in the browser, via the temporary preview route (see above):**
- **Desktop.** Clicking "Fee" sorted ascending (InstaReM 3.30 → Wise 5.50 → Maybank 12) then, on a second click, descending (Maybank → Wise → InstaReM); the best-service row (InstaReM) stayed highlighted green with its badge in both orders. "Your family receives" showed the default sort with the ▼ marker.
- **Non-comparable section.** "USD Direct Express: fee SGD 8, pays out in USD" rendered under "Paid in another currency", outside the sortable table.
- **Mobile (375×812).** Table scrolled horizontally inside its card; the non-comparable note reflowed to full width with no overflow; best badge and sort arrows stayed visible.
- No console errors on either viewport.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Table never appears | `compare.data` is only set after a successful `/compare` call; check the summary card above it shows first |
| Sort direction looks backwards on first click | Each column's first click is its own "best first" direction (decision 4), not always ascending — check `DEFAULT_DIRECTION` in `remittanceTable.ts` for that column |
| A "less than the best" note is missing on a row that isn't best | `less_than_best` is `0` for the best row and non-`null` for the rest; a `0` on a non-best row (a tie) correctly shows nothing, since `!!provider.less_than_best` treats `0` as falsy |
| Table looks squeezed on phone | Check `overflow-x-auto` wasn't removed from the table's wrapper `div`; the table itself has `min-w-[640px]` on purpose |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Button`, existing tokens; no new `components/ui/` needed)
- [x] Fully mobile responsive (375×812, horizontal scroll, verified live)
- [ ] Works on slow network (throttled 3G): not separately tested — the table renders from data `/compare` already fetched, no new network call of its own
- [x] Loading states: matches the sibling summary card's existing convention (renders only once data exists, decision 6)
- [x] Error states: N/A — no new failure path; the data is already-validated `RemittanceComparison`
- [x] i18n keys for all user-facing strings (6 languages), key parity checked
- [ ] Screenshots added to PR: take them when opening the PR
- [x] Accessibility: `aria-sort`, `scope="col"`, `<caption>`, `sr-only` rank text, keyboard-operable sort buttons (real `<button>` elements)

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Whoever ends up owning the Gemini recommendation card:** no task ID currently covers it (see decision 8); it would sit between the summary card and this table, or below it.
- **Pranjal (NF-P2-020, trend chart):** unaffected by this table; the page's layout after this task is header → form → summary card → comparison table.
- **Whoever wires up `SavingsCallout.tsx` (NF-P2-022's UI, unassigned):** `GET /remittance/savings` is now built; nothing in this table depends on it.
- **NF-P3-022 (radar flags):** `FlaggedProviderBadge.tsx` is still an empty stub; this table has no radar-flag column or badge yet.

## Commit and PR for this task

Branch: `feature/remittance-compare-table` (already checked out when this task was built).

```bash
git commit -m "feat(remittance): add sortable provider comparison table" -m "Refs: NF-P2-019"
```

PR title: `feat(remittance): sortable comparison table with best/savings highlight (NF-P2-019)`

## Not covered here

- The Gemini recommendation card (see decision 8)
- The trend chart and best day (NF-P2-020), radar "flagged provider" badges (NF-P3-022), the savings callout UI (NF-P2-022's UI half, unassigned)
- Slow-3G throttled testing
