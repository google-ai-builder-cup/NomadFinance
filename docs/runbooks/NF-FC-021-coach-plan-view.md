# NF-FC-021 — Coach 90-day plan view, PDF download and share

## Summary

A worker who has made their plan can now **open it**: a page with the plan's summary, the warnings most serious first, the monthly budget as cards, the money to send home (with a link into Remittance X-Ray), debt and emergency savings, the 13 weeks one after the other, the checklist they can tick, and the PDF to **download or share**. It works at 360 px with no sideways scroll.

| Part | What it does |
|---|---|
| **The page** `/coach/plan/:planId` | Behind the `coach` flag like `/coach` (a worker the flag is off for goes to the dashboard and downloads nothing of it). Reads `GET /api/v2/coach/plans/{id}?language=` in the app's language |
| **The way in** | A "View my plan" button on the score screen once the plan is made, and a "Your 90-day plan is ready" card on the Coach page, from `GET /overview` (shown also while a new interview is under way; if the read fails the page is as it was) |
| **Language** | The plan follows the app's language. A language the plan is not stored in is translated by the server on that first request, so the plan already on screen stays, dimmed, with "Translating your plan…" until the new one arrives |
| **Warnings** | Urgent first, then warning, then note; the severity is a word and an icon as well as a colour |
| **Budget, debt, savings** | Cards for income, costs, what is set aside, what is left (or "Short each month by" with a help line when it is negative), the first month's one-off costs, the debt (only when there is one) and the emergency fund |
| **Remittance** | The monthly amount, the cheapest provider's fee, what the family receives and the rate, the weeks to send, and a link to Remittance X-Ray with the corridor and amount. No corridor or nothing to send: no link, and a line saying prices cannot be compared |
| **Remittance X-Ray deep link** | `/remittance?corridor=AU-IN&amount=900` opens with the corridor chosen and the amount filled in and **runs the comparison once**. A link that is not valid (unknown corridor, bad amount) opens the screen as usual |
| **Timeline** | The 13 weeks, with a "Send money" tag on the weeks of the remittance schedule |
| **Checklist** | Ticks are kept on the phone only, as ids, under the worker's id and the plan's id (`nomadfinance.coach.checklist.<uid>.<planId>`), and are wiped at sign-out with the Coach's other local data |
| **PDF** | "Download PDF" always; "Share" only where the browser can share a file. The file comes through the API with the token (`GET /plans/{id}.pdf?language=`), is made on the first request in a language, and is kept for the second press. If the phone refuses the share because the file took long, the screen says "Your PDF is ready. Press Share again." |
| **Figures** | Written as the PDF writes them: `4,200 AUD`, digits 0 to 9, whatever the language |

## Files

| File | Change |
|---|---|
| `frontend/src/types/coach.ts`, `services/coachService.ts` | The plan's types; `getCoachOverview`, `getCoachPlan`, `fetchCoachPlanPdf` |
| `frontend/src/hooks/useCoachPlan.ts` | `useCoachPlan` (keeps the previous language's plan while the next loads) and `useCoachOverview` |
| `frontend/src/utils/coachPlan.ts`, `coachChecklist.ts`, `coachPdf.ts`, `coachStorageKeys.ts`; `lib/coachLocalData.ts` | Figures, the Remittance link, warning order; the ticks; saving and sharing the file; the sign-out wipe |
| `frontend/src/components/coach/plan/` (new), `components/coach/PlanCard.tsx` (new) | `PlanHeader`, `WarningsPanel`, `BudgetCards`, `RemittanceCard`, `DebtFundCards`, `WeekTimeline`, `Checklist`, `PdfActions`, and the Coach page card |
| `frontend/src/pages/coach/CoachPlanPage.tsx`, `CoachPlanRoute.tsx` (new), `CoachHome.tsx`; `router.tsx` | The page, its lazy flag-guarded route, the card on the Coach page |
| `frontend/src/components/coach/score/PlanButton.tsx` | The success block links to the plan |
| `frontend/src/utils/corridors.ts`, `components/remittance/CorridorPicker.tsx`, `pages/remittance/RemittanceCompare.tsx` | `parseCompareLink`, an `initialAmount` for the form, the one automatic comparison |
| `frontend/src/lib/analytics.ts` | `/coach/plan/:planId` is anonymised in Google Analytics (the plan id is a hash of the worker's answers) |
| `frontend/src/i18n/coach/*.json` | `plan.*`, `home.plan.*`, `score.plan.view` in 6 languages |
| `frontend/src/mocks/coachTurns.ts` | `replayOverview` for tests |
| `docs/api/v2-coach.md`, `docs/deferred-items.md` | Status note; D-244 |

No shared file (`package.json`, lockfile, `firebase.json`, workflows) and no backend file was touched.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | The route | `/coach/plan/:planId`, flag-gated; reached from the score screen and a Coach page card (the dashboard widget is NF-FC-022) |
| 2 | The deep link | Fills the form **and** runs the comparison once, so the worker lands on the answer |
| 3 | Language | The app's language, translated on first view, previous plan kept meanwhile |
| 4 | PDF | Download always; Share only where Web Share with files is supported; the shared file is the same one |
| 5 | Figures | As the PDF writes them, not in the worker's own digits |
| 6 | Plan id in analytics | Replaced by `:planId` in the page path |
| 7 | Axe found a real fault | A `<dl>` held a plain `<div>` (the rate line); it is now a paragraph beside the list |

## Results

**Frontend (2026-10-09):** 1,334 tests pass (114 files); `tsc -b`, `eslint --max-warnings 0`, `prettier --check`, the i18n check (1,205 keys × 6 languages) and `pnpm build` are clean.

| Check | Result |
|---|---|
| The page, from the recorded plans | All nine sections in order; urgent warning first with its severity written; figures as `4,200 AUD`; the link is `/remittance?corridor=AU-IN&amount=900`; the three send weeks are marked in the 13; a plan with no debt and no provider hides the debt card and the link and says why |
| Checklist | Starts unticked; a tick is stored as an id under the worker and the plan and shows again on the next visit; un-ticking removes the key; blocked or damaged storage never throws |
| Not found, errors | A missing plan says so with no retry; a server error offers Try again and shows the plan when it works |
| Language | Asks in the app's language; a switch keeps the plan on screen with the note, then shows the Hindi plan |
| PDF | Request carries the token and the language; one request however many presses; a new language asks again; Share hidden where unsupported, "press again" when blocked, saves the file when the phone cannot share, silent when the sheet is closed; a failure shows an alert and works on the next press |
| The deep link | Corridor and amount filled in, one `mutate` call, none on a second render; invalid links change nothing |
| The flag | Off: redirected, the page never rendered; on: shown |
| Accessibility | axe (serious and critical) is clean on the page; no raw key in any of the six languages |

**In the emulator (real backend and a real Gemini key; a plan seeded from the English mock; viewport 360 × 740):**
- `/coach` showed "Your 90-day plan is ready" with "View my plan"; the page opened with every section and **no sideways scroll** (page width 360).
- **Deep link:** "Compare in Remittance X-Ray" opened `/remittance?corridor=AU-IN&amount=900`: AU → IN chosen, 900 filled in, **one** compare request, the results "Sending A$900 to India" with 35 table rows.
- **Hindi:** switching the language dimmed the English plan under the note, a real translation call took about 4 seconds, and the page showed the Hindi plan (headings, checklist) with figures still `4,200 AUD`.
- **PDF:** with the Storage emulator running, "Download PDF" fetched a real PDF (`%PDF-1.7`, 22 KB, saved as `nomadfinance-plan-en.pdf`); a second press saved again with **no second request**; in Hindi a new request returned a 35 KB `nomadfinance-plan-hi.pdf`. Without Storage the API answered 500 and the screen showed the error in Hindi with the button usable again.
- **Checklist:** one tick stored `["open_pay_account"]` under the worker and plan, and was ticked again after a reload.

**Not verified:** Share with a file on a real phone (this browser has no `canShare`, so the button is correctly hidden); the screen on a real phone; the wording by native speakers (D-244).

## Manual test

```bash
cd frontend && pnpm vitest run src/pages/coach src/components/coach src/utils/coachPlan.test.ts src/utils/coachChecklist.test.ts src/utils/coachPdf.test.ts src/pages/remittance
```

Locally: run the Firebase emulators **with Storage** (`firebase emulators:start --only auth,firestore,storage --project demo-nomadfinance` from `frontend/`), start the API with `STORAGE_EMULATOR_HOST=http://127.0.0.1:9199` in addition to the variables of `backend-api-live`, and `frontend-emulator`. Seed a worker, set `config/feature_flags.flags.coach.enabled` to true, store a plan under `users/{uid}/coach_plans/{id}` (the English mock `docs/mocks/coach/plan-get-01-english.json` has every field), sign in, open `/coach`, press "View my plan", then try the link into Remittance X-Ray, a language switch and the PDF. For the comparison to return prices, load `rates_cache` and `corridors` into the emulator.

**Windows PowerShell:** set the variables first, for example `$env:STORAGE_EMULATOR_HOST = "http://127.0.0.1:9199"`, then run `uvicorn` in the same window.

## Definition of Done (Frontend)

- [x] The plan mock renders at 360 px with no sideways scroll (checked in the browser pane)
- [x] The deep link opens Remittance X-Ray with corridor and amount filled in (and runs the comparison once)
- [x] Week-by-week timeline, budget cards, remittance schedule, warnings panel, checklist with local ticks
- [x] PDF download works; Web Share offered only where supported (logic tested; not tried on a phone)
- [x] Strings through i18n in 6 languages; digits and plan id handled (analytics anonymised)
- [x] axe clean; strict types, lint and format clean; tests added for every part
- [x] No shared file touched
- [ ] Share tried on a real Android and iOS phone (D-244)
- [ ] Wording read by native speakers (D-244, D-221)
- [ ] Reviewed by a teammate (Aditya, who owns the task)

## Commit

Branch: `feature/NF-FC-021-coach-plan-view` (already checked out).

```bash
git commit -m "feat(coach): add 90-day plan view with PDF download and share" -m "Refs: NF-FC-021"
```

PR title: `feat(coach): 90-day plan view with PDF download and share (NF-FC-021)`
