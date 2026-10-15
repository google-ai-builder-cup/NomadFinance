# NF-F0-006 — Feature flag hook and lazy routes for the two new modules

## Summary

The Coach (`/coach`) and the Scam Analyzer (`/scam-check`) now exist in the app but are invisible until the backend says the signed-in user has the flag. With both flags off the navigation, landing page, dashboard and analytics are exactly what v1.0 has, and a worker who types `/coach` lands on the dashboard. Each module is its own lazy chunk and a worker whose flag is off never downloads it. The two pages are placeholders (the "Coming soon" card) until NF-FC-017 and NF-SA-015 replace them.

How it works:

1. `useFeatureFlags()` asks `GET /api/v2/flags` (NF-F0-005) once per signed-in user and keeps the answer for 60 seconds, the same time the backend keeps its own copy.
2. **It fails closed.** Until the first answer arrives, if the call fails, or if the API does not know the route (an older deployment), every module is off. A refetch that fails keeps the last good answer.
3. `<FlagGate flag>` renders its children only when the flag is on, with optional `loading` and `fallback`.
4. `/coach` and `/scam-check` are wrapped in `<FlagRoute flag>`: a skeleton while the answer is on its way, a redirect to `/dashboard` (replacing the history entry, so Back does not return) when it is off, and the page when it is on.
5. The sidebar and the phone tab bar add an entry for each module that is on.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The two modules are in a new `MODULE_ITEMS` list, not in `PILLAR_ITEMS`. | `PILLAR_ITEMS` also feeds the landing page, the dashboard cards, analytics and the router; leaving it at four keeps all of them as v1.0. |
| 2 | Each route is a small module (`pages/coach/CoachRoute.tsx`) that holds its own guard and loads the page with `React.lazy` inside it. | The router fetches a matched route's module before any guard runs, so with the router's own `lazy` a worker whose flag is off would still download the page. Verified in the browser: only the tiny route module is fetched. |
| 3 | The flag answer is keyed by uid. | One account's answer is never shown to the next account that signs in on the same browser. |
| 4 | With six or seven tabs the phone bar shows only the active tab's label, in a wider column; the others are icons and keep their label for screen readers. | Measured at 375 px: with all labels, four of seven were cut off ("Remitt…"). Five tabs (flags off) are unchanged. See D-111. |
| 5 | Only `nav.coach` and `nav.scamCheck` were added to the six language files. The `coach` and `scam` namespaces are NF-F0-013. | Smallest change that satisfies "all user-facing strings through i18n". The wording needs a native speaker (D-113). |
| 6 | No new package. Tests use the repo's existing pattern (vitest, `renderToStaticMarkup`, mocks). | `package.json` is a shared file; the repo has no React Testing Library. |

## Files

| File | Change |
|---|---|
| `frontend/src/types/flags.ts` (new) | `FEATURE_FLAGS`, `FeatureFlag`, `FeatureFlags`, `ALL_FLAGS_OFF` |
| `frontend/src/services/featureFlagService.ts` (new) | `getFeatureFlags()`; `parseFeatureFlags()` turns a module on only for the boolean `true` |
| `frontend/src/hooks/useFeatureFlag.ts` (new) | `useFeatureFlags()`, `useFeatureFlag(flag)` |
| `frontend/src/components/common/FlagGate.tsx`, `FlagRoute.tsx` (new) | The gate and the route guard with its skeleton |
| `frontend/src/pages/coach/CoachRoute.tsx`, `CoachHome.tsx` (new) | `/coach`: guard, and the placeholder page (own chunk) |
| `frontend/src/pages/scam/ScamCheckRoute.tsx`, `ScamCheckHome.tsx` (new) | `/scam-check`: the same |
| `frontend/src/components/layout/navItems.ts` | `MODULE_ITEMS`, `visibleNavItems(flags)` |
| `frontend/src/components/layout/Sidebar.tsx`, `BottomNav.tsx` | Read the flags; the tab bar goes compact from six tabs |
| `frontend/src/components/layout/Header.tsx` | Page title for the two new paths |
| `frontend/src/router.tsx` | Two route entries |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `nav.coach`, `nav.scamCheck` |
| 4 new test files | See below |
| `docs/data-model/firestore-schema.md` | Fixes the invalid `gcloud` command (below) |

No shared file was touched (`package.json`, lock file, `firebase.json`, workflows are unchanged).

## Bundle

Production build, before and after (gzip in brackets):

| | Before | After |
|---|---|---|
| First load (entry JS + CSS) | 634,015 B (194,177) | 635,418 B (194,669): **+1,403 B (+492 gzip), 0.25%** |
| `CoachHome` chunk | none | 481 B, own file |
| `ScamCheckHome` chunk | none | 485 B, own file |

The first-load growth is the two route entries; the guard, the hook and the API call load only when someone opens `/coach` or `/scam-check` or when the app shell opens. It is not byte-identical to v1.0: the new code has to live somewhere. An earlier version that imported the guard from the router grew the entry by 10 KB, which is why each module has its own route module. D-112 records that the service worker still precaches the module chunks.

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `tsc -b` | clean |
| `eslint . --max-warnings 0` | clean |
| `prettier --check` on the changed files | clean (`format:check` on the whole tree fails on Windows because of CRLF, D-21) |
| `vitest run src` | 35 files, 295 tests, all pass (31 new) |
| `vite build` | succeeds; the two modules are their own chunks |

**In a browser** (frontend in emulator mode, backend and Firestore and Auth emulators running locally, a made-up phone number, flags written straight into the emulator):

| Situation | Result |
|---|---|
| Both flags off | Navigation has exactly the v1.0 five; `GET /api/v2/flags` answered 200 |
| `/coach` typed while off | Redirected to `/dashboard`; `CoachRoute` fetched, **`CoachHome` never fetched** |
| `coach` on, `scam` off | `Coach` entry appears and `Scam check` does not; `/coach` shows the page with the title "Coach" in the header; `/scam-check` redirects |
| Both on, 375 px wide | 7 tabs, no sideways scroll, only the active label showing (73 px, not cut off) |
| Backend stopped, both flags still on in Firestore | Flags call failed (500); navigation back to the five, `/coach` redirects: **fails closed** |

Not verified: a real phone (D-111, D-72), the screenshot for the PR (the browser pane timed out drawing the phone-size view), and the deployed Cloud Run API (the live revision may not have `/api/v2/flags` yet; the app treats that as everything off).

## Manual test

Needs Java (emulators) and the backend venv. From the repo root, in three terminals. PowerShell shown; the bash form only differs in how variables are set.

1. Emulators:

```powershell
cd frontend
firebase emulators:start --only firestore,auth --project demo-nomadfinance
```

2. Backend, against the emulators:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"
$env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
$env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m uvicorn app.main:app --port 8080
```

3. Frontend: `cd frontend`, then `node_modules\.bin\vite --mode emulator --host 127.0.0.1` (or `pnpm dev --mode emulator --host 127.0.0.1` where pnpm works). Open `http://127.0.0.1:5173/sign-in`, sign in with any phone number, read the code at `http://127.0.0.1:9099/emulator/v1/projects/demo-nomadfinance/verificationCodes`, and finish onboarding.
4. Flags off: the sidebar has Home, Remittance, Contracts, Radar, Identity. Type `/coach`: you land on `/dashboard`.
5. In the Emulator UI (`http://127.0.0.1:4000/firestore`) create `config/feature_flags` with a map `flags` holding `coach` and `scam`, each a map `{ enabled: true or false, allow_uids: [] }` (shape in `docs/data-model/collections/config.md`). **Wait 60 seconds** (the backend's copy) and reload: the entries for the flags that are on appear and their pages open.
6. Narrow the window to about 375 px: with a flag on the bottom bar shows icons, and the label of the page you are on.

Rollback (stated for the PR): set `enabled` to `false` and clear `allow_uids` in `config/feature_flags`; the entries and routes disappear within a minute, with no deploy. The code itself is inert with the flags off.

## Gaps carried in from NF-F0-004

- **Doc error, fixed here.** `firestore-schema.md` showed `gcloud firestore indexes fields update ... --index=order=ASCENDING,query-scope=COLLECTION_GROUP`. That command cannot work: `--index` accepts only `order` and `array-config`, so a collection-group index cannot be made with `gcloud` at all. The page now says to create it from the file (`firebase deploy --only firestore:indexes`) or in the console, with the warning not to accept index deletions. This is outside NF-F0-006's own scope, so it is best committed separately.
- **Deploy from the file, not done.** The `fieldOverrides` entry was made by hand in production and never deployed from `firestore.indexes.json`, and I have no project access, so it is an action for you (D-114), best on staging first.

## Definition of Done

Feature-flagged module:
- [x] Route and nav entry hidden when the flag is off (flag-off API is NF-F0-005)
- [x] v1.0 behaviour unchanged with the flags off (five tabs, same pages; first load +0.25%)
- [x] Each module is its own lazy chunk
- [x] Rollback path stated: flag off first

Frontend feature:
- [x] Tailwind and the existing shadcn components (skeleton)
- [x] Mobile responsive, measured at 375 px
- [x] Loading state (skeleton), error state (fails closed)
- [x] i18n keys in all six languages (wording to be reviewed, D-113)
- [x] Keyboard and screen reader: real links, skeleton is `role="status"`, hidden tab labels stay readable to screen readers
- [ ] Slow-network run: not done (the placeholder pages have nothing to load)
- [ ] Screenshots in the PR: to add
