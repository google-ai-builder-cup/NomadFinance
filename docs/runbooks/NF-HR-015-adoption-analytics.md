# NF-HR-015 — Adoption analytics funnels and the pitch snapshot

## Summary

The Scam Analyzer and the Coach can now be followed from start to finish in Google Analytics, and the two numbers of the pitch (Coach completion rate, scams caught) come from one saved query.

| Part | What it is | Where |
|---|---|---|
| **Coach events** | `coach_started`, `coach_answers_confirmed`, `coach_plan_created`, `coach_plan_viewed`, `coach_checkin_answered` (the scam events already existed, NF-SA-022) | `frontend/src/lib/analytics.ts` |
| **Funnels, audiences, dimensions** | The exact definitions to build in the console | `infra/analytics/ga4-definitions.json`, this page |
| **The snapshot** | A read-only script over Firestore: counts only, the same figures on a second run | `data-scripts/src/metrics/adoption_snapshot.py`, `data-scripts/scripts/adoption_snapshot.sh` |

**What the code cannot do:** funnel explorations and audiences are made in the Google Analytics console, so they are built by hand from the definitions below, and "funnels visible in the console" is checked there (open item in the Definition of Done).

## The events

| Event | Fired by | Parameters |
|---|---|---|
| `coach_started` | `useCoachSession` when the interview comes back from the server: `new` (created), `resumed` (the open one); `useCoachRestart` sends `restart` | `start_kind`, `ui_language` |
| `coach_answers_confirmed` | `CoachChat`, when the stage becomes `plan` on this screen. Not for an interview that was already confirmed when the screen opened | `ui_language` |
| `coach_plan_created` | `useMakeCoachPlan`, when the plan call succeeds | `band`, `corridor_id`, `ui_language` |
| `coach_plan_viewed` | `CoachPlanPage`, once per plan on each opening of the screen (not again on a translation) | `band`, `corridor_id`, `ui_language` |
| `coach_checkin_answered` | `useSubmitCheckin`, for the first answers of a milestone only | `milestone` |

Every parameter is a short id or a flag. A test pins the exact parameters of each, and another reads `infra/analytics/ga4-definitions.json` and fails if it names an event or a parameter the app does not send, or a funnel uses a parameter that is not a custom dimension.

## Build it in the console (once, about 15 minutes)

Do this after the app with these events is deployed and a few events have arrived (Analytics → Realtime shows them within a minute). Labels in the console move; the values are exact.

**1. Register the custom dimensions** (Admin → Data display → Custom definitions → Create custom dimension): scope *Event*, one for each row of `custom_dimensions` in the definitions file. A dimension reports only what is collected after it is registered, so do this first. Several (`ui_language`, `corridor_id`, `input_type`, `is_scam`, `risk_level`, `scam_type`, `source`) are the ones D-164 already asked for; register only the ones missing: `start_kind`, `band`, `milestone`.

**2. Build the four funnels** (Explore → Blank → Technique *Funnel exploration*). For each funnel in `funnels`:

1. Name it as in the file. Under Tab settings leave **Make open funnel** off (a worker who skips the first step is not in the funnel), turn **Show elapsed time** on, and add the listed `breakdowns` as the breakdown dimension (one at a time).
2. Edit the steps. For a step: add a condition *Event name* exactly *is* the step's `event`; for each of its `conditions`, **And** the custom dimension *equals* the value (`is_scam` equals `true`; the value is a string in Analytics).
3. Apply and read the bars: users who did each step, the drop between them.

| Funnel | Steps | What it answers |
|---|---|---|
| Scam Analyzer: check, verdict, warning | `scam_check_submitted` → `scam_verdict_viewed` (`source` = `check`) → `scam_reported` | Do workers who send a message read the answer, and do they warn others |
| Scam Analyzer: scam caught, warning | `scam_verdict_viewed` (`is_scam` = `true`, `source` = `check`) → `scam_reported` | Of the scams caught, how many are reported to the Radar |
| Coach: start, answers, plan, plan read | `coach_started` (`start_kind` = `new`) → `coach_answers_confirmed` → `coach_plan_created` → `coach_plan_viewed` | Where workers drop out of the interview |
| Coach: plan, check-in | `coach_plan_created` → `coach_checkin_answered` | Whether a plan brings the worker back |

**3. Create the four audiences** (Admin → Audiences → New audience → Create a custom audience): *Coach started, no plan yet* (include `coach_started`, exclude `coach_plan_created`, 30 days), *Coach plan makers* (`coach_plan_created`, 90 days), *Scam checkers* (`scam_check_submitted`, 30 days), *Caught a scam* (`scam_verdict_viewed` with `is_scam` = `true`, 30 days). An audience fills in 24 to 48 hours.

**4. Check it.** Explore → the four funnels each draw bars, with the breakdown cutting them. Admin → Audiences lists the four, each with a user count after a day. If a funnel shows nothing, open DebugView with a development build (see `NF-P1-025-firebase-analytics.md`) and walk the feature: each step's event should appear with its parameters.

## The pitch snapshot

```bash
cd data-scripts
./scripts/adoption_snapshot.sh                                  # all that is stored
./scripts/adoption_snapshot.sh --since 2026-10-01 --json out.json   # a window, and the full figures
```

Against the emulator set `FIRESTORE_EMULATOR_HOST` first; against production run `gcloud auth application-default login` with read access to `nomadfinance-prod`. It reads three collection groups (`coach_sessions`, `coach_plans`, `scam_checks`) with a field mask, writes nothing, and prints a table; `--json` also saves every figure.

### What each number means

| Figure | Definition |
|---|---|
| Interviews started | Stored `coach_sessions` documents (every status). A worker who starts over has two |
| Interviews that reached a plan | `status` = `completed` |
| **Completion rate** | reached a plan ÷ started. Open interviews count as not finished, so it rises as they finish |
| Of those that ended | reached a plan ÷ (reached a plan + abandoned): the rate with nobody still in progress |
| Workers with a plan / who started | Distinct workers, so a worker who gave up once and finished once is a completion |
| Median minutes to a plan | `completed_at` − `created_at`, median of the finished ones |
| Check-ins answered | Plans with `checkins.d30/d60/d90.answered_at` |
| Messages checked | Stored `scam_checks` documents. A repeat of a stored message is one document; `times_asked_including_repeats` adds its repeats |
| **Scams caught** | `verdict.is_scam` = true |
| Reported to Radar | `reported_at` is set |

Breakdowns (by band, corridor, language, scam type) hide a cell under 5 as `<5`, as the Partner API must (D-165). Totals are exact. Demo workers are left out unless `--include-demo` is given, so the numbers are real usage.

### What the numbers are not

- **What is stored now, not ever.** A check is kept 90 days, an interview 30, and a worker who closes their account takes both away. Run it for the pitch and keep the output: the figures are a photograph.
- **Not who used the app.** Analytics counts browsers that allowed it; this counts what the server stored. They will not match, and neither is "all users".
- **A completion rate on a small base** (the finale has a handful of workers) describes those workers, not workers in general. Say the count next to it.

### Worked example (emulator, demo seed, `--include-demo`)

The three demo workers of NF-HR-003, seeded into the emulator, give the table below. It shows the shape and proves the second run is the same (the two JSON files were identical apart from `generated_at`); it is not a measure of usage.

| Measure | Value |
|---|---|
| Coach interviews started | 3 |
| Coach interviews that reached a 90-day plan | 3 |
| **Coach completion rate** | **100%** |
| Workers with a plan / workers who started | 3 / 3 |
| Median minutes from start to plan | 10.0 |
| Check-ins answered (day 30 / 60 / 90) | 2 / 0 / 0 |
| Messages checked by the Scam Analyzer | 15 |
| **Scams caught** | **9** (6 high risk) |
| Warned other workers (reported to Radar) | 0 |

## Files

| File | Change |
|---|---|
| `frontend/src/lib/analytics.ts`, `analytics.test.ts` | The five Coach events, their tests, and the drift test against the definitions file |
| `frontend/src/hooks/{useCoachSession,useMakeCoachPlan,useCoachCheckin}.ts`, `components/coach/CoachChat.tsx`, `pages/coach/CoachPlanPage.tsx` | Where each fires |
| `frontend/src/hooks/coachAnalytics.test.tsx` (new), `CoachChat.review.msw.test.tsx`, `CoachPlanPage.msw.test.tsx` | When each is sent, and when it is not |
| `infra/analytics/ga4-definitions.json` (new), `infra/README.md` | The definitions |
| `data-scripts/src/metrics/adoption_snapshot.py` (new), `scripts/adoption_snapshot.sh` (new), `tests/test_adoption_snapshot.py` (new), `tests/fake_firestore.py` | The snapshot |
| `docs/data-model/collections/coach.md`, `data-scripts/README.md`, `docs/deferred-items.md` | Docs |

No shared file (`package.json`, lockfile, `tsconfig*`, workflows, `firebase.json`, rules, indexes) was touched, no dependency was added, and no index is needed: the snapshot reads unfiltered collection groups.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where the pitch numbers come from | Firestore, not the Analytics API: it also counts completions a browser never reported, needs no property credentials, and is the data the product itself holds |
| 2 | "Complete" for the Coach | A plan was made (`status` = `completed`). Reading the plan is a further funnel step, and a check-in is a follow-through funnel |
| 3 | "Started" | The interview exists. A worker who opens the Coach and leaves has started one; this is why `start_kind` = `new` is the funnel's first step and `resumed` is not |
| 4 | Plan made twice | `coach_plan_created` is sent on every successful call; asking again returns the same plan. Funnels count users, so a repeat does not change them |
| 5 | Small cells | Hidden in breakdowns, exact in totals (D-165) |
| 6 | Demo workers | Left out by default, so the pitch is real usage |
| 7 | The definitions file | Documentation that a test keeps honest, not something the app or a job reads. Creating funnels through the Analytics Admin API needs credentials that are not in the project |

## Checks run (2026-10-13)

| Check | Result |
|---|---|
| Frontend | `pnpm lint`, `format:check`, `test:coverage`, `build`, end-to-end: see the Definition of Done |
| Data-scripts | `pytest` (12 new), `ruff check`, `black --check`, `mypy src tests` |
| The snapshot against the real client | Firestore emulator, demo seed: the field masks with dotted paths return what the code reads; a second run is identical apart from `generated_at` |
| Break check | Naming `start_kind` as `kind` in the definitions file fails the drift test with the event and both names |

**Not verified:** the funnels and audiences in the console (they cannot be built or read from here), DebugView for the Coach events (it needs a real measurement ID), the snapshot against production, and the cost of the read on a busy week (one read of three small fields for each stored document).

## Definition of Done (Data task)

- [x] Events fire with coarse parameters only, and are tested
- [x] The definitions of the funnels, audiences and dimensions are exact and kept honest by a test
- [x] The snapshot is read-only, counts only, and the same on a second run (test, and the emulator)
- [x] Data model, runbook and deferred items updated; no shared file touched
- [ ] Custom dimensions registered, the four funnels and four audiences built, and the funnels seen in the console (the steps above; D-315)
- [ ] The Coach events seen in DebugView (D-315)
- [ ] Snapshot run once against production before the demo (D-316)
- [ ] Reviewed by a teammate (Aditya)

## Commit

Branch: `feature/NF-HR-015-data-analytics-funnels-v2` (already checked out).

```bash
git commit -m "feat(analytics): add Coach funnel events and an adoption snapshot" -m "Refs: NF-HR-015"
```

PR title: `feat(analytics): Coach funnel events, GA4 definitions and an adoption snapshot (NF-HR-015)`
