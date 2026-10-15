# NF-P3-023 — Cross-Pillar: Radar Warnings on Contract Shield

## Summary

When the employer or recruitment agency a contract names has been flagged by Exploitation Radar, the Contract Health Report now shows a red "Community flagged — N reports" warning under the risk badge, linking to the business's radar profile. This is the Radar → Contract Shield arrow of the cross-pillar flow (original design). Frontend only: no backend, rules, seed or dependency change.

Not in this task: the other direction (Contract Shield's own danger clauses becoming radar reports, NF-P2-021), the same warning in Remittance X-Ray (NF-P3-022), and any change to the radar seed.

## How it works

- **Names:** `users/{uid}/contracts/{id}.extracted.employer_name` and `.agency_name`, written by the detect step (`contracts.md`). The analyze response does not carry them, so `getContractParties` reads the contract document from Firestore (the owner may read it; the progress watcher already does).
- **Profiles:** `radar_entities`, through the heatmap's cached query (`useRadarEntities`). No extra read per page.
- **Match** (`utils/flaggedParties.ts`):
  - An employer name must match an `employer` profile and an agency name a `recruitment_agency` profile, the two types the backend's contract signal files them under.
  - The profile must be `flagged` (two or more distinct incidents). One report is not verified and shows nothing.
  - Names are compared by `matchKey`: the slug without trailing legal-form words (Co, Ltd, Pty, Sdn Bhd, Inc, Corp and a few more), against the profile's slug, name and aliases. So "Han River Metals Co., Ltd." on the contract meets the profile "Han River Metals Co". Only trailing words are dropped; "Co-op Staffing" stays as it is.
  - Of several matches, the one with most reports wins.
- **Display:** one row per flagged party under the risk badge: shield icon, "Community flagged — N reports" as the link to `/radar/entity/{slug}`, then the role and the name as the contract writes it. The link has an `aria-label` with the name and count.
- **Failure:** while loading, when nothing is flagged, or when either read fails, nothing is shown and the report is unaffected. A first-load failure is not toasted.

## Files

| File | Change |
|---|---|
| `types/contract.ts`, `services/contractService.ts`, `hooks/useContract.ts` | `ContractParties`, `getContractParties`, `useContractParties` |
| `utils/flaggedParties.ts` (new) | `matchKey`, `findFlaggedParties`, pure |
| `hooks/useRadar.ts` | `useFlaggedParties(contractId)` |
| `components/contract/FlaggedParties.tsx` (new) | The warning rows |
| `components/contract/ReportCard.tsx` | Renders it under the risk badge |
| `i18n/*.json` (6) | `contract.flagged.label`, `.detail`, `.listLabel` (the role names reuse `radar.report.who.types.*`) |
| `utils/flaggedParties.test.ts`, `components/contract/FlaggedParties.test.tsx` (new) | 19 tests |

## Decisions

1. **Suffix-tolerant matching.** A plain slug match would miss even our own sample contract ("Han River Metals Co., Ltd." gives `han-river-metals-co-ltd`; the profile is `han-river-metals-co`). The rule is deliberately looser than the backend's exact slug: a missed warning costs more than a link to the profile of the same business. A different business that differs only by a legal word would also match; that is accepted.
2. **Employer against `employer`, agency against `recruitment_agency`.** A money transfer service or an agency that shares an employer's name never matches.
3. **Warning wording with the name first.** The `aria-label` reads "{name}: community flagged, N worker reports. View details." A test caught that putting the name before a sentence full stop gave "Ltd.. View details."
4. **Read the contract document, not the API.** Same pattern as the report and the progress; no backend change.

## Demo caveat

With the current radar seed and sample contracts:

| Sample contract | Names | Warning |
|---|---|---|
| KR `kr_manufacturing_worker` | Employer Han River Metals Co., Ltd. | Yes: 2 reports |
| AU `au_working_holiday` | Agency Bayanihan Overseas Recruitment Pty Ltd (employer Outback Harvest is not in Radar) | Yes: 5 reports |
| HK `hk_domestic_worker` | Employer Mr. Wong Chi Keung of Lantau Bay Household | **No.** The profile `lantau-bay-household` has one report, so it is not flagged (and the contract text may be extracted as the person, not the household). `manifest.json` lists the slug, but one report is not a pattern |
| SG, MY, JP | Not in Radar | No |

Whether Gemini's `employer_name` for each sample contract matches as above has not been run: that needs a live analysis (NF-P2-008 is waiting for quota). Making HK show would take a second seed report for the invented household, a small data-scripts change left out on purpose.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `tsc -b` | Clean |
| `eslint . --ext ts,tsx --max-warnings 0` | Clean |
| `prettier --end-of-line auto --check .` | Clean |
| `vitest run` | 181 passed. The two `tests/rules` files fail without the Firestore emulator, as before |
| `pnpm run build` | Clean |

**Live browser (Auth and Firestore emulators, `frontend-emulator`)**: signed in with a test phone number and seeded three radar profiles and three completed contracts. Only the upload and analyze HTTP calls were answered by a stub (the backend was not running); the contract document, its report and the profiles were read from the emulator by the real code.

| Contract names | Result |
|---|---|
| Employer "Han River Metals Co., Ltd." (profile: 2 reports, flagged) and agency "Bayanihan Overseas Recruitment Pty Ltd" (5 reports, flagged) | Two warning rows under the risk badge, "Community flagged — 2 reports" and "— 5 reports", each linking to its profile (`/radar/entity/han-river-metals-co`, `/radar/entity/bayanihan-overseas-recruitment`) |
| Employer "Lantau Bay Household" (1 report, not flagged) | Report shown, no warning |
| Employer unknown to Radar | Not run in the browser; covered by a unit test |

Not checked: mobile width, dark theme, the Hindi/other-language strings on screen (all six files are in place), and clicking the link through to the profile (same route as NF-P3-022's badge, which was).

## Manual test steps

1. Start the emulators and the dev server from `frontend/`:
   ```bash
   firebase emulators:start --only auth,firestore --project demo-nomadfinance
   ```
   ```bash
   pnpm dev --mode emulator
   ```
2. Sign in at `http://localhost:5173/sign-in` with a phone number (code at `http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`), finish onboarding.
3. Upload and analyze one of the NF-P3-020 sample contracts with the backend running against the emulator (see `NF-P1-009-frontend-firebase-auth.md`), after loading the radar seed into the emulator:
   ```bash
   FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.radar_seed
   ```
   The KR contract should show the Han River Metals warning once the report appears; the AU one the Bayanihan warning. Without Gemini quota, write a `users/<uid>/contracts/<id>` document with `extracted: {employer_name: "Han River Metals Co., Ltd."}` and a `reports/en` document directly, as the live check did.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A flagged business shows no warning | Compare `extracted` on the contract document with the profile: the names must agree after `matchKey`, and the profile must be `flagged` with the right `entity_type`. Add the contract's spelling to the profile's `aliases` if not |
| Warning shows for the wrong business | Two businesses differ only by a legal word (`Acme` and `Acme Ltd`); they are one profile for this rule |
| No warning although `extracted` has the name | The profile read failed or is still loading, or the contract is older than the detect step's `extracted` field |
| A change to `flagged` takes a minute to appear | `useRadarEntities` caches for 60 s |

## Definition of Done (Frontend Feature)

- [x] Built with Tailwind and existing components (same warning style as the radar entity page)
- [ ] Mobile responsive: the rows wrap by design, not checked at 375 px
- [ ] Slow network: not tested throttled
- [x] Loading and error states: nothing shown, report unaffected
- [x] i18n keys added for all 6 languages
- [ ] Screenshots added to the PR: left for the PR
- [x] Accessibility: a real link with a focus ring and a descriptive `aria-label`, list with a label, icon hidden
