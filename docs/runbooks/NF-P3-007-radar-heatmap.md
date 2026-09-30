# NF-P3-007 — Radar: Heatmap Map View

## Summary

`/radar` (and `/radar/heatmap`, the same page) shows an OpenStreetMap map of the Asia-Pacific region with the six money corridors drawn as lines (thicker and redder with more reports) and flagged businesses as clustered markers. Below the map is a plain list of the corridors with their report counts, which also serves keyboard and screen-reader users. A "Report a problem" button links to the form from NF-P3-006. Frontend only: no backend, rules or index change.

Not in this task: entity profile page (NF-P3-008), alert feed (NF-P3-009), warning badges (NF-P3-022, NF-P3-023).

## Where the data comes from

The page reads `radar_entities` directly from Firestore (signed-in users may read it; it holds no personal data). `radar_reports` is not readable from the browser, so nothing here uses individual reports. All entities are read in one call and cached for 60 seconds; at this scale no index or filtered query is needed.

- **Corridor line** = sum of `report_count` of the entities that list that corridor. An entity's count is not split by corridor, so a business on two corridors counts in full on both.
- **Heat level** (colour and thickness) = share of the busiest corridor: up to a third, up to two thirds, above. No reports = grey.
- **Marker** = one per business with `flagged: true` (two or more incidents), colour by `risk_level`. Businesses have no address, so a marker sits on the business's host country, and businesses of the same country are spread in a small spiral; the cluster layer groups them when zoomed out. Employers (country only, no corridor) appear as markers but not on a corridor line.
- **Type filter** (all, money transfer service, agency, employer) re-totals the lines and markers.
- Country coordinates are a fixed table in `utils/radarMap.ts` (rough centres of the 11 countries in scope).

## Dependencies added (approved shared-file change)

`frontend/package.json` and `pnpm-lock.yaml`: `leaflet` 1.9.4, `react-leaflet` 4.2.1, `react-leaflet-cluster` 2.1.0, dev `@types/leaflet` 1.9.22. React-leaflet 5 needs React 19, and the app is on React 18, so version 4 is used; `react-leaflet-cluster` 2.1 is the line built for it. Upgrade the three together when the app moves to React 19.

## Files

- `frontend/src/utils/radarMap.ts` and `radarMap.test.ts`: coordinates, corridor totals and levels, filter, marker placement
- `frontend/src/components/radar/HeatmapMap.tsx`: the map
- `frontend/src/pages/radar/RadarHeatmap.tsx`: page, filter, legend, corridor list, loading, empty and error states
- `frontend/src/services/radarService.ts` (`listRadarEntities`), `hooks/useRadar.ts` (`useRadarEntities`), `types/radar.ts` (`RadarEntityProfile`)
- `frontend/src/router.tsx`: `/radar` and `/radar/heatmap`
- `frontend/src/i18n/*.json`: `radar.heatmap.*` in all six languages

## Test it by hand

Needs a signed-in, onboarded user and data in `radar_entities` (load it with NF-P3-005: `python -m src.loaders.radar_seed`, see `data-scripts/README.md`, against the same Firestore the app uses).

```bash
cd frontend
pnpm dev
```

1. Open `/radar`. With the seed data: six lines, `SG-PH` and `AU-PH` reddest, `AU-IN` and `MY-ID` thinnest; five to six markers (flagged businesses).
2. Hover a line: a tooltip with the route and its report count. Click a marker: a popup with name, type, reports, rating, main violation.
3. Zoom out on the region: nearby markers merge into a numbered cluster; click it to zoom in.
4. Change the filter to "Employer": only Korea and Hong Kong businesses remain, all lines grey.
5. With an empty `radar_entities`: "No reports yet" and the report button.
6. Turn off the network and reload: the retry message appears.
7. Change language in the header: labels follow. Shrink the window to phone width: the map keeps its width, the corridor list stacks.
8. Use the keyboard only: the filter, report button and corridor list are reachable (the map itself is mouse and touch).

## Limits

- Not run in a browser by me: the page is behind sign-in and needs Firestore data. Type-check, lint, `pnpm build` and 124 unit tests passed; the map's rendering (tiles, clustering, popups) needs your eyes.
- Tiles come from `tile.openstreetmap.org`. That server's usage policy is for light use; for a public launch use a tile provider with an agreement. The map needs internet, and the service worker does not cache tiles.
- Marker positions are per country, not per address, so they show where a business operates, not where an incident happened.
- The hi, tl, id, ne and bn strings were written without a native speaker; have them reviewed.
- `pnpm build` warns that the main chunk is over 500 kB; Leaflet adds to it. Lazy-loading the radar pages would fix it and is out of scope.
