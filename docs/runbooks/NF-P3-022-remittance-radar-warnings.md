# NF-P3-022 — Cross-Pillar: Radar Warnings in Remittance UI

## Summary

A provider in the Remittance X-Ray comparison that Exploitation Radar has flagged now carries a red "Community flagged" badge, linking to its radar profile. This is the Radar → Remittance arrow of the cross-pillar flow (design doc §5.6). Frontend only: no backend, rules, seed or dependency change.

Not in this task: the same badge on Contract Shield's report card (NF-P3-023), and any change to the radar seed data (see "Demo caveat").

## How it works

- **Data:** `radar_entities/{slug}`, the profile NF-P3-003 keeps up to date. Signed-in users can read it, and the heatmap already does; the badge reuses that query (`useRadarEntities`, one read per page, cached 60 s).
- **Match:** the provider's name is slugified and compared with the profile's slug, or with a slug of one of its `aliases`. `utils/slug.ts` has to give what the backend's python-slugify gives (the slug is the join key, `docs/data-model/collections/radar.md`); a test checks 20 names against the backend's own output, including every World Bank provider name that is not plain words.
- **What counts:** a profile that is `flagged` (two or more distinct incidents, a pattern rather than one unverified report) and whose type is `money_transfer_operator`. A single report, an employer, or a recruitment agency with the same name never shows a badge.
- **Where it shows:** beside the provider in each table row, beside "Best service" in the headline card, and in the "paid in another currency" list.
- **Failure:** while loading, or if the read fails, no badge shows and nothing else changes. A warning is an extra, so it cannot break a comparison. A failed first load is not toasted (the query client only toasts failed refetches).
- **Accessibility:** the badge is a real link with an `aria-label` that says the report count and the provider ("Community flagged: 4 worker reports about Example Remit. View details."); the icon is decorative.

## Files

| File | Change |
|---|---|
| `utils/slug.ts` (new) | `slugify`, same output as the backend for Latin-script names |
| `utils/flaggedProviders.ts` (new) | `findFlaggedEntity(firm, entities)`, pure |
| `hooks/useRadar.ts` | `useFlaggedProvider(firm)` |
| `components/remittance/FlaggedProviderBadge.tsx` | Was an empty stub |
| `components/remittance/ComparisonTable.tsx`, `pages/remittance/RemittanceCompare.tsx` | Badge in rows, headline and not-comparable list |
| `types/radar.ts` | Optional `aliases` on `RadarEntityProfile` (already in the document) |
| `i18n/*.json` (6) | `remittance.flagged.label` and `.detail` |
| `utils/slug.test.ts`, `utils/flaggedProviders.test.ts`, `components/remittance/FlaggedProviderBadge.test.tsx` (new) | 30 tests |

## Decisions

1. **`flagged`, not "any report".** The data-model doc says `flagged` is what drives these badges; one report is not verified. A profile with a single incident shows nothing.
2. **Company-level, not corridor-level.** A flagged operator is warned about on every corridor it appears on; the profile page lists the corridors the reports were about. Narrowing to the viewed corridor would hide a pattern the worker should still know about.
3. **Name match, with aliases as the escape hatch.** Exactly what the data-model doc prescribes. Known limit: a provider the World Bank spells differently from the way workers report it (for example `PNB (Philippines National Bank)`) misses until an alias is added to its profile.
4. **No new component test library.** The badge test renders to static markup with `react-dom/server`; adding jsdom or Testing Library would edit `package.json`.

## Demo caveat

None of the five operators in the radar seed (Merlion QuickSend, Ganga Transfer Hub, Kapitan Padala, Southern Cross Remit, Nusantara Kirim) is among the 70 providers of the World Bank comparison data, so **with the current seed the badge does not appear in the demo**. The seed was left alone on purpose: making it appear would mean attaching invented incident reports to real companies. The Contract Shield badge (NF-P3-023) does not have this problem, because the employers and agencies in the seed and in the sample contracts are invented. If the team later wants it visible here, that is a deliberate data-scripts change with an explicit "demo data" label, not a frontend one.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean |
| `prettier --check .` | Clean with `--end-of-line auto` (the plain check flags every CRLF checkout file on Windows, including ones this task did not touch) |
| `vitest run` | 162 passed. The two `tests/rules` files fail without the Firestore emulator, as before (`pnpm test:rules` runs them with one) |
| `pnpm run build` | Clean |

**Live browser (Auth + Firestore emulators, `frontend-emulator`)**: signed in with a test phone number, wrote four profiles into the emulator, and answered `/remittance/compare` with a canned comparison (the backend was not running) whose providers are all fictional:

| Provider in the comparison | Profile in the emulator | Badge |
|---|---|---|
| Example Remit | `example-remit`, flagged operator, 4 reports | Yes: headline and table row |
| Sample Bank (Alias Test) | `pnb`, flagged operator, alias `Sample Bank (Alias Test)` | Yes, through the alias |
| Test QuickPay | `test-quickpay`, one report, not flagged | No |
| Sample Cash Express | `sample-cash-agency`, flagged but an employer | No |
| Plain Provider | none | No |

Clicking the badge opened `/radar/entity/example-remit`. Checked at 1024 px and 375 × 812 (the badge wraps under the name, no overflow). The dark-theme look was not checked; the badge uses the same `destructive` tokens as the entity page's flagged badge. The console showed only 500s from the backend that was not running (savings, trends, report list).

## Manual test steps

1. Start the emulators (from `frontend/`) and the dev server:
   ```bash
   firebase emulators:start --only auth,firestore --project demo-nomadfinance
   ```
   ```bash
   pnpm dev --mode emulator
   ```
2. Sign in at `http://localhost:5173/sign-in` with any phone number; the code is at `http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`. Finish onboarding.
3. Add a flagged operator whose name is a provider of the corridor you will compare (from `data-scripts/` with the venv active; `Wise` is a real provider, so use a throwaway emulator only and never the real project):
   ```bash
   FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 python - <<'EOF'
   from datetime import datetime, UTC
   from google.cloud import firestore
   c = firestore.Client(project="demo-nomadfinance")
   now = datetime.now(UTC)
   c.collection("radar_entities").document("<slug of the provider>").set({
       "name": "<provider>", "slug": "<slug of the provider>",
       "entity_type": "money_transfer_operator", "aliases": [],
       "corridors": ["SG-IN"], "host_countries": ["SG"],
       "report_count": 3, "incident_count": 3, "violation_counts": {"hidden_fees": 3},
       "first_reported_at": now, "last_reported_at": now, "community_rating": 3.5,
       "risk_level": "medium", "flagged": True, "updated_at": now, "schema_version": 1})
   EOF
   ```
4. Run the backend against the same emulator (see `NF-P1-009-frontend-firebase-auth.md`), load the corridors (`python -m src.loaders.corridors` with the emulator host set), and compare on `/remittance`. The provider shows "Community flagged"; setting `"flagged": False` in the document removes it after the 60 s cache or a reload.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A flagged provider shows no badge | Its slug differs from the provider's name: compare `slugify(<name>)` (`utils/slug.ts`) with the document id, or add the World Bank spelling to the profile's `aliases` |
| Badge shows for the wrong business | Two businesses share a name and so a slug; they are one profile by design (`radar.md`) |
| No badge on any row, console shows `permission-denied` | Not signed in, or `firestore.rules` does not allow `radar_entities` reads |
| A change to `flagged` takes a minute to appear | `useRadarEntities` caches for 60 s; reload the page |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind and the existing components (same badge style as the radar entity page)
- [x] Mobile responsive: checked at 375 × 812
- [ ] Slow network: not tested throttled
- [x] Loading and error states: no badge and no change to the comparison
- [x] i18n keys added in all 6 languages
- [ ] Screenshots added to the PR: left for the PR (captured during the live check, not saved to the repo)
- [x] Accessibility: a real link, keyboard focus ring, descriptive `aria-label`, decorative icon hidden
