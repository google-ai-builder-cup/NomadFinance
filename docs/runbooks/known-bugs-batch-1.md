# Known bugs, batch 1: eight open items from the demo list

Fixed on 2026-10-13 after NF-HR-005 and NF-HR-006 merged. The list was kept by the team (items 2 to 9 of it); each is checked against `main` below. No task id: these came from the demo walk-through, not from the tracker.

## Summary

| # | Bug | Result |
|---|---|---|
| 2 | Day-30 check-in not arriving from Cloud Scheduler | **No defect found in the code; production still has to be read** (below) |
| 3 | One contract flags an employer at once | **Fixed** |
| 4 | Contract upload 400 / 415 / 422 all say "Something went wrong" | **Fixed** |
| 5 | A repeated scam check ignores the route | **Fixed** |
| 6 | Contract salary logged as written, hourly counted as a month | **Fixed** (the score no longer adds an hourly rate up) |
| 7 | `1.500` read as 1,500 with no warning | **Fixed** (it says how it was read; the reading itself is unchanged) |
| 8 | `RemittanceHistory.tsx` empty, no list of logged transfers | **Fixed** (a real page and route) |
| 9 | The Financial Identity score only from the weekly job | **Fixed** (a button, and an endpoint, that work it out now) |

## What changed

| # | Where | Change |
|---|---|---|
| 3 | `backend/app/services/cross_pillar/contract_to_radar.py` | All reports of one contract share one `cluster_id` (the first report's id), so the entity's `incident_count` goes up once per contract, not once per kind of danger. Two contracts about one business are still two incidents |
| 4 | `frontend/src/utils/pipelineProgress.ts`, `components/contract/UploadDropzone.tsx`, `i18n/*.json` | 400 says the file is empty, 413 too large, 415 not a PDF or photo, 422 not a contract. The picker also refuses an empty file before sending (`minSize: 1`) |
| 5 | `backend/app/services/scam/analyzer.py` | A stored check is served only when its `corridor_id` equals the request's. After a change of route the message is checked again (one Gemini call, one hourly check) and the stored check is replaced |
| 6 | `backend/app/services/cross_pillar/contract_to_fib.py`, `fib/profile_metrics.py`, `profile_builder.py`, `report_html.py`, `report_labels.py` | The income entry keeps the stated `amount` and gains `salary_period` and `monthly_amount` (month: as is; week: ×52/12; hour or day: null). The score reads `monthly_amount`; a null is left out and counted in `excluded_entries`. The PDF prints the period beside the salary ("18 AUD per hour") in six languages. Currencies without a rate were already left out |
| 7 | `frontend/src/utils/amountReading.ts`, `components/common/AmountReading.tsx`, the Remittance amount and the three Financial Identity amount fields | One dot followed by exactly three digits is shown as "We read this as 1,500." before sending |
| 8 | `frontend/src/pages/remittance/RemittanceHistory.tsx`, `hooks/useRemittance.ts`, `services/remittanceService.ts`, `router.tsx` | `/remittance/history`: the newest 50 logged transfers (date, service, sent, received, route), read from `users/{uid}/transfers`, with a link from the Remittance page. No firestore.rules change: the owner could already read it |
| 9 | `backend/app/api/v1/fib.py`, `services/fib/profile_builder.py` (`refresh_profile`), `schemas/fib_profile.py`; `frontend/src/components/fib/RefreshScore.tsx` | `POST /api/v1/fib/profile/refresh` works out the caller's profile now (one reasoning-tier call). A profile younger than an hour is returned as it is. The Identity score screen shows "Work out my score now" while there is no score |

## Item 2: what was checked, and what is left

- **The job in the code and against Firestore:** `send_checkins` and its repository, the internal route and the OIDC check pass (76 tests, 40 of them against the Firestore emulator, including the group-scope query on `departure_date`). Nothing in the code explains a day-30 reminder that does not arrive.
- **The five Scheduler files** use the same address and audience, so if the rate refresh runs, this one authenticates the same way.
- **By design, not defects:** only a worker's newest plan is reminded; the reminder is due 30 days after `departure_date` and picked up for 3 days after; the job runs once a day at 02:00 UTC, so a plan set to 30 days ago "now" is reminded at the next run, or when the job is run by hand; a worker with `reminders: false` or the `coach` flag off is skipped.
- **What a person has to read** (D-231, D-276; not readable from here):
  1. `gcloud scheduler jobs run coach-checkins --project nomadfinance-prod --location asia-south1`
  2. In Logs Explorer, `jsonPayload.message=~"^coach_checkins "`: `found=` is how many plans were in the window, and `skipped={...}` says why a plan was not reminded (`superseded`, `reminders_off`, `flag_off`).
  3. If the run answers 401 or 403, the audience on the Cloud Run service (`CRON_AUDIENCE`) does not equal the one in the YAML; if 503 with `coach_checkin_query_failed`, the group-scope index on `coach_plans.departure_date` is missing (D-114).

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Item 3: what is "independent" | One contract is one incident. Two contracts by the same worker about the same employer still count as two (nothing identifies the worker on a contract signal, so there is no way to tell them apart): D-333 |
| 2 | Item 5: serve with new fields, or check again | Check again. The route changes the explainer's wording as well as the flags, so patching two fields would leave a text for the wrong route. It costs one check, once per route change |
| 3 | Item 6: how to count an hourly rate | Not at all, rather than guess at hours. The PDF still shows what the contract says. `monthly_amount` for a week uses 52 ÷ 12 weeks a month |
| 4 | Item 7: change the reading or say it | Say it. A dot before exactly three digits is how Indonesian and European keyboards write thousands, and refusing it would refuse correct amounts |
| 5 | Item 8: edit or delete a logged transfer | Read-only. A wrong entry is not edited here; that is its own decision (D-334) |
| 6 | Item 9: compute on every log, or on request | On request, with a one-hour floor. Every log would be a 20 to 40 second reasoning call per entry and a bill with it |

## Checks run (2026-10-13)

| Check | Result |
|---|---|
| Backend `ruff`, `black --check`, `mypy app` | clean |
| Backend unit | 3,252 passed, 1 skipped |
| Backend integration (emulators) | all but one passed on the first run; the one was the AI-route list in `test_auth_matrix.py`, which now names the new route (25 passed) |
| Frontend `lint`, `format:check`, `tsc`, `tsc -p e2e` | clean |
| Frontend unit | 152 files, 1,729 passed |
| End-to-end, default projects (`vite build --mode emulator`, as CI) | 250 passed (246 before, plus 4 new) |
| API contract docs | `docs/api/openapi.json` re-exported, `docs/api/endpoints.md` has the new route (`test_api_contract_docs.py` passes) |

**Not verified:** the Cloud Scheduler job in production (item 2); the new strings by a native speaker (D-335); the refresh button against the real model (a 20 to 40 second call); the Firestore read of the history on a worker with more than 50 transfers.

## Commit

```
fix(known-bugs): close eight open items from the demo walk-through
```

One commit is simplest; to keep each fix easy to review or drop, the same work splits cleanly by item:

```
fix(radar): count one contract as one incident
fix(contract): say why an upload was refused
fix(scam): check a message again after a change of route
fix(fib): count a contract salary by the month, not as written
fix(frontend): say how an amount like 1.500 was read
feat(remittance): list the transfers a worker logged
feat(fib): work out the score on request
```
