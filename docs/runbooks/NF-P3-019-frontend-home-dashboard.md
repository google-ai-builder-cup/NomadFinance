# NF-P3-019 — Home Dashboard Tying All Pillars

Originally assigned to Aditya; picked up on your confirmation (Aditya occupied).

## Summary

`/dashboard` was a static 4-card grid (pillar name, description, "Open" link, no live data). This task turns each card into a real widget: the worker's most recent contracts and their risk, a corridor-aware remittance shortcut, their most recent radar alerts, and their Financial Identity score. Every widget loads independently — a slow or empty one never blocks the others, and the page shell always renders immediately.

## What was already there vs. what this task had to build

Checked before planning, since three of the four widgets turned out to need zero new data plumbing:

- **Radar alerts** — `useNotifications()` (NF-P3-009) and `AlertItem.tsx` reused as-is.
- **FIB progress** — `useFinancialProfile()` and `STATUS_COLOR`/`statusFor` (NF-P3-017/018) reused as-is.
- **Recent contracts** — genuinely missing. `ContractList.tsx` is an empty, unrouted stub and `contractService.ts` had no list function at all. Built `listRecentContracts` as a new direct Firestore read (light fields only — `title`, `status`, `health_score`, `risk_level`, `created_at` — never a `reports/{language}` document), the same owner-read pattern `fibService.ts`'s entry listers already use.
- **Remittance "shortcut"** — the task names this one differently from the other three ("shortcut," not "recent transfers"), and nothing reads `transfers` anywhere in the frontend. Read that literally: a CTA card using `defaultCorridor()` (already used by `RemittanceCompare.tsx`), not a new data widget.

## Files

| File | Change |
|---|---|
| `types/contract.ts` | `ContractSummary` — the light contract document's fields, distinct from `ContractAnalysis` (the analyze endpoint's response shape) |
| `services/contractService.ts` | `listRecentContracts` (new Firestore read) |
| `hooks/useContract.ts` | `useRecentContracts` |
| `components/dashboard/WidgetCard.tsx` (new) | Shared card chrome (icon, title, content, "Open" link) — the four widgets are otherwise near-identical shells |
| `components/dashboard/RecentContractsWidget.tsx` (new) | Up to 3 contracts, risk badge (reuses `RISK_BADGE_CLASSES` and the existing `contract.result.counts.*` translations) or status label |
| `components/dashboard/RemittanceShortcutWidget.tsx` (new) | Corridor-aware CTA |
| `components/dashboard/RadarAlertsWidget.tsx` (new) | Up to 2 alerts via `AlertItem`, unread count |
| `components/dashboard/FIBProgressWidget.tsx` (new) | Overall score ring + status |
| `pages/Dashboard.tsx` | Rewritten to compose the four widgets into the grid, replacing the static cards |
| i18n | `dashboard.widgets.*`, all 6 languages |

No backend changes.

## Decisions

1. **Each widget's card is a `<div>`, not a whole-card `<Link>`** (the old design's pattern) — `AlertItem` inside the radar widget needs its own real link to each notification's deep link, and nesting an `<a>` inside an `<a>` is invalid. Every widget gets an explicit "Open <pillar>" link at the bottom instead, for visual consistency across the grid even where a widget (remittance) has no inner links of its own.
2. **`WidgetCard` is a shared shell**, not four copies of the same card markup — legitimate reuse, not a speculative abstraction: all four widgets needed the identical chrome at the moment of writing them, not a hypothetical future one.
3. **Risk badges reuse `contract.result.counts.safe/caution/danger`** (already translated, already used by `ReportCard.tsx`) rather than new `dashboard.*` keys for the same three words.
4. **Each widget's query is independent** (`useRecentContracts`, `useUserProfile`, `useNotifications`, `useFinancialProfile`, four separate hooks) rather than one combined "dashboard summary" query — matches this app's existing pattern (e.g. `FIBDashboard.tsx`'s profile vs. timeline) and means a brand-new worker with nothing anywhere still gets a page that renders instantly, each card settling into its own empty state independently.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean |
| `prettier --check .` | Clean (4 files auto-formatted) |
| `pnpm exec vitest run` | 133 passed, unchanged (no new pure logic to unit test) |
| `pnpm run build` | Clean; `recharts` stays in its own lazy chunk, ~9 KB total growth from this task's code |

**Live browser (Firebase emulators)**

- **Brand-new worker, nothing anywhere**: all four widgets render their own correct empty state at once — "Upload a contract to get started," the corridor shortcut (correctly reading the worker's own onboarding profile: "Singapore to India"), "No alerts yet," "Log activity to start building your score." No spinner stuck open, no layout collision between four empty cards.
- Wrote one `financial_profile/current`, two contracts (one `completed` with a risk level, one `processing` with no title), and one unread notification directly into the Firestore emulator (admin SDK) and reloaded: every widget switched to its populated state correctly — the risk badge, the "Checking…" status label for the title-less processing contract, the unread-count line plus the real `AlertItem` row (confirmed its own link and deep link both correct), and the score ring in the right status color (65 → amber "Fair").
- Mobile (375×812) light mode and desktop dark mode — both clean, cards stack correctly, no truncation issues on the longer contract title.

## Manual test steps

Same emulator setup as the other FIB runbooks. To populate all four widgets at once without running every pillar's real pipeline:

```bash
cd data-scripts
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 .venv/bin/python -c "
from google.cloud import firestore
from datetime import datetime, timezone
client = firestore.Client(project='demo-nomadfinance')
uid = '<uid from the users collection>'
now = datetime.now(timezone.utc)
client.collection('users').document(uid).collection('contracts').document('c_01').set({
    'status': 'completed', 'title': 'Test Contract', 'legibility': 'good',
    'mime_type': 'application/pdf', 'size_bytes': 1, 'content_hash': 'x',
    'health_score': 58, 'risk_level': 'caution', 'clause_counts': {'safe': 1, 'caution': 1, 'danger': 0},
    'report_languages': [], 'law_version': 1, 'prompt_versions': {},
    'created_at': now, 'updated_at': now, 'schema_version': 1,
})
client.collection('users').document(uid).collection('notifications').document('n_01').set({
    'type': 'radar_alert', 'title': 'Test alert', 'body': 'Test body', 'language': 'en',
    'deep_link': '/radar/alerts', 'read': False, 'created_at': now, 'schema_version': 1,
})
"
```

(NF-P3-017's runbook has the `financial_profile/current` script.)

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Recent contracts widget always empty despite uploaded contracts | Check `orderBy("created_at", "desc")` isn't failing on a missing composite index — single-field range/order on one subcollection needs none, per `fib.md`'s same note about `entry_date` |
| Remittance shortcut shows the wrong corridor | It reads the worker's own profile (`host_country`/`home_country`), not a fixed default — check onboarding actually saved those fields |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind + shadcn/ui (reuses `Button`-free plain Tailwind cards, matching the original Dashboard's own style)
- [x] Mobile responsive — verified live at 375×812
- [ ] Slow network — not tested throttled
- [x] Loading states (each widget shows its own small loading text independently)
- [x] Error states (each widget degrades to its own inline error, doesn't block the others)
- [x] i18n keys added for all user-facing strings, all 6 languages
- [x] Screenshots — captured during live verification, sent to you directly

## Commit and PR

Branch: `feature/frontend-home-dashboard` (already checked out).

```
feat(dashboard): add live pillar widgets to the home dashboard
Refs: NF-P3-019
```

## Noticed, not fixed

- `ContractList.tsx` remains an empty, unrouted stub — a full contract list page was never part of this task's scope (only "recent," for the widget).
- A few stale `net::ERR_CONNECTION_REFUSED` / 500 entries showed up in the browser console's history during this session, left over from restarting local emulator servers between earlier tasks in the same long-running browser pane — not reproducible on a fresh load of this page, and every live check here rendered correctly with no visible error state.
