# NF-SA-022 — Scam analytics events and weekly corridor counts

## Summary

Two things, both counts and never content:

1. **Three Firebase Analytics events** from the check screens: `scam_check_submitted`, `scam_verdict_viewed`, `scam_reported`.
2. **A daily job** that counts the Scam Analyzer's stored checks per corridor, ISO week and kind of scam into `scam_stats/{corridor}/weeks/{isoWeek}`, the feed for the Partner API later.

The contract of the collection and the events is in `docs/data-model/collections/scam.md` ("`scam_stats`" and "Analytics events").

## The events

| Event | Fired by | Parameters |
|---|---|---|
| `scam_check_submitted` | `ScamCheckHome`, when the worker taps Check. A "Try again" after a failure is the same submission and is not counted again | `input_type` (`text`, `screenshot`), `corridor_id` (id or `none`), `language` |
| `scam_verdict_viewed` | `ScamResult`, once per check put on the screen | `is_scam`, `risk_level`, `scam_type` (id or `none`), `cached`, `source` (`check` = just finished, `history` = a stored check opened) |
| `scam_reported` | `ReportButton`, when the report is created. Not when the server only returns the first report (`already_reported`) | `scam_type` |

The functions are in `frontend/src/lib/analytics.ts` and take typed arguments, so a message cannot be passed to them by accident. A test checks the exact parameters of each. Nothing is sent in emulator mode or without `VITE_FIREBASE_MEASUREMENT_ID`, and Analytics is loaded only on first use, like the other events.

## The weekly counts

| Piece | What it does |
|---|---|
| `POST /api/v1/internal/aggregate-scam-stats` (`app/api/v1/internal.py`) | Cloud Scheduler only (OIDC, as the other jobs), hidden from the public docs. 200 when both weeks were written, **503 when a week could not be read or written**, so the scheduler retries |
| `app/services/scam/stats.py` | ISO-week arithmetic in UTC, the counting (`tally`) and the run. Under `mypy --strict` |
| `app/repositories/scam_stats_repo.py` | A collection-group query on `scam_checks.created_at` with a **field mask** (only `corridor_id`, `verdict.is_scam`, `verdict.scam_type`, `input_type`, `reported_at`), and a batched write of the 7 corridor documents of a week |
| `infra/cloud-scheduler/scam-stats.yaml` | `30 1 * * *` UTC. `scheduler-deploy.yml` creates the job when the file is merged to `main` |
| `frontend/firestore.indexes.json` | `fieldOverrides` for `scam_checks.created_at`: collection ascending and descending (the history), collection group ascending (this job) |

**Idempotent by replacement.** Each run recounts the current and the previous ISO week from the checks and **replaces** the documents with what it counted. Nothing is added to what a former run wrote, so a retry, a double run or a manual run gives the same documents. Older weeks are not recounted: stored checks are deleted after 90 days and a recount would make them shrink.

**Counts only.** A document holds numbers, the corridor id, the week label, the type ids and timestamps. A test feeds it a check carrying a message, a link, an explainer and a uid and asserts none of it reaches the document; an emulator test seeds checks with a message, an account number, a domain and two worker ids and asserts none of them appears anywhere in `scam_stats`.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | The tracker's `scam_stats/{corridor}/{iso_week}` has three path segments, which is not a document path | `scam_stats/{corridor}/weeks/{isoWeek}`. `none` is the corridor of a worker whose route is none of the six |
| 2 | How often, and which weeks | Daily at 01:30 UTC; the current and the previous week only |
| 3 | A week with one check describes one person | Exact counts are stored (the collection has no client access). **The Partner API must hide a cell under 5** (D-165) |
| 4 | The route of the job | Under `/api/v1/internal/` like the other four jobs. `app/core/features.py` labels it `scam` |
| 5 | What a "check" is | One stored check (one message of one worker in one language). A repeat of the same message is not counted again |
| 6 | `scam_verdict_viewed` from the history | Counted with `source: "history"`, so the two can be told apart |

## Manual test

**The events in DebugView** (needs a real Firebase measurement ID, so not in CI). In `frontend/.env.local` set `VITE_FIREBASE_MEASUREMENT_ID`, run `pnpm dev` (a development build sends with `debug_mode`), sign in with a user the `scam` flag is on for, and open Firebase console, Analytics, DebugView:

1. Paste a message and tap Check: `scam_check_submitted` with `input_type: text`.
2. When the answer shows: `scam_verdict_viewed`, `source: check`.
3. Tap Warn other workers, Send warning: `scam_reported`, with the kind of scam.
4. Open the history and a stored check: `scam_verdict_viewed`, `source: history`.
5. Look at every parameter of every event: none holds any words of the message.

**The job.** After the pull request is merged and deployed, and the index and dimensions of D-164 are done:

```bash
gcloud scheduler jobs run scam-stats --project nomadfinance-prod --location asia-south1
```

Then in Firestore open `scam_stats`: 7 documents (`SG-PH` to `AU-PH` and `none`), each with a `weeks` collection holding the two ISO weeks. Run the command a second time: every number is the same and only `computed_at` is later. If the run failed, the log of the Cloud Run service shows `scam_stats_week_failed`; the usual cause is the missing index (the log names it).

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| Backend tests, no emulator | 2,044 passed, 125 skipped; 17 new for the counting and the run, 7 for the route (the answer, 503, 401, 403, hidden), 1 for the feature label |
| Backend emulator step (`firebase emulators:exec ... pytest tests/integration`) | 559 passed, 75 skipped; 3 new: the query finds checks of every worker in the week and reads only the counted fields, a second run changes nothing, nothing a worker wrote reaches the stats |
| Frontend `tsc -b`, ESLint, Prettier | clean |
| Frontend tests | 806 passed, 12 new (the exact parameters of each event, once per check, history vs check, retry not recounted, already-reported not counted, no event without a measurement ID) |
| Break the code on purpose | Counting each check twice failed 4 tests; dropping the field mask failed the emulator test; both restored |

**Not verified:** DebugView (it needs a real measurement ID), the production index (it does not exist yet: D-164), the Cloud Scheduler job on the real service, and the daily run's cost on a busy week (one read per check in two weeks).

## Definition of Done (Data task)

- [x] Events fire with coarse parameters only
- [ ] Events seen in DebugView (manual, above)
- [x] Job idempotent (test) and counts only (tests)
- [x] Behind Cloud Scheduler authentication
- [x] Data model, runbook and deferred items updated
- [ ] Index created in production, custom dimensions registered, job run once (D-164)
- [ ] Reviewed by a teammate (Aditya)

## Commit

Branch: `feature/NF-SA-022-data-scam-stats` (already checked out).

```bash
git commit -m "feat(scam): add analytics events and weekly corridor counts" -m "Refs: NF-SA-022"
```

PR title: `feat(scam): analytics events and weekly corridor counts for the Scam Analyzer (NF-SA-022)`
