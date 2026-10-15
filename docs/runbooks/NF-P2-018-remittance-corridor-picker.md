# NF-P2-018 — Remittance: Corridor + Amount Selector

## Summary

`/remittance` is now the real Remittance X-Ray page instead of "coming soon". A worker picks where they send money and how much, and sees the best way to send it.

- **Corridor dropdown.**
  - The six corridors, with country names in the UI language, e.g. "Australia → Philippines".
  - The worker's own corridor (host → home from the profile) is pre-selected. Otherwise the first corridor from their host country, otherwise Singapore → Philippines.
- **Currency indicator.**
  - Under the dropdown: "You send Australian Dollar (AUD). Your family receives Philippine Peso (PHP)."
  - The amount field shows the sending currency inside it.
- **Amount checks in the browser, translated.** The limits the backend enforces (e.g. A$50 to A$5,000), whole yen only, at most 2 decimals. It reads "1,000", "1.000" (a dot before exactly three digits is thousands), "645.50" and "4 250". A comma is never a decimal point: "645,50" and "5,10" are refused with a message that says to use a dot.
- **Shortcuts** for the two amounts the World Bank surveyed (e.g. A$200 and A$500), where every price is exact rather than estimated.
- **Result.** `POST /api/v1/remittance/compare` (NF-P2-014), then a summary card:
  - the best service and what the family receives
  - how much more than the most expensive service, and the no-fees amount
  - how many services were compared, and the exchange rate used
  - notes when the rate may be out of date or the amount is outside the surveyed ones
  - the survey dates and the World Bank's required attribution
  
  On a phone the card scrolls into view and takes focus. The full table of every service comes in NF-P2-019.
- **Errors in plain words:** no prices for the corridor (404), amount outside the limits (422, names them), offline, server error.
- **Analytics:** `remittance_compared` with the corridor only, never the amount.
- All texts in the 6 languages. No backend change, no new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `frontend/src/types/remittance.ts` (was a stub) | `RemittanceCompareRequest`, `RemittanceComparison` and its parts, for this page and NF-P2-019 |
| `frontend/src/services/remittanceService.ts` (was a stub) | `compareRemittance()` |
| `frontend/src/hooks/useRemittance.ts` (was a stub) | `useCompareRemittance()` (mutation; sends the analytics event on success) |
| `frontend/src/utils/corridors.ts` (new) | `CORRIDORS` (currencies, surveyed amounts, limits, decimals), `defaultCorridor()`, `parseAmount()`, `compareFailure()` |
| `frontend/src/utils/corridors.test.ts` (new) | 42 tests: every corridor against the survey file, pre-selection, 28 amount inputs, money formatting, error messages |
| `frontend/src/services/remittanceService.test.ts` (new) | 2 tests: the request sent, errors passed on |
| `frontend/src/components/remittance/CorridorPicker.tsx` (was a stub) | The form |
| `frontend/src/pages/remittance/RemittanceCompare.tsx` (was a stub) | The page and the summary card |
| `frontend/src/router.tsx` | `/remittance` → `RemittanceCompare` (a map of pillar pages instead of one condition) |
| `frontend/src/utils/format.ts` | `currencyName()`, `formatMoney()` |
| `frontend/src/lib/analytics.ts`, `analytics.test.ts` | `trackRemittanceCompared()` |
| `frontend/src/i18n/{en,hi,tl,id,ne,bn}.json` | `remittance.*` (27 strings) |
| `docs/pipelines/remittance-xray.md`, `docs/runbooks/NF-P1-025-firebase-analytics.md`, `NF-P1-015-worldbank-rpw-parse.md`, `docs/deferred-items.md` | Page and form; the new event; the survey refresh now includes the frontend table; D-46 updated, D-66 new |

## Decisions

1. **The limits live in the frontend, checked against the survey file** (option A, agreed).
   - The backend accepts a quarter of the smaller surveyed amount to ten times the larger one.
   - `CORRIDORS` holds the surveyed amounts. `corridors.test.ts` recomputes currencies, amounts and limits from `data-scripts/data/processed/rpw_corridors.json`, the file the backend's data comes from. A new survey quarter fails the test until the table follows.
   - The alternative, a new backend endpoint, would have been backend work in a frontend task, and one more request before the form works.
   - Frontend CI does not run `src` tests yet (D-46), so today this check runs by hand.
2. **Amounts are typed as text, not `type="number"`.** A number field ignores "1,000", changes with the mouse wheel, and accepts "1e3".
   - The parser accepts both grouping styles: a dot followed by exactly 3 digits is a thousands separator, so "1.530" is 1,530, the Indonesian style.
   - For the yen every separator groups thousands.
   - The keyboard is `decimal`, or `numeric` for the yen.
3. **A new sending currency clears the amount** (645 SGD means nothing in yen). The same currency keeps it (SG-PH ↔ SG-IN).
4. **The 422 message is the frontend's own,** with the limits formatted in the UI language. The backend's `detail` is English only (D-10).
5. **The survey amounts are shortcuts, the placeholder is the larger one.** Those are the only amounts where every service's price is exact; other amounts are interpolated or estimated (the card says so).
6. **The amount is never sent to analytics or put in the URL.** It is the worker's own money. The URL stays `/remittance`.
7. **The result scrolls into view and takes focus.** On a phone the card is below the form; without this, a worker taps "Compare" and sees nothing change. Smooth scrolling only without "reduce motion".
8. **The attribution stays in English** (`lang="en"`, linked). It is the World Bank's required wording.

## Flow

```
/remittance
  profile (host, home) → defaultCorridor → form
  worker: corridor → currencies shown, shortcuts, limits
          amount → parseAmount (empty / invalid / decimals / tooSmall / tooLarge → message under the field)
  submit → useCompareRemittance → POST /api/v1/remittance/compare {corridor_id, amount}
           200 → remittance_compared {corridor_id} → summary card (scrolled into view, focused)
           404 → "Prices for this corridor aren't available yet"
           422 → "We can't compare this amount. Enter an amount between … and …"
           other → offline / server / too many requests (app-wide messages)
```

## All commands, in order

### 1. Checks (from `frontend/`; `pnpm.cmd` in PowerShell if `pnpm` is blocked)

```bash
pnpm install --frozen-lockfile
pnpm exec tsc -b
pnpm lint
pnpm exec prettier --check src
pnpm exec vitest run src
pnpm build
```

On Windows with CRLF checkouts: `pnpm exec prettier --check --end-of-line auto src`.

### 2. Try it on the emulators

Terminal 1, from `frontend/`:

```bash
firebase emulators:start --only auth,firestore --project demo-nomadfinance
```

Terminal 2, load the corridors **into the emulator**, from `data-scripts/` (Git Bash):

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance python -m src.loaders.corridors
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m src.loaders.corridors
```

Without a cached live rate the comparison uses the survey's rate and the card says it may be out of date. That's fine for trying the form. For live rates, run the cron once against the emulator (NF-P1-019 runbook).

Terminal 3, the API against the emulators, from `backend/`:

```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 FIREBASE_PROJECT_ID=demo-nomadfinance GCLOUD_PROJECT=demo-nomadfinance uvicorn app.main:app --port 8080
```

PowerShell:

```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_AUTH_EMULATOR_HOST = "127.0.0.1:9099"
$env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GCLOUD_PROJECT = "demo-nomadfinance"
uvicorn app.main:app --port 8080
```

Terminal 4, from `frontend/`:

```bash
pnpm dev --mode emulator
```

Open **http://localhost:5173** (not `127.0.0.1`), sign in with any phone number (the code is in Terminal 1), and onboard as a worker in Australia sending to the Philippines. Then open **Remittance** in the navigation.

**What to look for:**
1. Australia → Philippines is selected; "You send Australian Dollar (AUD). Your family receives Philippine Peso (PHP)."; hint "between A$50 and A$5,000"; shortcuts A$200 / A$500.
2. Compare with nothing typed → "Enter the amount you want to send." Type 20 → "Enter at least A$50." The field turns red and a screen reader reads the message.
3. Type `1,000` → Compare → the summary card: best service, "Your family receives", services compared, the estimate note (above A$500), survey dates, attribution link.
4. Switch to Australia → India: the amount stays. Switch to Japan → Philippines: it clears; the shortcuts become ¥17,000 / ¥42,000; `17000.5` → "Enter a whole number of JPY".
5. Switch the language to हिन्दी: countries, currencies, amounts and dates change language.
6. DevTools → phone size (375 px): no sideways scrolling. After Compare, the page scrolls to the card.
7. Keyboard only: Tab to the dropdown, arrow keys change it, Tab to the amount, type, Enter.
8. 404: delete `corridors/MY-ID` in the Emulator UI (http://localhost:4000), compare Malaysia → Indonesia → "Prices for this corridor aren't available yet". Run the loader again afterwards.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `tsc -b`, `pnpm lint` (max warnings 0), `prettier --check` | Pass |
| `vitest run src` | 100 passed (7 files; 44 new) |
| `pnpm build` | Pass |
| A test can fail | The survey check compares each of the 6 corridors with the file; a wrong amount fails that corridor's test |

**Live, in the browser, on the emulators** (6 corridors loaded, live ECB rates from a local cron run):
- **Pre-selection.** Australia → Philippines picked from the profile, with its currencies, limits A$50–A$5,000 and shortcuts A$200 / A$500.
- **Validation, real clicks and typing.**
  - Empty → "Enter the amount you want to send."
  - 20 → "Enter at least A$50.", with `aria-invalid` and `aria-describedby` set.
  - Yen: `17000.5` → whole-number message; `999999` → "Enter at most ¥420,000".
- **Comparisons.**
  - `1,000` AUD → AU-PH: 32 services, MoneyGram best, ₱44,615.20, estimate note, survey 5–20 Feb 2025, attribution.
  - ¥42,000 (shortcut, `aria-pressed`) → JP-PH: 40 services, Wise best, ₱16,492.98, no estimate note.
- **Corridor switches.** Same currency keeps the amount; a new currency clears it.
- **Errors and stale rate.**
  - MY-ID deleted from the emulator → 404 message, old result hidden.
  - SGD_PHP rate removed → survey rate 43.299331 and the "may be out of date" note.
- **Hindi, at 375 px.** Countries, currencies, amounts (JP¥, PHP) and dates in Hindi; page width 375, no sideways scroll (screenshots).
- **Keyboard only.** Tab → dropdown, ArrowUp → Japan → Philippines, Tab → amount, "300" + Enter → Hindi "at least ¥4,250" message. Then "20000" + Enter → the card scrolled into view and its title had focus.

**Found and fixed during the live test:**
- **Money formatting.** "₱44,615.2" now shows "₱44,615.20".
- **Result on a phone.** It appeared below the fold with no sign of it; it now scrolls into view and takes focus.

**Not run:** DevTools "Slow 3G". The comparison answers in well under a second locally, and the button says "Comparing…" while it waits.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Prices for this corridor aren't available yet" | `corridors/{id}` is not loaded in that Firestore: run the corridor loader (step 2) |
| "We can't compare this amount" although the form accepted it | The frontend table and the backend's survey data differ: run `pnpm exec vitest run src/utils/corridors.test.ts` and update `CORRIDORS` |
| Card says the rate may be out of date | No `rates_cache/{pair}` or older than 6 hours: the cron has not run (NF-P1-019) |
| A service's family amount is above the "no fees" amount | The survey recorded a better-than-market rate for it (D-66) |
| `/remittance` still shows "coming soon" | An old build or service worker: reload twice (D-42) |
| "Our server had a problem" | The API is down or `VITE_API_BASE_URL` is wrong (deployed site) |

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind + shadcn/ui (`Button`, the app's field style)
- [x] Fully mobile responsive (375 px; touch-sized shortcuts; result scrolls into view)
- [ ] Works on slow network (throttled 3G in DevTools): not run; the button shows "Comparing…" and locks the form while waiting
- [x] Loading states: profile spinner, "Comparing…" button
- [x] Error states: amount checks, 404, 422, offline, server, too many requests
- [x] i18n keys for all user-facing strings (6 languages); the World Bank attribution stays in its required English
- [ ] Screenshots added to PR: take them when opening the PR (form, result, Hindi at phone width)
- [x] Accessibility: labels, `aria-invalid` and `aria-describedby`, `role="alert"` errors, `aria-pressed` shortcuts, keyboard only, focus moved to the result

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Aditya (NF-P2-019, table):**
  - `compare.data` in `RemittanceCompare.tsx` is the `RemittanceComparison`; the TODO marks where the table goes.
  - `types/remittance.ts` has every field.
  - `formatMoney()` and `CORRIDORS[id].decimals` / `receiveDecimals` format amounts consistently.
  - Key rows by `rpw_id`. Mind D-66 (better-than-market services).
- **Pranjal (NF-P2-020, trend chart):** the page is the place for it; `compare.variables.corridor_id` is the corridor last compared.
- **Pranjal (D-46):** with the OK on the shared-file diff, a `vitest run src` step in frontend CI would make the survey check automatic.
- **Survey refresh (NF-P1-015 runbook, step 6):** update `frontend/src/utils/corridors.ts` if the surveyed amounts change.

## Commit and PR for this task

Branch: `feature/remittance-corridor-picker` (already checked out).

```bash
git add frontend/src docs
git status
```

```bash
git commit -m "feat(remittance): add corridor and amount selector with result summary" -m "Refs: NF-P2-018"
```

PR title: `feat(remittance): corridor and amount selector with comparison summary (NF-P2-018)`

## Not covered here

- The table of every service, sorting, savings highlight (NF-P2-019)
- The trend chart and best day (NF-P2-020), the recommendation (NF-P2-016), logging a transfer (NF-P2-017)
- Running the `src` unit tests in CI (D-46)
