# NF-HR-009 — UX polish and accessibility audit across the new modules

## Summary

Every signed-in screen was run through axe in a real browser, in the light and the dark theme, on a phone and a desktop, and walked with the keyboard. The failures it found were fixed, and the run is now a committed test (`frontend/e2e/accessibility.spec.ts`), so a contrast or heading regression fails CI. **axe finds 0 serious or critical issues on every screen tested.** The two open tickets from the regression suite (D-277, D-278) are closed.

| # | Finding | Where | Fix |
|---|---|---|---|
| 1 | `text-subtle` grey at 3.0:1 on 10 to 11 px labels (D-278) | sidebar "Menu", dashboard card headings, many small labels | `--subtle-foreground` light value to 42 % lightness (4.8:1 on the card, 4.6:1 on the muted surface) |
| 2 | Status words ("Good") at 3.3:1, in a colour meant for rings (D-278) | `/identity`, the dashboard card, the report preview | Words use `--safe-ink`, `--caution-ink`, `--danger-ink` (`STATUS_INK`); the paper preview uses fixed inks; the fills stay for graphics |
| 3 | The clause label at 4.3:1 (`opacity-80` on a tint) (D-278) | contract report | `opacity-80` removed |
| 4 | Error text (`text-destructive`) at 2.9:1 on the dark surface | 27 files: every form error and load error in the dark theme | `text-danger-ink` everywhere; `text-destructive` stays the button's background |
| 5 | The account button's name did not contain its visible text (WCAG 2.5.3, serious) | every signed-in page, both themes | The name is made from the content: the initials, then a screen-reader-only "Account menu" |
| 6 | White initials on a bright gold tile in the dark theme (1.7:1) | `/remittance` provider pair, landing | `dark:text-background` |
| 7 | Inactive step cards at `opacity-80` (landing, desktop) | `/` | Opacity removed |
| 8 | A sideways-scrolling diagram that a keyboard could not reach (serious) | landing, on a phone | The region takes focus and has a name |
| 9 | No level-1 heading in the loading and failed states | plan, scam check detail, Radar entity, Radar alerts and heatmap, contract list and report, identity, export, profile, remittance, 404 | One frame, `PageStateFrame`, puts the page's own title above its loading or failed state; the 404 page's title is an `h1` |
| 10 | The 360 px home in Tagalog at 1,517 px against 1,480 (D-277); Indonesian and Bengali had 0 and 5 px of room. CI then measured the page with the web font not yet loaded (the font comes from Google Fonts) and the Tagalog home was 1,499 | `/dashboard` | The KPI headings take the card's width on a phone, with less padding; the language badge is not on a phone; tighter gaps and padding on the cards, the tool tiles and the greeting. The test blocks the web font, so it holds the tallest case on every run |

## Files

| File | Change |
|---|---|
| `frontend/e2e/accessibility.spec.ts` (new) | axe in the browser, light and dark; the populated screens of every module; the loading and failed states; five other languages; the keyboard walk |
| `frontend/e2e/dashboard.spec.ts` | The two-screens limit in each of the six languages, with both modules on and a plan, the web font blocked and the answers of the two cards waited for |
| `frontend/e2e/support/coachSteps.ts` | `expectAsked` waits up to 15 s (it was 5): a Coach test was flaky on a loaded CI machine |
| `frontend/src/styles/tokens.css`, `utils/fibScore.ts` | The subtle grey; `STATUS_INK` and `STATUS_PAPER_INK` |
| `frontend/src/components/common/PageStateFrame.tsx` (new), `EmptyState.tsx` | The title frame; `headingLevel` may be 1 |
| `frontend/src/pages/**` (11 screens) | Their loading, failed and missing states under their header |
| `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/dashboard/{StatCard,KpiRow,GreetingBand,WidgetCard,FIBProgressWidget}.tsx`, `fib/{ScoreMeter,ReportDocCard}.tsx`, `contract/ClauseRow.tsx`, `layout/AccountMenu.tsx`, `landing/{Ecosystem,HowItWorks,PerformanceBento}.tsx`, `common/CountryPair.tsx` | The fixes above |
| 27 files with `text-destructive` | `text-danger-ink` (a class name; no logic) |
| Tests (new or changed) | `PageStateFrame`, `AccountMenu`, `NotFound`, the plan page and the check detail (a heading in every state); one plan-page test waited on the heading and now waits on the plan |

No shared file was touched (`package.json`, the lockfile, `tsconfig*`, workflows, `firebase.json`, rules): `axe-core` was already a development dependency and is loaded into the page from `node_modules`. No new string, so no translation changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | "axe 0 serious / critical app-wide" | Held as a test: WCAG 2.0 and 2.1, A and AA, serious and critical, in a real browser, both themes, both viewports. jsdom cannot judge contrast, so the unit tests could not hold it |
| 2 | Tagalog home (D-277) | The recommended option: remove room for every language, so no wording changed and no native read is needed. It turned out the lines were in the KPI cards' sentences, not the greeting; the icon tile on those four cards is not on a phone, and phone padding and gaps are tighter |
| 2a | Which font the limit is held with | The tallest case: the web font not loaded. On the first CI run the page was measured without it (Linux fallback fonts are wider for Latin text) and was 1,499 in Tagalog while the same code was 1,447 here; the test now blocks the font so the number does not depend on the network |
| 3 | Where a "state" is required | A screen that is a form on arrival (`/scam-check`, a check-in) has its states when the worker sends; it is scanned, not forced into a skeleton. The dashboard's Scam and Coach cards show the plain pitch while loading and on an error, on purpose (NF-HR-002, NF-FC-022): the way in is never taken away |
| 4 | The first-run tour | Scanned alone, as a dialog, since the page behind it is dimmed and out of reach; the page is scanned once the tour is closed |
| 5 | The Radar not-found state | Gets the page title too, since it has no data to name it |
| 6 | QA-A-09 (a console line on an expected 404) | Left: it is not shown to a worker |

## Results

**Frontend (2026-10-11), run as `frontend-ci.yml` runs them:** `pnpm lint` (0 warnings), `pnpm format:check`, `pnpm test:coverage` (142 files, 1,650 tests), `pnpm build`, the end-to-end job (`vite build --mode emulator`, `tsc -p e2e`, `firebase emulators:exec ... pnpm test:e2e`: **196 passed** on the desktop and mobile projects), and `pnpm test:rules` (186). No backend file changed.

| Check | Result |
|---|---|
| axe, populated screens | `/`, `/sign-in`, 404, `/dashboard` (with the tour as a dialog), `/profile`, `/scam-check` (and its verdict), history and detail, `/coach` (first question, second question, review, score), `/coach/plan/:id`, `/coach/checkin/:id`, `/contract`, history and report, `/identity`, log and export: **0 serious or critical**, light and dark, phone and desktop |
| axe, other languages | the home, the profile and the scam check in `hi`, `tl`, `id`, `ne`, `bn`: 0 |
| Loading and failed states | `/dashboard`, `/coach`, `/coach/plan/:id`, `/scam-check/history`, `/scam-check/history/:id` each show a status (loading) and an alert (failed), with a level-1 heading and 0 axe issues; nine v1 screens show a heading and 0 axe issues in both |
| Keyboard | on 7 screens (dashboard, profile, scam check, history, detail, contract, identity log): every visible control takes focus by Tab and shows an outline or a ring; the first-run tour holds focus and Escape ends it (`dashboard.spec.ts`) |
| Dashboard height, 360 × 740, web font blocked (the tallest case) | `en` 1,346, `hi` 1,340, `tl` 1,397, `id` 1,391, `ne` 1,343, `bn` 1,376 px, against 1,480, on this machine. The same case on the first CI run, before the second trim: `tl` 1,499. Before any change: `tl` 1,517 |
| Time | the new spec is 36 tests and about 2 minutes on one machine; the end-to-end job went from about 1.1 to 2.8 minutes here (CI is about twice as slow). The whole job also ran with 4 workers and no retries: 196 passed |
| Break check | The first run failed on 5 families of findings (list above); each was seen failing before its fix and passing after. The first measurement of the home in Tagalog (1,517) failed the target; the three changes that followed are in the table |

## Screens and their states

| Screen | Loading | Empty | Failed | Held by |
|---|---|---|---|---|
| `/dashboard` KPI cards | skeleton the shape of the figure | a way forward, never a "0" | a line | `StatCard`; browser sweep |
| `/dashboard` Radar, contracts, identity cards | skeleton | message | message | browser sweep |
| `/dashboard` Scam and Coach cards | the plain pitch | the pitch with Start | the pitch | by design (NF-HR-002) |
| `/scam-check` | the button is busy | the empty form | an alert with the reason | `scam-check.spec.ts` |
| `/scam-check/history` | skeleton | "no checks yet" | an alert with Try again | browser sweep |
| `/scam-check/history/:id` | spinner under the title | "we could not find this check" | an alert with Try again | unit test, browser sweep |
| `/coach` | skeleton | the first question | an alert | browser sweep |
| `/coach/plan/:id` | skeleton under the title | "we could not find this plan" | an alert, Try again | unit test, browser sweep |
| `/coach/checkin/:id` | none (a form) | the invalid-link state | the answer's own error | `CoachCheckinPage` tests |
| Contract, Identity, Radar, remittance, profile | spinner under the page title | their own empty states | alert with retry | unit tests; read in code; axe |

## Manual test

From `frontend/`, with the emulators as CI runs them (stop anything on ports 8085, 9099 and 4173 first):

```bash
VITE_API_BASE_URL=http://127.0.0.1:4173 pnpm exec vite build --mode emulator
pnpm exec tsc -p e2e
firebase emulators:exec --only auth,firestore --project demo-nomadfinance "pnpm exec playwright test e2e/accessibility.spec.ts e2e/dashboard.spec.ts"
```

**Windows PowerShell:** `$env:VITE_API_BASE_URL = "http://127.0.0.1:4173"` first, then the same three commands.

By hand: open `/dashboard` in a 360 px window in Tagalog and scroll to the end (about 1,400 to 1,450 px, under two screens, with or without the web font); switch to the dark theme and open any form with a mistake in it (the error line is readable); press Tab from the address bar on `/scam-check` (the skip link, the header, then the form, each with a ring); open `/coach/plan/<any id>` with the network off (the heading is there, then the alert).

## Definition of Done (Frontend Feature)

- [x] Strict types, lint and format clean; no shared file touched; no dependency added
- [x] Loading, empty and error states on every new screen, each shown or held by a test
- [x] axe 0 serious or critical on every screen, light and dark, phone and desktop
- [x] Keyboard: every control reachable, focus visible, the tour closes with Escape
- [x] Mobile responsive (the phone project, 360 px home in six languages)
- [x] No new string, so all six languages are unchanged; no raw keys
- [x] The CI jobs run locally with the same commands, including end-to-end
- [ ] Tried with a screen reader on a phone (D-285)
- [ ] Wording read by native speakers (D-268, D-270)
- [ ] Screenshots in the pull request (before and after of the dashboard in Tagalog, the dark-theme error line)
- [ ] Reviewed by a teammate (Pranjal)

## Commit

Branch: `feature/NF-HR-009-frontend-polish-v2` (already checked out).

```bash
git commit -m "fix(accessibility): fix contrast, names and headings found by axe" -m "Refs: NF-HR-009"
```

The header is 65 characters (the limit is 72), and the scope is letters only: commitlint's kebab-case rule refuses digits, so `a11y` is not a valid scope. PR title: `fix(accessibility): axe-clean screens, headings in every state and a 360 px home in six languages (NF-HR-009)`
