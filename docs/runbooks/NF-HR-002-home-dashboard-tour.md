# NF-HR-002 — Home dashboard integration and first-run tour

## Summary

The signed-in home now has both new modules with **live status**, a **first-run tour** that introduces them, and a **compact phone layout** that keeps the page within two screens at 360 px.

| Part | What it does |
|---|---|
| **Scam Check card** | Says what the worker's last check found ("Last check: high risk, 2 days ago.", "no scam found", or "Paste a message to check it before you act." when there is no history). Reads `GET /api/v2/scam/checks?limit=1`; while that loads, and if it fails, the card is the plain pitch with its link, so the way in is never lost. It uses shared strings, not the `scam` namespace |
| **Coach card** | Already had Start, Continue and View plan (NF-FC-022); unchanged in what it says |
| **First-run tour** | A short modal over the home, one step for each module that is on for the worker and a closing step ("All in one place"). Skip, the close button, Escape, a tap outside and "Got it" all count as seen. Shown once per worker per browser; never for a worker with no module on; never while the flags are loading |
| **Phone layout** (below 640 px) | The greeting's actions are one row that scrolls inside the card; the four KPIs are a 2 × 2 grid; the six cards are two columns of compact tiles with a short "Open" (the full name stays for screen readers); a card keeps three lines and the first row of a list; the Radar card is its unread count; the identity ring is smaller. From 640 px up nothing changes |

## Files

| File | Change |
|---|---|
| `frontend/src/components/dashboard/ScamWidget.tsx`, `utils/scamCardState.ts` (new), `hooks/useScamChecks.ts` | The card, the pure state, and `useLatestScamCheck` (its key starts with `SCAM_CHECKS_KEY`, so a new check or report refreshes it) |
| `frontend/src/components/dashboard/FirstRunTour.tsx`, `utils/firstRunTour.ts` (new) | The tour (focus kept inside, Escape, focus handed back, page scroll locked while open, like the report sheet) and its storage and steps |
| `frontend/src/pages/Dashboard.tsx`, `GreetingBand.tsx`, `KpiRow.tsx`, `StatCard.tsx`, `WidgetCard.tsx`, `RadarAlertsWidget.tsx`, `FIBProgressWidget.tsx`, `CoachWidget.tsx` | The phone layout and the mounted tour |
| `frontend/src/components/dashboard/ModuleWidget.tsx` | Removed: `ScamWidget` replaced its only use |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `dashboard.tour.*`, `dashboard.widgets.scam.*`, `dashboard.widgets.openShort` |
| `frontend/e2e/dashboard.spec.ts` (new), unit tests | See Results |

No shared file (`package.json`, lockfile, workflows, `firebase.json`, rules) was touched, and no dependency was added.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | "At most one screen of scroll" | Read as a page at most two viewports tall at 360 × 740 (1,480 px). The home was 2,933 px (3.96 screens) before, so the v1 pieces had to be made compact on phones too |
| 2 | Where the tour is remembered | `localStorage`, per worker, in this browser (`nomadfinance.tour.v2.<uid>`), not cleared at sign-out. No backend change |
| 3 | The tour's dialog | Built like `ReportSheet`, with no dialog library, so no new dependency |
| 4 | A browser that cannot store | Counts as "seen": a tour that cannot be remembered would repeat every visit |
| 5 | Which modules it introduces | Only those on for the worker, then a closing step; none on means no tour |
| 6 | The long "Open ..." links | A short "Open" on phones, the full name for screen readers, so the accessible name is unchanged |

## Results

**Frontend (2026-10-10), run as `frontend-ci.yml` runs them:** `pnpm lint` (0 warnings), `pnpm format:check`, `pnpm test:coverage` (135 files, 1,615 tests, floors held), `pnpm build` (`tsc -b` and the build), the i18n check (1,325 keys × 6 languages), and the end-to-end job (`vite build --mode emulator`, `tsc -p e2e`, `firebase emulators:exec ... pnpm test:e2e`: 64 passed on the desktop and mobile projects).

| Check | Result |
|---|---|
| Height at 360 × 740 | **1,421 px, 1.92 screens**, with a populated worker (3 contracts, 3 alerts, an identity score, an interview under way, a scam check). Hindi 1,413, Bengali 1,427. Before: 2,933. No sideways scroll |
| The Scam card | Asks for one check; none, high, benign, unusable time and unknown risk level each say the right thing; the plain pitch while loading and on a failed read; its link is `/scam-check`; no raw key and axe-clean in six languages |
| The tour | Appears for a worker with a module who has not seen it; not with none on, flags loading, no worker, or storage blocked; per worker; forward, back and "Got it"; Skip, close, Escape and a tap outside end it for good; not ended by a tap inside; focus in the panel, Tab wraps, focus handed back; page scroll locked and released; no raw key and axe-clean on every step in six languages |
| The browser | The tour opened as a bottom sheet over the home and Escape closed it and stored the mark; the page measured as above |
| Existing tests | `CoachWidget` asserted each link's `textContent`; it now asserts the accessible name, href and order. `Dashboard.flags` mounts a stand-in for the tour (it has its own tests) |
| Break check | The first height measurement (1,617 px) and the second attempt (1,491 px, wrapping the score label) failed the target; the phone layout was adjusted until 1,421 |

**Not verified:** the layout on a real phone; screens shorter than 740 px (D-269); the wording by native speakers (D-268); the tour on a second device (it shows again by design).

## Manual test

```bash
cd frontend
pnpm vitest run src/components/dashboard src/utils/firstRunTour.test.ts src/utils/scamCardState.test.ts src/pages/Dashboard.flags.test.tsx
```

The end-to-end check, as CI runs it (stop anything on ports 8085, 9099 and 4173 first):

```bash
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:4173 pnpm exec vite build --mode emulator
pnpm exec tsc -p e2e
firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm test:e2e"
```

**Windows PowerShell:** set the variable first, `$env:VITE_API_BASE_URL = "http://127.0.0.1:4173"`, then run the same three commands.

By hand: with the `coach` and `scam` flags on for a worker, open `/dashboard` at a 360 px window. The tour opens; Skip it; reload and it does not return. Scroll the page: it should be about two screens. To see the tour again, remove the `nomadfinance.tour.v2.<uid>` key from local storage.

## Definition of Done (Frontend)

- [x] Both modules are on the home grid with live status
- [x] The tour is skippable and shown once
- [x] The home is at most one screen of scroll at 360 px (1,421 px of 1,480 allowed)
- [x] Strings in 6 languages (checked for raw keys); axe clean on the card and every tour step
- [x] Strict types, lint and format clean; no shared file touched; no dependency added
- [x] The CI jobs run locally with the same commands, including end-to-end
- [ ] Wording read by native speakers (D-268)
- [ ] Tried on a real phone
- [ ] Reviewed by a teammate (Pranjal)

## Commit

Branch: `feature/NF-HR-002-frontend-home-v2` (already checked out).

```bash
git commit -m "feat(dashboard): add scam card status, first-run tour and phone layout" -m "Refs: NF-HR-002"
```

The header is 70 characters (the limit is 72). PR title: `feat(dashboard): live module cards, first-run tour and phone layout (NF-HR-002)`
