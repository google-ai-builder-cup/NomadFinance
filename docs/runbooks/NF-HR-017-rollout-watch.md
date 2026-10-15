# NF-HR-017 — Production rollout watch (48 hours) and post-release review

Owner Devam, reviewer Pranjal. Branch `chore/NF-HR-017-ci-post-release-v2`. Written 2026-10-13.

## Summary

After both modules are on for everyone, someone watches the service for 48 hours, triages whatever is new, and files a review note. **This page is how to do that, and the tools for it. It is not the watch.** A 48-hour watch is real time against production, so nothing here claims a result: the watch log below and the "Watch results" sections of [`docs/release-notes/v2.0.md`](../release-notes/v2.0.md) are empty until a person fills them.

| What | Where |
|---|---|
| **The numbers of any window** in one command: requests and server errors by feature, p50 and p95 by route, Gemini failures, budget refusals, cache hit rate, and what crossed a threshold | `infra/monitoring/watch_report.py` |
| **Two alerts that could fire**: server errors above 5 % of requests (with at least 20 requests in 15 minutes), and p95 latency above 30 s. Before this there was only the Gemini daily-limit alert, and every limit is still `null` (D-122), so "no unacknowledged alert" would have been true of nothing | `infra/monitoring/service-alerts/` |
| **The plan**: prerequisites, schedule, per-check procedure, thresholds, triage, log, ending the watch | this page |
| **The note** to file at the end, with what is already known filled in | `docs/release-notes/v2.0.md` |

## Before the clock starts

The 48 hours begin at **T0 = the moment both flags are on for everyone** (Scam Analyzer, then Coach, as `NF-HR-011-release-v2.0.md` stages it). Production already had both on on 2026-10-11, so T0 is the time you start watching with the alerts below in place; write it down. Each item says how to know it is done.

| # | Before T0 | How to check | If it is not |
|---|---|---|---|
| P1 | The release steps of `NF-HR-011-release-v2.0.md` are done: gate G4 and G5 clear (G2 and G3 were done on 2026-10-13), `v2.0.0` tagged and released | `git for-each-ref refs/tags`; `/health` says `"version":"2.0.0"` | Not a reason to skip the watch, but say so in the note: the watch is then of an untagged build |
| P2 | **Monitoring exists in the project** (dashboard, metrics, alerts) and has been created with this task's alerts | Cloud Monitoring, Dashboards: *NomadFinance: requests, errors and Gemini usage*. Alerting, Policies: *API server errors above 5% of requests* and *API 95th percentile latency above 30 s* | `ALERT_EMAILS="a@x,b@x,c@x" bash infra/monitoring/setup-monitoring.sh` (D-122), by a project owner. Try `DRY_RUN=1` first |
| P3 | Every `rpd` in `quota-limits.json` is a number, the backend redeployed by hand (the budget guard is on) | `quota-limits.json` has no `null`, and `gemini_usage/<today>` (Firestore) has `calls.<feature>.<tier>` counts once a request has been made | D-122 and D-286 (`NF-HR-010-gemini-quota-guard.md`). Without it a spent quota shows workers "try again later" with no early warning |
| P4 | Scam patterns loaded | Firestore `scam_patterns` has about 480 documents | `python -m src.loaders.scam_patterns` from `data-scripts/` (D-135, D-271). Without it "seen before" has nothing to search |
| P5 | The state of the flags is known and intended, including the tester `allow_uids` on `scam` | Firestore `config/feature_flags` | Decide and write it in the note (G10) |
| P6 | A starting window is on record | `python infra/monitoring/watch_report.py --window 6h` and paste the table in the log below as line 0 | A watch without a before cannot say what changed |
| P7 | The previous revision is known, as the rollback target | `gcloud run revisions list --service nomadfinance-api --region asia-south1 --project nomadfinance-prod --limit 5` | Write the revision id in the log header. Read it **after** the last merge to `main` (NF-HR-005 and -006 deployed new revisions on 2026-10-13), so the rollback target is the one the watch starts from |
| P8 | Who is watching, and who is the second pair of eyes at night | Names in the log header | Three people, two time zones: agree it before T0 |

## Schedule

| From T0 | How often | Who |
|---|---|---|
| 0 to 4 h | Every 30 minutes | The person on watch |
| 4 to 24 h | Every 2 hours while awake; read the alert e-mail on waking | Whoever is up |
| 24 to 48 h | Morning, afternoon and evening, and on any alert | Whoever is up |

Alerts go to e-mail; an alert at night is read in the morning, and its time goes in the log. If nobody can read mail overnight, say so in the note: "no unacknowledged alert" then means "none seen".

## One check (about 5 minutes)

1. **The numbers.** From the repository root, for the time since the last check:

   ```bash
   python infra/monitoring/watch_report.py --window 2h
   ```

   PowerShell: `python infra/monitoring/watch_report.py --window 2h` is the same; it needs `gcloud` logged in with read access to `nomadfinance-prod`. Exit code `0` nothing crossed a threshold; `1` something did (each is named); `2` no request in the window, which is not healthy. Without `gcloud`, paste `--format=json` output from the Logs Explorer into `--stdin`.
2. **Incidents.** Cloud Monitoring, Alerting, Incidents: list the open ones, acknowledge each, and put its name and time in the log.
3. **Errors.** Logs Explorer, `resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api" AND severity>=ERROR`. A message you have not seen before is a finding: copy its `request_id`, find the other lines of that request, and decide with the table below.
4. **Quota.** Today's Gemini counts per model, from `gemini_usage/<day>` (the command is in `NF-HR-010-gemini-quota-guard.md`, "Commands"), against the limit in AI Studio's Rate limits page. The dashboard's *rolling 23.5 h* chart is the same number.
5. **Jobs.** `gcloud scheduler jobs list --project nomadfinance-prod --location asia-south1`: the five jobs (`coach-checkins`, `fib-recompute`, `scam-stats`, `refresh-rates`, `radar-aggregation`) are ENABLED with a recent, successful last attempt.
6. **People.** Anything a worker or a teammate reported since the last check: "cannot work out your score", "try again later", a wrong-language screen.

## What the numbers mean

| Signal | Normal | Watch (look again in 30 min) | Act |
|---|---|---|---|
| Server errors (5xx) share of a feature's requests, at least 20 requests | Under 1 % | 1 % to 5 % | Over 5 %: the alert fires. Find the route in the report; flag the module off if it is one module (`NF-HR-011`, rollback lever 1) |
| An ordinary route's p95 (`watch_report` *Slowest routes*) | Tens of milliseconds | Over 2 s | Over 2 s on two checks in a row: look at the logs of that route and at cold starts (a new instance takes about 8 s once, D-77) |
| A Gemini route's p95 (analyze, a Coach turn, plan, translation, PDF) | Seconds (analyze about 14 s, a plan 20 to 40 s) | Over 45 s | Over 30 s at the 95th percentile for 15 min: the latency alert fires. Check AI Studio status and *Gemini calls that gave up* |
| Gemini calls that gave up | A few `ai_busy` | A cluster of `ai_timeout` | Many in ten minutes: the quota is going, or the model is down |
| Refused by the daily budget | None | Any | The guard works as designed; check which feature, tell the team, and decide on the model or the key (`NF-HR-010`) |
| `4xx` | Mostly 401, 404 and 429 | A new 4xx on a route that had none | A `429` from the hourly scam limit or the per-minute limit is the limit working. A new `422` on a route is a client or contract bug |
| Cache hit rate (scam checks, plans) | Rises with traffic | Zero with repeated messages | Not an outage; a cost, so note it |

The thresholds are proposals made from NF-HR-007 and NF-HR-010 on a laptop with a stand-in model (Gemini 2 to 25 s). Change them with `--max-5xx-share`, `--max-p95-ms` and `--max-ai-p95-ms`, and write the change in the log.

## Stop and flag off

Taken from `NF-HR-011-release-v2.0.md` and kept here so the watcher does not need two pages:

- a server error on a module's routes that no `gemini_call_failed` or `gemini_budget_blocked` line with the same `request_id` explains;
- any error on a v1 route that began after the flags went on;
- the happy path fails, or a screen shows a stack trace, a blank page or the wrong language;
- a daily-limit alert, or a model near its limit with hours left in the day;
- more than a few workers saying "cannot work out your score" or "try again later" in 30 minutes.

**Flag off first** (Firestore `config/feature_flags`, `flags.<name>.enabled` = `false`, 60 s on the server and up to 60 s for an open page); then the previous Cloud Run revision (`gcloud run services update-traffic nomadfinance-api --to-revisions <previous>=100`, and `--to-latest` afterwards or no later deploy goes live); then the previous Hosting release. The commands are in `NF-HR-011-release-v2.0.md`, "Rollback".

## Triage: what to do with something new

| What you saw | Is it new? | Do | Record |
|---|---|---|---|
| An error message that has not appeared in the baseline (P6) | Yes | Find its `request_id`, read the whole request, decide: fix now (small, safe, tested), ticket, or ignore with a reason | A line in the log, and a note for anything not fixed |
| A `gemini_call_failed` with `ai_busy` or `ai_timeout` | Expected at some rate | Count it; act only past the table above | The count per window in the log |
| An alert | Yes | Acknowledge it, then triage as above | Name, time opened, time acknowledged, cause, what was done |
| A worker report | Maybe | Reproduce on the live site with a test account; if it is the module, treat as an error | Who, what, whether it reproduced |
| Something that is a v1.0 behaviour | Not new | Do not fix in this task | Out of scope, listed in the note |

A fix made during the watch goes through the normal pull request and the five required checks; it is not a reason to bypass the process, and it restarts the question "did the rollout change?" for the next window (note the revision id).

## The watch log

Fill one line per check. Line 0 is the baseline (P6). **Empty: nobody has watched yet.**

Header: T0 `____`, revision `____`, rollback target `____`, watchers `____`, flags at T0 `____`.

| # | Time (UTC) | By | Window | Requests | 5xx share (worst feature) | Slowest ordinary route p95 | Gemini gave up | Budget refused | Open incidents | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | | | | | | | | | | baseline |
| 1 | | | | | | | | | | |

## Ending the watch

The watch **passed** when, for 48 hours after T0: no incident went unacknowledged; no row of the table above reached "Act" without a recorded decision; no flag was turned off or revision rolled back for a reason that is still open; and every new finding has a line in the log and either a fix or a ticket.

Then fill in `docs/release-notes/v2.0.md`: the watch results, the incidents, what was found and the follow-ups, with the log attached or summarised. Open the pull request with the commit below, and tell Pranjal.

If the watch did **not** pass, say so in the same note; a failed watch with a clear cause is a result.

## Files

| File | Change |
|---|---|
| `infra/monitoring/watch_report.py` (new) | The numbers of a window, from the service's own log lines. Read-only; counts and timings only; path ids replaced |
| `infra/monitoring/service-alerts/server-errors.json`, `slow-requests.json` (new) | The two alert policies, with what to do in the notification |
| `infra/monitoring/render_policies.py`, `setup-monitoring.sh` | Make the service alerts with the same channels, even when no model has a limit |
| `backend/tests/unit/test_watch_report.py` (new), `test_monitoring_definitions.py` | The report on log fixtures and on a real request; the alerts' definitions |
| `docs/release-notes/v2.0.md` (new), this page | The note, the plan, D-318 to D-320 |

No shared file was touched (`package.json`, lockfile, `Dockerfile`, workflows, `firebase.json`, rules, `requirements*.txt`), no dependency was added, and nothing in production was read or changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | "No unacknowledged alert" with only a quota alert | Added the two alerts a rollout could actually trip. They are definitions; a person applies them with `setup-monitoring.sh` |
| 2 | Latency | From Cloud Run's own `request_latencies` for the alert (a 30 s p95 is a pathology alarm: Gemini timing out, a stuck instance), and from the log's `latency_ms` per route in the report (a 2 s limit for an ordinary route, 45 s for the six routes that wait for Gemini) |
| 3 | A 5 % server-error share | With a floor of 20 requests in 15 minutes, since a quiet service makes one failure of three look like 33 % |
| 4 | Reading production | Not done here. The report is for whoever watches; `gcloud` reads of `nomadfinance-prod` were refused to the earlier tasks and are the watcher's to run |
| 5 | The review note | Filled where the answer is already known (what shipped, how it was checked, production at release, ranked follow-ups); the watch sections are empty and marked |
| 6 | T0 | When the alerts exist and the flags are on for everyone, since production already had both on before this task |

## Checks run (2026-10-13)

| Check | Result |
|---|---|
| `black`, `ruff` (line length 100) on the report, the renderer and their tests | clean |
| `mypy --disallow-untyped-defs` on `watch_report.py` | clean |
| `pytest tests/unit/test_watch_report.py` | 14 passed: path ids removed, nearest-rank percentiles, counts by feature and class, Gemini failures, budget blocks and cache, thresholds (a share, a slow route, an AI route over its own limit, a budget block), no id in the output, the filter, the exit codes, and **a real request through the real middleware and JSON formatter** read by the report |
| `pytest tests/unit/test_monitoring_definitions.py` | 33 passed: 5 new for the alerts |
| `bash -n infra/monitoring/setup-monitoring.sh` | syntax ok |

**Not verified:** that Cloud Monitoring accepts the two new policy files as written (the same caveat as D-123: it is known only when `setup-monitoring.sh` has run), the report against the live project (`gcloud` read access to production), and, of course, the watch.

## Definition of Done

Documentation and DevOps (tracker): Markdown, consistent formatting, committed under `/docs`, no tool attribution: done. Reviewed by a teammate: pending (Pranjal).

Tracker "Done when":

- [ ] No unacknowledged alert for 48 hours: **not done: the watch has not been run**
- [x] The review note exists in `docs/release-notes/v2.0.md` (its known parts filled in; the watch sections are marked)
- [ ] Alerts created in the project and the watch log filled (D-318, D-319; limits D-320)

## Commit

Branch: `chore/NF-HR-017-ci-post-release-v2` (already checked out).

```bash
git commit -m "chore(release): add rollout watch plan, alerts and review note" -m "Refs: NF-HR-017"
```

PR title: `chore(release): rollout watch plan, error and latency alerts, and the v2.0 review note (NF-HR-017)`
