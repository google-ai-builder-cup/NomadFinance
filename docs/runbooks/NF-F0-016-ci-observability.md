# NF-F0-016 — Observability: log fields, metrics, dashboard, daily-limit alerts

## Summary

Every log line of a request now carries the same three fields (`request_id`, `uid_hash`, `feature`). Five log-based metrics turn those lines into per-feature counts of requests, errors, Gemini requests, Gemini failures and tokens. One dashboard charts them, and one alert per Gemini model fires when this service has used 80% of that model's daily request limit.

**Production only.** The tracker says "on staging"; staging was dropped (`NF-F0-011-ci-staging-env.md`, D-121).

**What is built and what is not:** the code, the definitions and their tests are done. **Nothing exists in the Google project yet.** A project owner has to run one script (D-122), and two numbers have to be read in Google AI Studio first. The two acceptance lines (the dashboard shows the charts; a forced breach fires the alert) can only be confirmed after that.

## The standard log fields

| Field | On | Meaning |
|---|---|---|
| `request_id` | every line of a request | Unchanged (NF-P1-028) |
| `uid_hash` | lines after sign-in | The 16-hex hash of the uid. **Renamed from `user_hash`** to match the tracker. Nothing queried the old name |
| `feature` | every line of a request, and Gemini lines | `contract`, `remittance`, `radar`, `fib`, `coach`, `scam`, or `platform` |
| `status_class` | `request_completed` | `2xx`, `4xx` or `5xx` |

`feature` comes from the request path (`backend/app/core/features.py`): `/api/v1/contracts/...` is `contract`, `/api/v2/scam/...` is `scam`, and a Cloud Scheduler job takes its pillar (`refresh-rates` is `remittance`). Everything else (`/health`, `/api/v2/flags`, `/api/v1/users/me`) is `platform`. A Gemini line names its own feature from its operation (`contract.detect` is `contract`), which wins, so a request and its Gemini calls agree. A test lists the only routes that are `platform` on purpose, so a new pillar route that is not mapped is caught.

**Every Gemini request now leaves exactly one line**, which the quota count depends on:

| Line | When | Before this task |
|---|---|---|
| `gemini_call` | an answered call | existed |
| `gemini_call_failed` | a call that gave up, or was cancelled or closed | existed; now also for embeddings |
| `gemini_retry` | an attempt that failed and will be tried again | existed, but carried no model or feature; now it carries the same `gemini_usage` identity as the others, and embeddings log it too |

The number of those three lines for a model is the number of requests Google counted against it. A test (`test_gemini_request_accounting.py`) keeps that true for success, retries and giving up, for chat and for embeddings.

## The metrics

Defined in `infra/monitoring/metrics/`, one file each, all filtered to the `nomadfinance-api` Cloud Run service.

| Metric | Type | Counts | Labels |
|---|---|---|---|
| `nf_http_requests` | counter | one per `request_completed` | `feature`, `status_class` |
| `nf_gemini_requests` | counter | every Gemini request: answered, gave up, retried, cancelled, closed, embedding | `model`, `feature` |
| `nf_gemini_failures` | counter | calls that gave up after every attempt (not cancelled, not closed) | `model`, `feature`, `error` |
| `nf_gemini_tokens_in` | distribution | prompt tokens per answered call | `model`, `feature` |
| `nf_gemini_tokens_out` | distribution | answer plus thinking tokens per answered call | `model`, `feature` |

**A log-based metric only counts lines written after it exists.** Nothing is back-filled, and a chart is empty until the first matching line arrives.

## The dashboard

`infra/monitoring/dashboard.json`, titled *NomadFinance: requests, errors and Gemini usage*. Per-feature charts of requests, server errors (5xx) and client errors (4xx); Gemini requests per model and per feature; Gemini failures per feature and error class; a rolling 23.5-hour count per model (the number the alert watches); prompt and answer-plus-thinking tokens per feature, as totals and as the mean per call.

## The daily-limit alert

One policy per model, *"Gemini daily limit 80%: <model>"*, from `infra/monitoring/alert-policy.template.json` and `quota-limits.json`. It fires when `nf_gemini_requests` for that model, summed over a rolling 23.5 hours, goes above 80% of the model's `rpd`, rounded down, and emails the channels. The alert text says what to do.

**What the count is, and is not:**

- It is **this service's** requests, counted from its logs, retries included. The AI Studio key lives in Google's own project (`infra/iam/service-accounts.md`), so Google's usage figure is not available in `nomadfinance-prod`'s monitoring.
- It leaves out other users of the same key (live-Gemini tests, scripts, a teammate's laptop).
- A rolling 23.5 hours is not Google's day, which ends at midnight Pacific. It over-counts just after a reset, so it errs towards alerting early. Treat the alert as a prompt to open AI Studio's Rate limits page, which is the real figure.
- The limits are **not in the repository**: ADR-002 says they are "only shown in AI Studio", and the numbers in the original design are for models that no longer exist.

## One-time setup (D-122)

A project owner, with `gcloud` logged in, `curl` and `python3`.

**1. Fill in the limits.** In Google AI Studio, Rate limits page (for the project that owns the `GEMINI_API_KEY`), read the requests-per-day for the four models and put them in `infra/monitoring/quota-limits.json` as whole numbers. Keep the model ids in step with `GEMINI_MODEL_*`; a test fails if the file and `app/config.py` disagree. A model left `null` gets no alert.

**2. Run the script** from the repository root. It is safe to run again: metrics are updated in place, and the dashboard and alerts are replaced.

```bash
ALERT_EMAILS="first@example.com,second@example.com,third@example.com" bash infra/monitoring/setup-monitoring.sh
```

Try it first without changing anything:

```bash
DRY_RUN=1 ALERT_EMAILS="first@example.com" bash infra/monitoring/setup-monitoring.sh
```

Expected: sections 1 to 4, with each metric `created`, the dashboard created, a channel per address, and an alert per model with a limit. A model without one is named as `SKIPPED` and the script ends with exit code 3, so a half-done run cannot pass for a finished one. PowerShell: run the script from Git Bash, or run its `gcloud` commands by hand (they are listed in the file).

The person running it needs `roles/logging.configWriter` and `roles/monitoring.editor`, or the project owner role. Addresses are passed on the command line and are never committed.

**3. Check the dashboard.** Open it from the link the script prints, generate some traffic (sign in, call any pillar endpoint), wait about two minutes, and confirm the request charts show the feature. The Gemini and token charts fill when an endpoint that calls Gemini is used.

**4. Forced-breach test** (the tracker's second acceptance line). Make the alert fire on purpose, then put it back:

1. In `quota-limits.json` set `rpd` of `gemini-3.1-flash-lite` (the classification model, used by `POST /api/v1/fib/categorize`) to `2`. The threshold becomes 1.
2. Run the script again.
3. Make two requests that call that model through the deployed API (two categorizations), so `nf_gemini_requests` for it goes above 1.
4. Within a few minutes an incident opens in Monitoring → Alerting and each address gets an email.
5. Put the real `rpd` back and run the script again, which replaces the test policy. **Do not leave the test threshold in place.**

**NF-HR-010 reads this file too.** `quota-limits.json` is also the source of the backend's per-feature daily budget: `infra/monitoring/rpd_env.py` turns each `rpd` into `GEMINI_RPD_<TIER>`, which `backend/scripts/deploy_manual.sh` sets on the Cloud Run service. Filling in the numbers (D-122) therefore also switches the budget guard on at the next deploy. See `docs/runbooks/NF-HR-010-gemini-quota-guard.md`.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | `user_hash` renamed `uid_hash`, no alias. | The tracker's name. No query, dashboard or document depended on the old one beyond this runbook set and two tests. |
| 2 | `feature` is set from the path by the middleware, and a Gemini line's own feature wins. | Requests and their Gemini calls can then be added up per feature without a join. |
| 3 | Counting the quota from our own logs, retries included, not from Google's quota metrics. | Google's figures live in a project we cannot see. This is an approximation, stated above. |
| 4 | One alert per model. | Limits are per model (ADR-002), and a single combined count would hide which one is near. |
| 5 | Email channel, addresses given at run time. | Slack needs an interactive sign-in in the console, so it cannot be scripted. The team's addresses are personal data and stay out of the repository. |
| 6 | Notification channels are created with the Monitoring REST API through `curl`. | `gcloud monitoring channels` exists only in the `alpha` component, which is not installed by default. |
| 7 | One script, run by hand; no deploy workflow. | Workflows are shared files, and these resources change rarely. The files in `infra/monitoring/` are the source of truth. |
| 8 | The dashboard and the alerts are replaced on a re-run, not edited in place. | Replacing needs no etag handling. Incident history belongs to the old policy. |

## What was verified

| Check | Result |
|---|---|
| Backend `pytest` | 1,343 passed, 69 skipped (the emulator and live-Gemini tests); it was 1,277 |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| The metric filters and label extractors, run by a small evaluator against the real log lines (the real middleware and the real Gemini client, formatted by the real `JsonFormatter`) | Each metric matches exactly the lines it is for; every label has a value; the request count equals the requests made |
| The three tests that matter, broken on purpose | Dropping the retry lines from `nf_gemini_requests`, renaming the `status_class` field, and dropping the `outcome="failed"` clause were each caught (the last one only after a cancelled and a closed call were added to the test data) |
| The dashboard | Every metric and label it uses exists; the five charts the tracker names are present |
| The alert renderer | 80% rounded down; a `null` limit is skipped and named, never given a made-up number; a zero, negative, fractional, string or boolean limit is refused; no placeholder is left in a policy |
| `setup-monitoring.sh` | `bash -n` clean; a dry run against a made-up project name shows every step, and the skipped alerts end with exit code 3 |
| `gcloud` syntax | `--config-from-file` (metrics, dashboards) and `--policy-from-file` (policies) confirmed in `gcloud --help` for 586.0.0 |

**Not verified, because it needs the project:** that Google accepts each file; that the two total-token charts (they use the Prometheus-style names `logging_googleapis_com:user_<metric>_sum`) show data, with the mean-tokens-per-call charts as the standard-form fallback; that a 23.5-hour alert window is allowed; that the dashboard shows real traffic; that the alert emails arrive (D-122, D-123).

## Cost

User-defined log-based metrics are chargeable beyond Cloud Monitoring's free monthly allowance, based on the metric data and the number of series. At a few hundred requests a day and a handful of labels this is expected to be negligible, but it has not been checked against a bill.

## Definition of Done

- [x] Standard structured-log fields (`feature`, `request_id`, `uid_hash`), tested
- [x] Log-based metrics for Gemini calls and errors per feature: defined and tested against the real log lines
- [x] Dashboard definition with per-feature request, error and token charts
- [x] Alert definition at 80% of the daily limit per model
- [ ] Dashboard shows the charts **in the project**: not done, needs D-122
- [ ] A forced quota breach fires the alert to the team channel: not done, needs D-122 and the test above
- [ ] The real daily limits filled in: not done, only Google AI Studio has them
- [ ] Reviewed by a teammate

## Commit

Branch: `chore/NF-F0-016-ci-observability`.

```bash
git commit -m "feat(observability): add log fields, metrics, dashboard and quota alerts" -m "Refs: NF-F0-016"
```

PR title: `feat(observability): log fields, metrics, dashboard and Gemini quota alerts (NF-F0-016)`

## Noticed, not fixed

- `docs/runbooks/NF-P1-028-structured-logging.md` is updated for the new fields. `NF-P1-004` and `NF-F0-007` runbooks describe `gemini_usage` and are still correct.
- `backend/app/core/` and `/infra/` are code-owner paths: this change needs a teammate's review.
- Cloud Scheduler jobs that call the Gemini-using cron endpoints are counted under their pillar's feature, which is right for cost but means `platform` never includes Gemini spend.
