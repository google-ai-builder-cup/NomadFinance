# NF-P3-008 — Radar: Entity Profile Page

## Summary

A page showing one business's aggregated profile — risk badge, flagged badge, report/incident counts, community rating, corridors/countries — plus the individual reports behind it, newest first. Reached from the heatmap's marker popup (new "View business profile" link) or directly at `/radar/entity/:slug`.

`radar_entities/{slug}` (the aggregated profile) was already client-readable straight from Firestore — the heatmap (NF-P3-007) already reads the whole collection this way. `radar_reports` isn't (`firestore.rules` denies it entirely), so "aggregated report list per entity" needed a new backend endpoint; `firestore-schema.md`'s required-index table had already anticipated this exactly (`radar_reports: entity_slug asc, created_at desc — Entity profile page (NF-P3-008)`).

## Files

**Backend**

| File | Change |
|---|---|
| `backend/app/repositories/radar_repo.py` | `list_by_entity(slug)` — the new composite-index query |
| `backend/app/schemas/radar_report.py` | `RadarReportSummary` — the client-facing shape, `reporter_hash` and the classification internals left out |
| `backend/app/services/radar/entity_reports.py` (new) | `list_entity_reports()` |
| `backend/app/api/v1/radar.py` | `GET /radar/entities/{slug}/reports` |
| `docs/api/endpoints.md` | New endpoint's row and section |
| 2 new test files | 9 tests: the service, and the endpoint (auth, empty-for-unknown-slug, shape validation, never leaks internals) |

**Frontend**

| File | Change |
|---|---|
| `frontend/src/types/radar.ts` | `RadarReportSummary`, `ReportSource` |
| `frontend/src/services/radarService.ts` | `getEntityReports()` |
| `frontend/src/hooks/useRadar.ts` | `useRadarEntity(slug)` (shares `useRadarEntities`'s cache — no extra fetch), `useEntityReports(slug)` |
| `frontend/src/components/radar/EntityRiskCard.tsx` (was an empty stub) | Risk badge, flagged badge, counts, rating, corridors/countries |
| `frontend/src/components/radar/EntityReportList.tsx` (new) | The report list itself |
| `frontend/src/pages/radar/RadarEntity.tsx` (was an empty stub) | Wires it together; loading/error/not-found states |
| `frontend/src/router.tsx` | `/radar/entity/:slug` |
| `frontend/src/components/radar/HeatmapMap.tsx` | Marker popup gets a "View business profile" link, now that the destination exists |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | New `radar.entity.*` keys, all 6 languages; `radar.heatmap.viewProfile` |

## Decisions

1. **`useRadarEntity(slug)` derives from `useRadarEntities()`'s already-cached list rather than a fresh single-doc Firestore read.** The heatmap has usually already populated that cache; even cold, fetching the whole (small, ~15-20 entity) collection once is simpler than adding a second read path. `entity` is typed `RadarEntityProfile | null`, doing double duty for "still loading" and "no entity at this slug" — safe because the page always checks `isPending`/`isError` before ever reading `entity`, so by the time `null` is treated as "not found" it really is.
2. **A new backend endpoint, not a Firestore rules change.** `radar_reports` stays fully backend-only, matching its own documented design ("no client access... the backend leaves out reporter_hash"); `RadarReportSummary` also drops the classification internals (`spam_score`, `category_confidence`, `model`) and the redundant `entity_slug`/`entity_type`/`entity_name` (every report in the list is about the same entity already on screen).
3. **An unknown slug and an entity with no reports both return an empty list, not a 404** — indistinguishable from a `radar_reports` query alone, and nothing is gained by telling them apart. The frontend's own "not found" state is driven entirely by `radar_entities` (client-side), never by this endpoint.
4. **The rating line avoids repeating itself.** The heatmap's popup reuses one combined string (`"Community rating: 4 / 5"`) because it has no separate label; the profile page's stat block already has a `<dt>` label, so reusing that same string would read "Community rating / Community rating: 4 / 5". Added a second key (`ratingValue`, just `"{{rating}} / 5"`) instead of fighting the existing one.
5. **Live-verified against real seed data in the Firestore emulator**, not just built and hoped: signed in a throwaway test user, seeded one `radar_entities` doc and two `radar_reports` docs directly via the emulator's REST admin-bypass, and clicked through the actual heatmap → popup → profile page flow. Caught and fixed the rating-redundancy issue (decision 4) this way, live, before calling it done — not something a type-checker would have caught.

## Verified results (2026-10-01)

**Backend**

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (39 files) |
| `pytest` (full suite) | 754 passed (9 new), 51 skipped |

**Frontend**

| Check | Result |
|---|---|
| `tsc --noEmit` | Clean (after `pnpm install` — `leaflet`/`react-leaflet`/`react-leaflet-cluster` were in `package.json` from NF-P3-007 but not yet installed locally; unrelated to this task, fixed by syncing `node_modules` to the existing lockfile) |
| `pnpm lint` (`--max-warnings 0`) | Clean |
| `pnpm exec prettier --write .` | Clean (only `HeatmapMap.tsx`, the one existing file this task touched, needed reformatting) |
| `pnpm exec vitest run src` | 124 passed, no new test file — this frontend has no established component-test (`.test.tsx`) pattern anywhere (11 existing `.test.ts` files are all pure-logic utils); verification here follows the project's own Frontend DoD instead: live browser, not unit tests |
| `pnpm build` | Clean (pre-existing >500kB chunk warning from `leaflet`/`react-leaflet`, NF-P3-007, unrelated to this task) |

**Live browser (Firestore emulator, seeded data, a real signed-in test user)**
- Heatmap marker popup → "View business profile" → correct navigation to `/radar/entity/example-remit`
- Full page render: risk badge, flagged badge, report/incident counts, rating, corridors, both seeded reports with correct violation labels, summaries and dates
- Not-found state (`/radar/entity/no-such-entity`)
- Mobile viewport (375×812): no horizontal overflow (`scrollWidth === clientWidth`), confirmed by direct DOM check, not just a screenshot
- Hindi: every new string renders translated, including reused `radar.violation.*` keys, `countryName()`-translated corridor names, and locale-aware date formatting — no missing-key fallbacks
- Dark mode: all new elements themed correctly

## Manual test steps

bash / PowerShell (same commands):
```bash
# With the emulators + backend + frontend running (.claude/launch.json: backend-emulators,
# backend-api-emulator, frontend-emulator) and at least one radar_entities document seeded
# (real data after NF-P3-005's loader has run, or seed one by hand the way this task's own
# verification did — see the emulator's REST API, Authorization: Bearer owner):

# 1. Sign in, then open the heatmap.
open http://127.0.0.1:5173/radar

# 2. Click a flagged marker, click "View business profile" in its popup.
# 3. Or go directly to a known slug:
open http://127.0.0.1:5173/radar/entity/<slug>

# 4. Try an unknown slug to see the not-found state:
open http://127.0.0.1:5173/radar/entity/no-such-entity
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `tsc`/build fails with "Cannot find module 'leaflet'" | Stale local `node_modules` — run `pnpm install` to sync it to the committed lockfile (this is what NF-P3-008 hit; not caused by this task) |
| Entity profile page shows "not found" for a slug you know exists | Check `useRadarEntities()`'s query actually returned data — the profile page never queries Firestore on its own, it only reads the heatmap's shared cache |
| Report list is empty but `report_count` on the badge is nonzero | Check the composite index (`entity_slug` asc + `created_at` desc) exists on `radar_reports` in the target Firestore — same index NF-P3-004's surge detection needs on a different field pair; a missing index here fails silently into an empty list rather than a visible error (`radar.list_by_entity` isn't wrapped in the same try/except pattern as the alert cron, since a failed query here would surface as FastAPI's own 500, not something worth silently swallowing on a user-facing GET) |

## Definition of Done

**Backend Endpoint**
- [x] Endpoint defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification
- [x] Structured logging — base middleware only; nothing extra needed for a plain read
- [x] Error handling with specific HTTP status codes (401/422)
- [x] Manual test via Swagger — done live, via the full browser flow, not `/docs` directly
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied (API-wide only, no Gemini call)

**Frontend Feature**
- [x] Built with Tailwind, matching existing conventions (shadcn-style cards, `<dl>` stat blocks); no new dependency
- [x] Mobile responsive — verified live at 375×812, no overflow
- [ ] Slow network — not tested throttled
- [x] Loading states (`LoadingSpinner`, matching the heatmap's own pattern)
- [x] Error states (load-error + retry, not-found) handled gracefully
- [x] i18n keys added for all user-facing strings, all 6 languages, verified live in Hindi
- [x] Screenshots — captured during live verification; available on request
- [x] Accessibility: semantic `<dl>`/`<dt>`/`<dd>` for stats, `aria-labelledby` on the reports section, `role="alert"` on error states, keyboard-reachable back link and retry buttons

## Commit and PR

Branch: `feature/radar-entity-page` (already checked out).

```
feat(radar): add entity profile page
Refs: NF-P3-008
```

PR title: `feat: exploitation radar entity profile page (NF-P3-008)`

## Noticed, not fixed

- No pagination on the report list — fine at prototype/demo scale (NF-P3-005 seeded 15-20 reports total, across every entity), would need revisiting if that scale changes.
- No link from the entity profile back to a corridor filter on the heatmap, or forward to anything else — this task only had to connect the heatmap → profile direction.
