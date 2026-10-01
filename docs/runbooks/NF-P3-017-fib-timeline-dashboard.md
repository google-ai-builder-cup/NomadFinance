# NF-P3-017 — FIB: Financial Timeline Dashboard

Your own task (reassigned from Aditya to you per tasks.md, to rebalance Week 3).

## Summary

`/identity`'s new home page: the overall score and four metric meters from the weekly-computed `financial_profile/current` (NF-P3-013), an income-vs-expense bar chart over the trailing 12 months, and income/expense category breakdowns — the last two read live from the raw `income`/`bills` subcollections, not the weekly-stale profile. `/identity` previously rendered the log-activity form (NF-P3-016's own choice); that's moved to `/identity/log`, matching every other pillar's IA (its primary route is the overview, not a form).

Three things changed the shape of this task from a literal reading of the tracker row, flagged and confirmed with you before building:

1. `financial_profile/current` doesn't exist at all for a worker with zero scoreable activity in the trailing 12 months — `profile_builder.py` returns `"no_data"` and writes nothing, not a zeroed document. The score meter needed its own real empty state, separate from "the chart has nothing to show yet."
2. The chart and category breakdowns read `income`/`bills` directly from Firestore (owner-readable per `firestore.rules`), live, not through the weekly-computed profile — `fib.md` says timeline queries are meant to hit `entry_date` ranges on the subcollections directly.
3. Nothing converts between currencies client-side (no general FX-conversion endpoint exists, only the remittance compare flow's own corridor rates). The chart and breakdowns total the majority currency in the window and exclude the rest — the same exclusion philosophy `profile_metrics.py` already applies server-side, just computed client-side by majority instead of by home-country FX rate.

## Files

| File | Change |
|---|---|
| `types/fib.ts` | `FinancialProfile`, `MetricKey`, `MetricResult`, and Firestore-read entry shapes (`IncomeEntry`, `BillEntry`, `SavingsEntry`) — distinct from the log endpoints' response types: no `entry_id` field (the doc id isn't stored inside the document), and `created_at` is a Firestore `Timestamp`, not an ISO string |
| `services/fibService.ts` | `getFinancialProfile`, `listIncomeEntries`, `listBillEntries`, `listSavingsEntries` — all direct Firestore reads, no backend call |
| `hooks/useFIB.ts` | `useFinancialProfile`, `useFinancialTimeline`, and the exported `financialTimelineKey` helper; the four existing log mutations now `refetchQueries` on it on success |
| `utils/fibTimeline.ts` (new) | Pure, unit-tested: `monthKey`, `monthWindow`, `majorityCurrency`, `monthlyTotals`, `incomeByCategory`/`billsByCategory` |
| `utils/fibTimeline.test.ts` (new) | 9 tests |
| `utils/fibForm.ts` | Exported `currencyDecimals` (was private to `parseAmount`), reused by the new chart/breakdown formatting |
| `utils/fibChartColors.ts` (new) | Named exports for the CSS custom properties below, referenced by role, never raw hex |
| `styles/tokens.css` | New `--chart-income`, `--chart-expense`, `--chart-cat-1..8` custom properties, light and dark |
| `components/fib/ScoreMeter.tsx` (was an empty stub) | Overall score, 4 metric meters, narrative, no-profile-yet state |
| `components/fib/FinancialTimeline.tsx` (was an empty stub) | Grouped bar chart, lazy-loaded from the page (see decisions) |
| `components/fib/CategoryBreakdown.tsx` (was an empty stub) | Two direct-labeled horizontal bar lists |
| `pages/fib/FIBDashboard.tsx` (was an empty stub) | Composes the three, "Log activity" button to `/identity/log` |
| `router.tsx` | `/identity` → `FIBDashboard` (was `FIBLogActivity`); new `/identity/log` → `FIBLogActivity` |

No backend changes.

## Decisions

1. **The brand teal (`--primary`) doesn't work as a categorical chart color.** Ran the dataviz skill's validator against it for a categorical palette: it fails the chroma floor in light mode (reads as gray) and the lightness band in dark mode (too light). Used the skill's own reference 8-hue categorical order instead — validated clean (all checks pass, only the documented contrast WARN, mitigated by the direct labels this page already uses) against this app's actual light (`#ffffff`) and dark (`#0c1418`) surfaces, not just the skill's generic ones.
2. **Income/Expense = slots 1/2 (blue/orange) of that same validated order**, not new colors — an already-validated adjacent pair, and distinct from the categorical breakdown's own use of the full 8-slot sequence, since the two charts are never shown overlaid.
3. **The chart and breakdowns exclude non-majority-currency entries rather than attempting conversion.** Flagged as a real constraint before building: there's no generic FX-conversion capability client-side. In practice a worker logs consistently in their own host currency (NF-P3-016 defaults the picker to it), so this rarely matters; it's the same tradeoff the backend itself makes, just resolved by majority-in-window instead of home-country rate.
4. **The "live" requirement is `refetchQueries` on mutation success, not an `onSnapshot` listener.** Matches `useUser.ts`'s existing `useUpdateProfile`/`useCompleteOnboarding` pattern exactly. `onSnapshot` stays reserved for `watchContractProgress`, where the backend is actively mutating a doc over several seconds mid-pipeline — not this case.
5. **`FinancialTimeline` is lazy-loaded from `FIBDashboard`**, caught by checking the build output after first wiring it in directly: `recharts` (already used by `TrendChart`) got pulled back into the main bundle, undoing that component's own `lazy()` split (D-45). Fixed by mirroring `RemittanceCompare.tsx`'s exact pattern; confirmed by rebuilding — `generateCategoricalChart` (382 KB) is back in its own shared chunk, main bundle back down near its pre-task size.
6. **Status colors (good/warning/critical) are the dataviz skill's own fixed palette**, not themed, always paired with a text label — mirrors `EntityRiskCard.tsx`'s `RISK_COLOR` precedent (plain hex constant + inline `style`) for the same reason: no Tailwind-config color token exists for this, and these three meanings are reserved, never reused as a 4th categorical slot.
7. **`savings_rate`'s meter shows the actual percentage** (`detail.savings_rate`, e.g. "10%"), not the abstract 0–100 score the other three metrics show — it's the one metric the task names explicitly ("Savings rate meter"), and the real number is more meaningful to a worker than a normalized score.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean |
| `prettier --check .` | Clean (4 files auto-formatted) |
| `pnpm exec vitest run` | 133 passed (9 new, `fibTimeline.test.ts`), 11→12 test files passing. The 2 Firestore/Storage rules files still need `pnpm test:rules`'s emulator wrapper — unrelated, pre-existing |
| `pnpm run build` | Clean; confirmed the `recharts` core is its own lazy chunk again after fixing decision 5, not bundled into `index` |

**Live browser (Firebase emulators, a fresh signed-in test worker)**

- **Empty state**, brand-new worker: score meter's own "not ready yet" message with a "Log activity" link, timeline and breakdown both showing their own empty messages — confirmed this is a real, distinct empty state, not a loading spinner stuck open
- Logged an income entry and a bill from `/identity/log`, navigated to `/identity`: the chart and breakdown showed the new entries immediately (confirms the `refetchQueries`-on-mutation wiring, decision 4) — correct bar heights, correct category rows, correct percentages
- Wrote a realistic `financial_profile/current` document directly into the Firestore emulator (admin SDK, bypassing rules, standing in for the weekly cron) to verify the populated score meter: overall score, all four metric meters including the null-score case ("Sending money home: Not enough data yet" instead of a broken 0% bar), the savings-rate percentage display, and the narrative text — all rendered correctly
- Mobile (375×812) and dark mode — both clean, confirmed the status colors (good/warning/critical) and chart legend swatches keep clear contrast on the dark surface

## Manual test steps

Same emulator setup as NF-P3-016's runbook. To see a populated score meter without waiting for a real weekly cron run, write a test `financial_profile/current` document directly:

```bash
cd data-scripts
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 .venv/bin/python -c "
from google.cloud import firestore
from datetime import datetime, timezone
client = firestore.Client(project='demo-nomadfinance')
uid = '<uid from the users collection>'
client.collection('users').document(uid).collection('financial_profile').document('current').set({
    'reporting_currency': 'SGD', 'period_start': '2026-04-01', 'period_end': '2026-10-01',
    'months_of_data': 6, 'entry_counts': {'income': 6, 'transfers': 0, 'bills': 12, 'savings': 4},
    'metrics': {
        'income_stability': {'score': 82, 'detail': {}},
        'savings_rate': {'score': 55, 'detail': {'savings_rate': 0.1}},
        'remittance_consistency': {'score': None, 'detail': {'reason': 'no_transfers'}},
        'bill_payment_reliability': {'score': 35, 'detail': {}},
    },
    'overall_score': 57,
    'narrative': {'language': 'en', 'text': 'Test narrative.', 'model': 'gemini-3.5-flash'},
    'prompt_versions': {}, 'computed_at': datetime.now(timezone.utc), 'schema_version': 1,
})
"
```

PowerShell: same Python one-liner works unchanged once the venv and `FIRESTORE_EMULATOR_HOST` are set per NF-P1-001's PowerShell conventions.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Score meter stuck on "isn't ready yet" despite logged activity | Expected — only the weekly cron (NF-P3-013) writes `financial_profile/current`; use the manual-test script above to see the populated state without waiting |
| Chart/breakdown show nothing despite logged entries | Check the entries are all in the same currency — a different currency than the majority in the window is silently excluded (decision 3), by design |
| New entry doesn't appear until a manual refresh | Check the mutation's `onSuccess` actually fired (network tab, 201) — the dashboard refetches on log success, not on a timer |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind + shadcn/ui (reuses `Button`/`Skeleton`; charts and meters are plain Tailwind + inline style for data-driven color, matching `EntityRiskCard`/`ComparisonTable` precedent)
- [x] Mobile responsive — verified live at 375×812
- [ ] Slow network — not tested throttled
- [x] Loading states (`LoadingSpinner` while the timeline query is pending, chart `Skeleton` while its lazy chunk loads)
- [x] Error states (timeline load failure blocks the page with a retry; score load failure degrades gracefully with its own inline retry, not blocking the rest of the page)
- [x] i18n keys added for all user-facing strings, all 6 languages
- [x] Screenshots — captured during live verification, sent to you directly

## Commit and PR

Branch: `feature/fib-timeline-dashboard` (already checked out).

```
feat(fib): add financial timeline dashboard
Refs: NF-P3-017
```

## Noticed, not fixed

- No period picker (fixed 12-month window, matching the backend's own convention) — flagged as an intentional scope cut in the original plan, not a gap found mid-build.
- `verified_employment` and `latest_export` (both on `financial_profile/current`) aren't surfaced on this dashboard — out of this task's scope (export UI is NF-P3-018; verified-employment display wasn't asked for here).
