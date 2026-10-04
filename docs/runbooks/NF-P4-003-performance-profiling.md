# NF-P4-003 — Performance profiling

## Summary

The app was measured on three fronts (Lighthouse and a throttled phone, Firestore reads, Gemini and API latency), and the worst problems found on the way were fixed.

**Where the time was going, and what changed:**

| Area | Finding | Done |
|---|---|---|
| Page load | Every visitor downloaded one 1.6 MB file (470 KB compressed) containing the whole app, including the map, push messaging and all six languages. On Slow 3G the screen was blank for 10.4 s. | The file is now 0.5 MB (161 KB compressed). Pages, the Firestore SDK, the map and the other five languages load on demand. A loading screen in `index.html` paints in about 1 s. |
| Sign-in start | Firebase Auth loaded Google's `apis.google.com` scripts at start-up and held back the signed-in/signed-out decision until they arrived (several round trips, 40 KB). | Auth no longer loads them at start. The Google sign-in calls load them when used. |
| Firestore reads | The dashboard read **every** notification (60 documents in the test data) to show two. Identity re-read a year of entries on every tab switch. | Dashboard: 62 → 5 reads, constant. Alerts page capped at 50. Identity and radar profiles are kept for 5 minutes. |
| Backend reads | Every contract analysis read all 15 labor-law rule documents. | Read once per law version per server instance. |
| Gemini latency | Slow calls are slow because of **thinking tokens** (84 to 89% of what the reasoning model generates). | Measured and written up. No quality-affecting change made (your decision). |
| API cold starts | The first request on each Cloud Run instance takes **8.4 s** (median over 165 instances). | Measured. Fix needs a deploy setting, so it is a decision for you (D-77). |

**Everything was measured on the local emulators and a local production build**, except the two public pages, which were also measured live. The numbers are real measurements of a real build, not of the deployed site, so re-run Lighthouse on the live site after deploying (commands below).

## Results

### Lighthouse (mobile preset: Moto G-class phone, simulated slow 4G)

Local production build served with Hosting-style compression and cache headers, signed-in pages with a signed-in profile. Before = start of this task. After = the final build.

| Page | Performance before → after | First paint | Largest paint | Blocking time | Layout shift |
|---|---|---|---|---|---|
| Landing | 75 → **98** | 3.3 → 1.7 s | 4.9 → 2.1 s | 94 → 11 ms | 0 |
| Sign-in | 83 → **99** | 3.3 → 1.7 s | 3.5 → 1.8 s | 100 → 4 ms | 0 |
| Dashboard | 83 → **91** | 3.3 → 1.7 s | 3.5 → 3.4 s | 113 → 47 ms | 0 → 0.051 |
| Remittance | 84 → **91** | 3.3 → 1.7 s | 3.5 → 3.4 s | 35 → 22 ms | 0 |
| Contract | 84 → **90** | 3.3 → 1.7 s | 3.5 → 3.5 s | 58 → 38 ms | 0 |
| Radar | 72 → **79** | 3.3 → 1.7 s | 5.2 → 5.1 s | 90 → 74 ms | 0.079 |
| Identity | 73 → **82** | 3.3 → 1.7 s | 5.2 → 4.6 s | 96 → 70 ms | 0.059 |

Accessibility, best practices and SEO are 100 on every page except Radar (best practices 96, see below). Desktop was 97 to 100 before and after, so it was not the problem.

**The live site, before the changes** (read-only, no sign-in): landing mobile **77**, sign-in mobile **81**, both desktop **100**. The local build gave 75 and 83 for the same pages, so the local numbers are a fair stand-in.

What is left, honestly:

- **Radar 79.** The largest paint is a map picture tile from `tile.openstreetmap.org` (a third party), and the map code (Leaflet) is itself 62 KB compressed. Best practices 96 is those tiles being served at a lower resolution than the screen. Not changed.
- **Identity 82.** It waits for the charts library (103 KB compressed, already on demand) and a year of entries.
- **Dashboard layout shift 0.051** is the alerts card growing when its data arrives. The test worker now has 60 alerts, the baseline run had none, so the two runs are not like for like. Still in Lighthouse's "good" range (under 0.1).
- The dashboard "largest paint" in these local runs is the Firebase emulator warning banner. The deployed site has none.

### Slow 3G on a phone profile (400 kbit/s, 400 ms delay)

Same script and test worker as the NF-P4-002 run; "usable" means the page's real content is on screen and no spinner is left.

| Page | First paint | Usable | Downloaded |
|---|---|---|---|
| Landing | 10.5 → **1.2 s** | 12.3 → **4.3 s** | 527 → 169 KB |
| Sign-in | 10.4 → **1.2 s** | 12.2 → **4.3 s** | 527 → 169 KB |
| Dashboard | 10.4 → **1.2 s** | 13.6 → **9.2 s** | 529 → 328 KB |
| Remittance | 10.5 → **1.2 s** | 13.7 → **9.4 s** | 528 → 336 KB |
| Contract upload | 10.4 → **1.2 s** | 13.6 → **9.7 s** | 528 → 345 KB |
| Radar map | 10.4 → **1.2 s** | 14.3 → **11.2 s** | 571 → 440 KB |
| Identity | 10.4 → **1.2 s** | 14.5 → **10.0 s** | 529 → 327 KB |
| Profile | 10.5 → **1.2 s** | 13.7 → **9.0 s** | 528 → 323 KB |
| Dashboard, second visit | 2.1 → **1.5 s** | | 9.6 → **1 KB** |

On Fast 3G the dashboard is usable in 2.8 s (4.1 s before). On a fast connection it is 0.2 s.

**Read this table fairly:** the blank screen is gone and public pages open in about 4 s, but a signed-in page still needs about 9 s to show its content on Slow 3G. The floor is the data: 328 KB at 400 kbit/s is 6.4 s before any delays. Going lower means shipping less, which is the Firestore SDK (132 KB compressed) and Firebase Auth (about 85 KB uncompressed, in the first download), both needed to show a signed-in page.

Remittance compare and the offline message are unchanged (1.2 s with signal, clear message without, 1.4 s after signal returns).

### The first download

| File | Before | After |
|---|---|---|
| Entry file, uncompressed | 1,610 KB | **501 KB** |
| Entry file, compressed | 470 KB | **161 KB** |
| Firestore SDK | inside the entry file | own file, 132 KB compressed, loaded after sign-in |
| Map (Leaflet) | inside the entry file | 62 KB compressed, only on the radar screens |
| Languages | all six (324 KB uncompressed) | English only; each other language is 10 to 13 KB compressed, fetched when chosen |
| Pages | all in the entry file | 17 separate files of 1 to 15 KB compressed each |
| Offline download (service worker) | 84 files, 2.29 MB | 73 files, 2.06 MB (0.89 → about 0.64 MB compressed) |

What remains in the entry file is the framework: React (26%), Firebase Auth (18%), the app's own code and English text (12%), the router (10%), i18next (9%).

### Firestore reads (documents returned, on the emulator with 9 radar profiles, 60 alerts, a year of entries)

| Screen, cold load | Before | After | Note |
|---|---|---|---|
| Dashboard | 62 | **5** | Was 60 alerts + profile + contract. Now 2 alerts + 1 count + profile + contract. Constant, no longer grows with the number of alerts. |
| Alerts page | 61 | **53** | Capped at the newest 50, so it stops growing. |
| Radar map | 10 | 10 | 9 profiles. Grows with the number of profiles; see D-84. |
| Identity | 25 | 25 | 24 entries. Grows with how often a worker logs; see "Not changed". |
| Remittance, Contract, Profile | 1 | 1 | Profile only. |

Reads that were re-done too often, now kept longer: Identity entries (1 → 5 minutes; this device's own logs still refresh it at once) and radar profiles (1 → 5 minutes). The old settings re-read them on every tab switch back after one minute.

How the count was made: a throw-away copy of the app (outside the repo) replaced the Firestore SDK with a wrapper that records every document returned, then a browser visited each screen. The count query is billed as at least one read.

The backend, read from the code:

| Where | Reads | Change |
|---|---|---|
| Contract analysis and comparison, labor-law rules | 15 rules + 1 version, every time | 1 version read; the 15 rules are kept per country until the version changes |
| Verified income from a contract (`contract_to_fib`) | all income entries, to find one month | not changed (D-80) |
| Bill categorising (`categorizer`) | all bills and savings, to find the uncategorised | not changed (D-80) |
| Weekly profile job | all entries of every user | not changed; it is a weekly batch |

### Gemini latency (98 successful calls in production, 2026-09-29 to 10-04)

Only successful calls are logged, so a call that failed on every attempt is not in these numbers.

| Operation | Model | n | Median | Slowest 5% | Reads | Writes | Thinking |
|---|---|---|---|---|---|---|---|
| contract.compare | 3.5 Flash | 7 | **34.7 s** | 54.6 s | 5,644 tokens | 826 | **4,299** |
| fib.synthesize_narrative | 3.5 Flash | 14 | **14.8 s** | 22.4 s | 755 | 335 | **2,680** |
| contract.translate | 3.1 Flash-Lite | 9 | 9.8 s | 21.0 s | 2,121 | 2,251 | 0 |
| remittance.recommend | 3.1 Flash-Lite | 2 | 2.8 s | 10.1 s | 3,072 | 118 | 0 |
| radar.alert_notification | 3.1 Flash-Lite | 11 | 4.2 s | 16.4 s | 326 | 46 | 0 |
| contract.extract | 3.5 Flash-Lite | 10 | 3.8 s | 6.6 s | 1,342 | 1,039 | 0 |
| fib.categorize | 3.1 Flash-Lite | 1 | 3.4 s | | 303 | 100 | 0 |
| radar.validate | 3.1 Flash-Lite | 9 | 3.2 s | 5.1 s | 374 | 50 | 0 |
| radar.categorize | 3.1 Flash-Lite | 8 | 3.1 s | 3.9 s | 424 | 49 | 0 |
| fib.extract_bill | 3.5 Flash-Lite | 2 | 2.2 s | 2.5 s | 1,428 | 87 | 0 |
| contract.detect | 3.5 Flash-Lite | 8 | 1.3 s | 2.5 s | 959 | 116 | 0 |
| radar.extract_entity | 3.5 Flash-Lite | 9 | 1.1 s | 31.7 s | 547 | 74 | 0 |

(Medians. "Reads" is the prompt, "Writes" the answer.)

What the numbers say:

1. **Time follows tokens generated, about 5 ms each, and thinking is most of them.** Comparison: 4,299 of 5,125 generated tokens are thinking (84%); narrative: 2,680 of 3,015 (89%). No call sets a thinking budget, so the model decides.
2. **A retry costs far more than a normal call.** 89 calls with one attempt: median 3.4 s. 9 calls with more than one attempt: median 22.4 s.
3. **The 31.7 s `radar.extract_entity` is one call that took 2 attempts, which matches the 30 s timeout expiring once** and the second attempt succeeding. All the other calls of that kind took 1.1 to 1.4 s.
4. **Why retries happen:** 16 times a 429 "quota exceeded" on 3.5 Flash, and 15 times a 503 "high demand" (6 on 3.5 Flash, 5 on 3.1 Flash-Lite, 4 on 3.5 Flash-Lite). The 429s are the key's own limit, not a bug.
5. **Translation is output-bound** (2,251 tokens out, no thinking): about 10 s is simply how long it takes to write a translated report.

### API and cold starts (Cloud Run request log, 2026-09-24 to 10-04, 717 requests)

| Endpoint | n | Median | Slowest 5% |
|---|---|---|---|
| remittance/compare | 31 | 0.45 s | 0.89 s |
| remittance/trends | 38 | 0.39 s | 1.33 s |
| remittance/savings | 21 | 0.74 s | 2.21 s |
| radar/entities/{slug}/reports | 21 | 0.37 s | 0.44 s |
| fib/income, bill, savings | 9 | 0.35 to 0.37 s | 0.4 s |
| fib/report/export (create) | 3 | 3.6 s | 4.3 s |
| contracts (upload) | 17 | 4.3 s | 7.1 s |
| contracts/{id}/analyze | 15 | 4.5 s | 58 s (Gemini) |
| contracts/{id}/reports/{lang} | 4 | 14.5 s | 15.5 s (Gemini) |
| radar/report | 9 | 8.9 s | 36.6 s (Gemini) |

**Cold starts are the largest delay a worker can hit.** The first request on each of 165 instances took **8.4 s** at the median, against 2 ms for later requests to the same instance. The service scales to zero (`min-instances` is not set, 1 CPU, 512 MiB, startup CPU boost already on), and the scheduled rate refresh (110 runs in these 10 days) keeps starting fresh ones. Importing the app takes 1.7 s on this PC; the rest (container start, first-use setup on Cloud Run's 1 CPU) was not measured separately. Loading the code on demand would not help much: it is spread across FastAPI (0.5 s), the Gemini client (0.35 s), Firebase (0.2 s), and the other libraries every request uses.

Not user-facing, but worth knowing: `internal/refresh-rates` takes 10 s per run (110 runs); `aggregate-radar` 10 s. 34 responses in the log were 500 (radar entity reports and report export on 2026-10-01, `/docs` on 09-25); the most recent 500 in this log is from 2026-10-01. Their cause was not investigated here.

## What was changed

| Change | Why | Where |
|---|---|---|
| Pages load on demand; a progress bar shows while the next page downloads | The one 1.6 MB file | `router.tsx`, `components/layout/NavigationProgress.tsx`, `components/common/RouteLoading.tsx`, `AppShell.tsx` |
| Firestore in its own module; the profile-based language switch only runs when signed in | Signed-out pages no longer need the Firestore SDK | `lib/firestore.ts` (new), `lib/firebase.ts`, 5 services, `LanguageSync.tsx`, `ProfileLanguageSync.tsx` (new) |
| Only English ships up front; other languages fetched on first use; falls back to English if the fetch fails | 287 KB of text nobody needs together | `lib/i18n.ts`, and the 4 places that switch language (`LanguageSync`, `LanguageSelector`, `DetailsForm`, `Onboarding`) |
| Loading screen in `index.html` | The screen was blank for 10 s | `index.html` |
| Firebase Auth started without the popup/redirect resolver; resolver passed to the Google calls | Google scripts loaded at start-up delayed everything | `lib/firebase.ts`, `services/authService.ts` |
| Service worker registers after the page has loaded and the browser is idle; iOS launch images no longer precached | It competed with the page for bandwidth, and 11 launch images (0.25 MB) were downloaded for a phone that uses one | `main.tsx`, `vite.config.ts` |
| Notifications: newest 50 only; dashboard asks for 2 plus an unread count | 60 reads for 2 rows | `notificationService.ts`, `hooks/useNotifications.ts`, `RadarAlertsWidget.tsx` |
| Identity entries and radar profiles kept 5 minutes | Re-read on every tab switch | `hooks/useFIB.ts`, `hooks/useRadar.ts` |
| Labor-law rules kept per country until the version changes | 16 reads per analysis | `repositories/labor_law_repo.py`, `services/contract/rag.py` |

## Decisions

1. **Landing and sign-in stay in the first download.** They are what a new visitor opens; loading them separately would add a round trip in front of the first screen.
2. **Pages use React Router's own `lazy`, not `React.lazy`.** The router fetches every matched route's file in parallel (a deep link would otherwise wait through a chain of downloads: shell, then page), and it gives a "loading" state to drive the progress bar.
3. **Language fetch failure falls back to English silently.** The alternative was showing raw keys. The files are precached after the first visit, so this only happens on a first visit with no signal.
4. **The unread count uses a Firestore count query** (billed about one read per 1,000 matches) instead of reading the feed. If the count fails, only the "N new" line is hidden. The alerts still show.
5. **The alerts page lists the newest 50.** A worker with more than 50 alerts no longer sees the oldest. Alerts are short-lived (they expire), so this was judged better than an unbounded read; say if you want paging instead.
6. **The Google redirect result is read only when this tab sent the person to Google** (a flag in session storage). Reading it always would load the Google scripts on every sign-in page visit.
7. **The labor-law cache is checked against the version on every call** (one cheap read), so a reload of the law data is picked up at once, never served stale.
8. **No Gemini setting was changed.** See the recommendations.

## Recommendations (your decision)

These are not done because each has a cost or a quality trade-off.

1. **Cold starts (D-77): set `--min-instances 1` on the Cloud Run service.** Removes the 8.4 s first request. Costs money while idle (it is billed all day, unlike now); check the Cloud Run pricing page for an instance of 1 CPU and 512 MiB. The deploy flag lives in `backend-deploy.yml` or a `gcloud` command (shared file: I will show the exact diff first). For the demo day alone, running the one command by hand and undoing it afterwards is the cheapest option.
2. **Thinking budget for the two reasoning calls (D-78).** Cap `thinking_budget` for `contract.compare` and `fib.synthesize_narrative`. Expected effect, from the token counts: if thinking dropped to a quarter, comparison would go from about 35 s to about 13 s and the narrative from about 15 s to about 5 s. **That is an estimate, not a test**; a lower budget can make the comparison less careful. Test it on the same 3 contracts before and after and compare the clause scores. This needs a small change in `integrations/gemini/client.py` (a `thinking_config` option), which I can add when you decide.
3. **Shorter timeouts for the quick calls (D-79).** Light operations (`radar.*`, `contract.detect`, `fib.categorize`) finish in under 7 s, but all have the 30 s default, so one stuck call costs 30 s (that was the 31.7 s above). A 10 s timeout for them would cut that tail to about 12 s. One of the 11 `radar.alert_notification` calls was a real 16 s success, so 10 s would have retried it: choose 15 s there.
4. **Quota (16 × 429).** The 429s are the Gemini key's own limit. Enabling billing on the Gemini project removes them; out of scope here.

## Files

| File | What |
|---|---|
| `frontend/index.html` | Loading screen |
| `frontend/vite.config.ts` | Launch images no longer precached |
| `frontend/src/main.tsx` | Service worker registers when idle |
| `frontend/src/router.tsx` | Pages on demand |
| `frontend/src/lib/firebase.ts`, `firestore.ts` (new) | Auth without the resolver; Firestore in its own module |
| `frontend/src/lib/i18n.ts`, `i18n.test.ts` (new) | Language on demand, with tests (switch, back to English, failed fetch) |
| `frontend/src/services/authService.ts` | Resolver passed to Google calls; redirect result read only when pending |
| `frontend/src/services/{contract,fib,notification,radar,user}Service.ts` | Import `db` from `lib/firestore` (notification: limit + count) |
| `frontend/src/hooks/useNotifications.ts`, `useFIB.ts`, `useRadar.ts` | Bounded list, unread count, cache times |
| `frontend/src/components/common/LanguageSync.tsx`, `ProfileLanguageSync.tsx` (new), `RouteLoading.tsx` (new) | Split language sync; loading view |
| `frontend/src/components/layout/AppShell.tsx`, `NavigationProgress.tsx` (new), `LanguageSelector.tsx` | Progress bar; use the new language call |
| `frontend/src/components/dashboard/RadarAlertsWidget.tsx`, `.test.tsx` (new) | 2 rows plus a count, with tests |
| `frontend/src/components/profile/DetailsForm.tsx`, `src/pages/Onboarding.tsx` | Use the new language call |
| `backend/app/repositories/labor_law_repo.py`, `backend/app/services/contract/rag.py` | Rules kept per version |
| `backend/tests/unit/repositories/test_labor_law_repo_cache.py` (new) | 5 tests |
| 5 backend test fakes | `get_rules` takes the version |

No shared file (`package.json`, lock files, `firebase.json`, rules, Dockerfile, `tsconfig*`, workflows) was edited.

## All commands, in order

### 1. Checks (from `frontend/`; `pnpm.cmd` in PowerShell if `pnpm` is blocked)

```bash
pnpm exec tsc --noEmit
pnpm exec eslint src
pnpm exec prettier --check --end-of-line auto src index.html vite.config.ts
pnpm exec vitest run src
pnpm exec vite build --mode emulator
```

`pnpm exec vitest run` without `src` also runs `tests/rules`, which fail unless started through `firebase emulators:exec` (they need the emulator; unrelated to this task).

From `backend/`:

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m black --check -l 100 app tests
.venv/Scripts/python.exe -m ruff check app tests
.venv/Scripts/python.exe -m mypy --strict app/services app/repositories/labor_law_repo.py
```

### 2. Lighthouse on the live public pages (any folder; nothing is installed in the repo)

```bash
npx lighthouse https://nomadfinance-prod.web.app/ --only-categories=performance --form-factor=mobile --quiet --chrome-flags="--headless=new"
npx lighthouse https://nomadfinance-prod.web.app/sign-in --only-categories=performance --form-factor=mobile --quiet --chrome-flags="--headless=new"
```

Add `--preset=desktop` for desktop. Use the same command after deploying and compare with the table above (landing 77, sign-in 81 mobile before).

### 3. Lighthouse on a signed-in page

Lighthouse starts a clean browser, so signed-in pages need a profile that is already signed in. The runs above used a small script (working folder, not in the repo) that signs the test worker in on the emulators into a Chrome profile folder, then points Lighthouse's `chrome-launcher` at that folder with `disableStorageReset`. That script is not saved in the repo (D-74 covers the same question for the NF-P4-002 harness).

### 4. Try the changes by hand (emulators running; see the NF-P1-001 runbook)

1. Open the app in Chrome, DevTools → Network → Slow 3G, hard reload. The logo and "NomadFinance" appear at once; the sign-in page is usable in about 4 s.
2. Sign in, switch the language to Hindi in the header: the strings change after a short fetch. In DevTools → Network you will see `hi-….js` load once.
3. Dashboard: in DevTools → Network, filter `firestore`, count the requests; or watch the emulator UI. The alerts card makes two requests, not one per alert.
4. Tap a menu item on Slow 3G: a thin bar pulses at the top until the page arrives.

## Verified results (2026-10-04)

- Frontend: tsc, eslint and prettier clean; **206 tests pass** (24 files; 14 new across `i18n.test.ts`, `queryClient.test.ts`, `RadarAlertsWidget.test.tsx`); production build passes. The widget test was checked by reverting the change: the "asks for two alerts" test then fails.
- Backend: **960 tests pass**, 66 skipped (they need the emulator or a live key); black, ruff and `mypy --strict` clean. The labor-law repository test passes against the Firestore emulator.
- Sign-in on the Auth emulator, on the final build: **phone code** signs in and survives a reload; **Google popup** completes; **Google redirect fallback** (popup blocked) completes through the pending flag. No `apis.google.com` request on the sign-in page before tapping.
- Not run: the Google sign-in **re-check** on the profile page (it uses `reauthenticateWithPopup`, which now passes the resolver; same pattern as the popup that was run), real phones (D-72).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| A page shows the bar for a long time, then an error page | A page file could not be fetched, e.g. an old tab after a deploy replaced the files | Reload the page (the error page has a reload button) |
| Language switches to nothing / stays English on a first visit offline | The language file was never cached | Open the app once with signal; the files are then precached |
| "N new alerts" line missing on the dashboard | The count query failed (offline, or rules); the alerts still show | Reload when online |
| Test run reports 2 failed files in `tests/rules` | They need the emulators started by `firebase emulators:exec` | Run them through the existing rules test script |
| Lighthouse says "Missing source maps" | The production build has no source maps by design | Ignore; it is not scored in the best-practices category |

## Definition of Done (Frontend Feature, plus Bug Fix for the offline change)

- [x] Tailwind and shadcn/ui only (one new bar, Tailwind classes)
- [x] Mobile responsive: the loading screen and bar are fluid; no layout changed
- [x] Works on slow network: measured on Slow 3G and Fast 3G, before and after (tables above)
- [x] Loading states visible: loading screen in the HTML, a spinner for the first page, a progress bar between pages
- [x] Error states handled: failed language fetch falls back to English; failed count hides one line
- [x] i18n: no new strings (the bar reuses `common.loading`)
- [ ] Screenshots in the PR: yours to add (Lighthouse reports before/after, the loading screen)
- [x] Accessibility: the bar and the loading screen have `role` and a label; no keyboard changes

## For teammates

- **Nobody** needs a new package or a `.env.local` change.
- **Anyone adding a page:** add it in `router.tsx` with `page(() => import("@/pages/..."))`, not a static import, or it goes back into the first download.
- **Anyone importing `db`:** import it from `@/lib/firestore`, not `@/lib/firebase`. `firebase.ts` now only has `auth` and `firebaseApp`, so a signed-out page does not pull in Firestore.
- **Anyone switching the language:** call `setLanguage(code)` from `@/lib/i18n`, not `i18n.changeLanguage(code)`; the second fails to find the strings for any language that has not been loaded yet.
- **Anyone using Google sign-in calls:** pass `browserPopupRedirectResolver` as the last argument (see `authService.ts`).
- **Aditya:** add "Google sign-in, popup and redirect, on iPhone Safari" to the D-72 checklist; the redirect path is the one real devices use when a popup is blocked.

## Commit and PR

Branch: `fix/performance` (already checked out). The NF-P4-002 Slow-3G follow-up (offline fix) is also uncommitted here; commit it first as its own commit.

```bash
git add frontend/src/lib/queryClient.ts frontend/src/lib/queryClient.test.ts docs/runbooks/NF-P4-002-cross-browser-testing.md
git commit -m "fix(frontend): run requests while offline instead of waiting silently" -m "Refs: NF-P4-002"
```

Then this task:

```bash
git add frontend backend docs
git status
git commit -m "perf(platform): split the bundle, bound Firestore reads, cache labor law" -m "Refs: NF-P4-003"
```

PR title: `perf(platform): load pages on demand, bound Firestore reads, profile Gemini and API latency (NF-P4-003)`

## Not covered here

- Real-phone timings (D-72), load with many users at once, a paid Gemini quota
- Moving the language files, charts and map out of the offline download (D-81)
- Hosting headers and compression (already set in `firebase.json`; Firebase compresses)
- A Lighthouse step in CI (it needs a shared-file change; D-74 is the same question)
