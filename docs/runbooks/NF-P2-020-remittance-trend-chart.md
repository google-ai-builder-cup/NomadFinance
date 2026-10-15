# NF-P2-020 — Remittance X-Ray: Trend Chart

## Summary

A historical mid-market-rate chart and a "best day to send" indicator on the comparison result (`RemittanceCompare.tsx`), from `GET /remittance/trends` (NF-P2-015, built). A worker picks a period (1M/3M/6M/1Y), sees the line move, and reads either a real best-day tip ("Wednesday tends to be the best day to send: about +0.3% better...") or, honestly, that there isn't one for this corridor — the backend's own endpoint doc requires that second case be said plainly, not invented.

New dependency: `recharts@2.15.4`, code-split so it only loads once a comparison exists to chart.

## Files

| File | Change |
|---|---|
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | `recharts` `2.15.4`, pinned exact (see decision 1) |
| `frontend/src/types/remittance.ts` | `RemittanceTrends`, `TrendSummary`, `WeekdayStat`, `Weekday`, `TrendDays`/`TREND_DAYS` (mirrors the backend schema) |
| `frontend/src/services/remittanceService.ts` | `getRemittanceTrends()`: `GET /remittance/trends?corridor_id=&days=` |
| `frontend/src/hooks/useRemittance.ts` | `useRemittanceTrends()`: a query, cached per corridor + period; a 404 is not retried |
| `frontend/src/components/remittance/TrendChart.tsx` (was a stub) | The chart, period picker, change summary, best-day box, loading/empty/error states, a screen-reader table alternative |
| `frontend/src/pages/remittance/RemittanceCompare.tsx` | Renders `<TrendChart>` under the table, lazy-loaded (`React.lazy` + `Suspense`) |
| `frontend/src/utils/format.ts` | `weekdayName()`: a weekday's localized name from the browser's own locale data, no new translation keys for the five weekdays |
| `frontend/src/utils/format.test.ts` (new) | 3 tests |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `remittance.trend.*` |
| `docs/runbooks/NF-P2-020-remittance-trend-chart.md` | This file |

No backend change: NF-P2-015 already built everything this task reads.

## Decisions

1. **`recharts@2.15.4`, not the newer `3.10.1`, and pinned exact.** Checked real npm metadata before choosing: v3 pulls in `@reduxjs/toolkit`, `react-redux` and `immer` as real dependencies — a lot of weight for one line chart, on top of the bundle-size issue this repo already has open (D-45). v2.15.4 has a much lighter tree (`clsx`, `lodash`, `react-is`, `react-smooth`, `victory-vendor`) and is fully compatible with the app's React 18.3.1 (confirmed every other React-peering package in `package.json` also already accepts React 19, so this wasn't a blocker either way — it was purely a bundle-weight call). v2's branch is in maintenance mode (`npm` shows a deprecation notice pointing at v3); acceptable for a simple, stable line chart, revisit if recharts v2 stops getting security patches.
2. **Code-split, not bundled into the main chunk.** `TrendChart` is `React.lazy`-loaded from `RemittanceCompare.tsx`, only once a comparison result exists. The build confirms it: a separate `TrendChart-*.js` chunk (109 KB gzipped) apart from the main bundle, in the spirit of D-45.
3. **One series, so no legend; a badge, not a second series, for the best day.** Per the `dataviz` skill: a single line needs no legend, the section title names it. The best-day indicator is `WeekdayStat` data (a per-weekday comparison, not a time series) shown as a compact callout — putting it on the same chart would force a second axis or confuse a magnitude scale with a categorical one, both listed as anti-patterns.
4. **Reused the app's own `--primary` token for the line**, not a new palette. It already has real, distinct light and dark HSL values (`tokens.css`), so the categorical/CVD validator in the `dataviz` skill doesn't apply here — that machinery is for assigning several categorical hues, and this chart has exactly one series.
5. **The best-day badge reuses the `emerald-500` treatment** `ComparisonTable.tsx` already uses for "this is the good one" (the best-ranked provider row), rather than inventing a new "positive" color — this repo's tokens have no semantic status colors, and Tailwind's `emerald`/`amber`/`destructive` trio is the established convention (`ComparisonSummaryCard`'s stale-rate note uses the same `amber-500/10` pattern).
6. **`timing_tip`-equivalent honesty: the "no best day" message is never skipped.** The trends endpoint doc requires the app to say "no reliable best day" rather than invent one; `best_day_reason` (`not_enough_history` / `no_clear_pattern`) always renders a plain-language explanation when `best_day` is null.
7. **Weekday names come from `Intl.DateTimeFormat`, not new i18n keys**, the same pattern `countryName`/`currencyName`/`languageName` already use — one anchor date (a known Monday with no DST edge nearby) plus an offset, so the five weekday names need no translation and stay correct for any locale the browser supports.
8. **A 404 (no history yet) is a quiet, specific message, not a retried error.** `useRemittanceTrends` never retries a 404; the component shows `remittance.trend.notLoaded` instead of the generic load-error/retry pair.
9. **A sr-only table alternative ships with the chart**, matching the `dataviz` skill's accessibility pass ("a table view exists") and this repo's own pattern in `ReportCard`.
10. **Found, not fixed: dark mode has no working toggle anywhere in the app.** `tailwind.config.ts` declares `darkMode: ["class"]` and `tokens.css` has full dark values, but nothing in the codebase ever adds a `.dark` class to `<html>` — searched for it, found nothing. Verified this chart's dark styling is correct by adding the class manually in a live browser session (screenshot in "Verified results"); the toggle itself is a pre-existing gap across the whole app, out of scope here, and not filed as a separate item only because it wasn't discovered by a task that owns theming.

## Flow

```
RemittanceCompare.tsx, once a comparison exists
  <Suspense> loads TrendChart's own chunk (recharts stays out of the main bundle)
    useRemittanceTrends(corridor_id, days)         [hooks/useRemittance.ts]
      GET /api/v1/remittance/trends?corridor_id=&days=     [services/remittanceService.ts]
        200 → points, summary, best_day, best_day_reason
        404 → shown as "not available yet", not retried
    empty points  → "no history yet for this period"
    points        → LineChart (--primary), hover tooltip, change-since-first line
    best_day      → emerald callout: "{weekday} tends to be the best day..."
    no best_day   → plain-language reason (never invented)
  period picker (1M/3M/6M/1Y) switches the query's cache key; a period already seen is instant
```

## All commands, in order

From `frontend/` with `pnpm install` already run.

### 1. The checks CI runs (`frontend-ci.yml`, `security-scan.yml`)

```bash
pnpm lint
pnpm format:check
```

```bash
VITE_FIREBASE_API_KEY=ci-placeholder VITE_FIREBASE_AUTH_DOMAIN=nomadfinance-prod.web.app \
VITE_FIREBASE_PROJECT_ID=nomadfinance-prod VITE_FIREBASE_APP_ID=ci-placeholder pnpm build
```

```bash
pnpm test:rules
```

```bash
pnpm audit --prod --audit-level high
```

### 2. Unit tests (not run by CI, D-46)

```bash
pnpm exec vitest run src
```

### 3. Try it by hand

Needs the Firestore and Auth emulators, the backend, corridors loaded (NF-P1-016), a live rate cached (the refresh cron logic), and rate history backfilled (`data-scripts`, `python -m src.loaders.frankfurter_backfill --days 400`) so the chart has real data. `docs/runbooks/NF-P2-010-contract-processing-animation.md` has the emulator setup; the sequence used for this task's own verification (below) is the same.

1. Sign in, compare a corridor, scroll to "Rate history".
2. Switch periods (1M/3M/6M/1Y): the line, the "change since" line and the x-axis all update.
3. Hover the line: a tooltip with the exact date and rate follows the cursor.
4. Compare AU-IN or MY-ID: the emerald best-day badge should name a real weekday. Compare any other corridor: the "no reliable best day" message should show instead.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `pnpm lint` (`--max-warnings 0`) | Pass |
| `pnpm format:check` | Pass |
| `pnpm build` (`tsc -b`, Vite) | Pass. `TrendChart` is its own 397.63 KB / 109.44 KB gzip chunk, separate from the 1,137 KB / 338 KB gzip main bundle |
| `pnpm test:rules` | 100 passed |
| `pnpm audit --prod --audit-level high` | Exit 0; the 2 moderate advisories are `react-router` (pre-existing, unrelated to `recharts`) |
| `vitest run src` (D-46, not in CI) | 111 passed (3 new) |
| **Live browser check**, real emulators, real backend, real ECB history (280 to 365 days backfilled per pair), a throwaway test-user account | All of the following observed directly, with screenshots: the chart renders with real SG-PH and AU-IN data; period switching (1M→3M→6M→1Y) reloads correctly with the right date range and change %; hover shows the exact date and rate in a themed tooltip with a crosshair; AU-IN correctly shows the real "Wednesday, about +0.09%" best-day badge; SG-PH correctly shows "no reliable best day" (no corridor's real pattern was invented for one that has none); dark mode (`.dark` added manually, since no in-app toggle exists — decision 10) keeps full contrast on the line, grid, axes and badge; mobile viewport (375×812) has no horizontal overflow, and the chart, buttons and badge all reflow correctly |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Rate history for this corridor isn't available yet." | `rates_history/{pair}` has no `daily` map: run the backfill (NF-P2-015, D-36) or wait for the cron |
| The best-day badge never appears for any corridor | Needs about a year of history (52 weeks) to find a pattern; a fresh backfill of only 90 days will correctly show "not enough history" |
| The chart chunk doesn't seem to lazy-load | Check the Suspense boundary is still around `<TrendChart>` in `RemittanceCompare.tsx`, and that the import stays a dynamic `import()`, not a static one |
| A weekday name looks wrong in one language | `weekdayName()` uses the browser's own `Intl` data for the UI language; it isn't a translation key, so check the browser/OS locale data, not `i18n/*.json` |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind, matching existing conventions (`emerald`/`amber`/`destructive`, `Button`, `Skeleton`); one new pinned dependency
- [x] Fully mobile responsive: verified at 375×812 in a live browser, no overflow
- [ ] Works on slow network: not tested throttled; the chart has its own skeleton and Suspense fallback
- [x] Loading states: a skeleton while the query is pending, a Suspense fallback while the chart's own JS chunk loads
- [x] Error states: 404 ("not available yet"), other errors (message + retry), an empty-points state, all distinct
- [x] i18n keys for all user-facing strings, all six languages; the five weekday names use `Intl`, not translation keys, deliberately (decision 7)
- [x] Screenshots: captured during live verification (see above); not attached to this file, available on request
- [x] Accessibility: labelled `role="group"` period picker with `aria-pressed`, `aria-alert`-free load/empty states, a `sr-only` data table alternative to the chart, hidden decorative chart region (`aria-hidden`)

## Commit and PR

Branch: `feature/remittance-trend-chart` (already checked out; up to date with `main`, includes NF-P2-019 and NF-P2-022).

```
feat(remittance): add historical rate trend chart with best-day indicator
Refs: NF-P2-020
```

PR title: `feat(remittance): trend chart and best-day-to-send indicator (NF-P2-020)`

## Not covered here

- `SavingsCallout.tsx`, the "you would have saved $X" hero moment (backend built by NF-P2-022; no frontend task in the tracker owns its display yet — noticed, not fixed)
- `FlaggedProviderBadge.tsx` (NF-P3-022)
- A working dark-mode toggle anywhere in the app (decision 10; pre-existing, not discovered by a task that owns theming)
