# NF-HR-007 — Performance and load profiling (v2): status and hand-over

**Status: partly done. Handed to Devam to finish.** The load harness and its first results are in the repo. The Lighthouse run is partial, the Firestore read review is not done, no concurrency change is proposed yet, and the acceptance report (`docs/evals/perf-v2.md`) is not written. This page says exactly what was run, what the numbers were, what they do not prove, and what is left.

Tracker row: "Lighthouse (PWA + performance ≥ 90 mobile), Locust run on analyze + coach SSE, Firestore read-count review, Cloud Run concurrency tuning." Acceptance: report in `docs/evals/perf-v2.md`; no endpoint p95 regression vs v1.0; top 3 findings fixed or ticketed.

## What is done

| Part | State |
|---|---|
| Load harness (`backend/tests/load/`) | Done, not yet linted or tested in CI form (see "Before this is committed") |
| Locust run, analyze + Coach SSE + v1 endpoints, 10 / 30 / 60 / 100 simulated workers | Done, 0 failures in every run |
| v1.0 vs v2 comparison on the v1 endpoints | Done, with one open point (compare, below) |
| Lighthouse (mobile) | **Partial**: 3 of 10 pages measured; see below |
| Firestore read-count review | **Not done**; the counter has a gap (below) |
| Cloud Run concurrency recommendation | **Not done**; only the inputs were measured |
| `docs/evals/perf-v2.md` | **Not written** |
| Fixes for findings | None made |

## The harness

Files: `backend/tests/load/{load_app.py, seed.py, locustfile.py, README.md}`. The README has the full run steps; this is the shape.

- **The API is the real app** (`create_app()`, real middleware, rate limiter, services, repositories, Firestore emulator, Auth emulator), started the way production starts it: one gunicorn `UvicornWorker`, `--timeout 0`.
- **Gemini is a stand-in that answers late**, with the latencies measured in NF-P4-003 (classify 2.0 s, explain 12 s, reassure 2.5 s, guard 1.0, extract 2.0, summarise 2.0, plan 25, translate 10, embedding 0.2; reply first token 1.2 s then 50 ms a piece). So the run measures what the service does while it waits (event loop, thread pool, Firestore, streams, PDF renderer), not Gemini. Production was never touched.
- **Workers**: `python -m tests.load.seed --users 120` creates `load-000…` in the emulators (refuses without emulator variables), each with 6 transfers, a demo plan and session, 5 scam checks, flags and rates.
- **Locust** (2.32.5, installed in a throwaway venv, not in `requirements-dev.txt`): `ScamUser` (analyze new / repeat, history), `CoachUser` (start session, SSE turn with "first token" and "complete" rows, session, overview, plan, plan PDF), `V1User` (compare, trends, savings, fib/income). `LOAD_SCENARIO` = `scam | coach | v1 | all`.
- **Rate limits** were raised by environment variable so 100 simulated workers are not refused by limits one worker would meet alone.
- **Reads** are counted per request (`X-Firestore-Reads`, `GET /__load/reads?reset=1`).
- **Between runs**: clear the Firestore emulator and seed again. A stopped run leaves Coach turns "running" for up to 90 s (`STALE_AFTER`), which makes the next run answer `409 turn_in_progress`.

## Results: load (2026-10-10, one laptop, 120 s per run, all scenarios mixed)

All runs: **0 failures**. Times in ms, p95 unless stated.

| Endpoint | 30 workers | 60 | 100 |
|---|---|---|---|
| `GET /remittance/savings` | 23 | 23 | 28 |
| `GET /remittance/trends` | 21 | 18 | 18 |
| `POST /remittance/compare` | 26 | 29 | 24 |
| `POST /fib/income` | 16 | 20 | 14 |
| `GET /scam/checks` | 29 | 43 | 32 |
| `POST /scam/analyze` (repeat, from cache) | 30 | 20 | 17 |
| `GET /coach/overview` | 22 | 27 | 26 |
| `POST /coach/sessions` (start) | 57 | 94 | 58 |
| `GET /coach/sessions/{id}` | 16 | 19 | 18 |
| `GET /coach/plans/{id}` | 32 | 26 | 25 |
| `GET /coach/plans/{id}.pdf` | 180 | 150 | 170 |

Gemini-bound paths (set by the stand-in, so they show the service adds nothing on top): Coach turn headers 2.0 s, first token 3.2 s, complete 4.5 s, flat from 30 to 100 workers. A new scam analysis takes 14 s (2 s classify + 12 s explain) at the p95 at every size; p50 falls to 4.5 s at 100 workers only because more of the sample is the benign path.

**Resources, one process:** CPU of one core, mean / max: 7.5 / 15 % (30 workers), 15 / 40 % (60), 16 / 39 % (100). Resident memory 219 to 231 MB against a 512 MiB limit, flat across the run. The service is nowhere near CPU- or memory-bound with Gemini taking its measured time.

## Results: v1.0 against v2 on the v1 endpoints

v1.0 is `main` before PR #108 (commit `6117b4f9`), exported with `git archive` and run on the same machine, same seeds, same mix, 90 s, 30 and 60 workers. Threshold in the plan: +10 % on p95.

| Endpoint (p95 ms) | v1.0 @30 | v2 @30 | v1.0 @30 (repeat) | v2 @30 (repeat) | v1.0 @60 | v2 @60 |
|---|---|---|---|---|---|---|
| `GET /remittance/savings` | 28 | 24 | 26 | 26 | 29 | 30 |
| `GET /remittance/trends` | 19 | 20 | 19 | 20 | 20 | 20 |
| `POST /fib/income` | 26 | 20 | 19 | 17 | 20 | 19 |
| `POST /remittance/compare` | 27 | 38 | 30 | 33 | 30 | 32 |

**Open point: `POST /remittance/compare`.** Its p95 is higher in v2 in all three pairs: +11 ms (+41 %), +3 ms (+10 %) and +2 ms (+7 %). The other three are equal or better. In absolute terms this is below the noise of a laptop (the first pair's v1.0 p99 was 480 to 550 ms from warm-up alone), so this is **not shown to be a regression, and not shown not to be one**. It needs a quieter machine or a longer run (5 minutes, 3 repeats) and a look at what v2 added on that path. Do not write "no regression" in the report for this endpoint until that is done. Also note the "+10 %" rule on 20 to 30 ms figures is finer than the machine can resolve; the report should give absolute milliseconds beside the percentage.

## Results: Lighthouse (mobile preset, signed in as a seeded worker, production build in emulator mode)

Build: `VITE_API_BASE_URL=http://127.0.0.1:8080 pnpm exec vite build --mode emulator` (precache 133 entries, 2,716 KiB), served by a static server with gzip and immutable caching on `/assets`. Lighthouse 12.6.1, cold = service worker and caches cleared, still signed in.

| Page | Performance | Accessibility | Best practices | SEO | FCP | LCP | TBT | CLS |
|---|---|---|---|---|---|---|---|---|
| `/dashboard` | **89** | 94 | 100 | 100 | 2.3 s | 3.4 s | 80 ms | 0.051 |
| `/remittance` | 93 | 100 | 100 | 100 | 2.3 s | 2.9 s | 60 ms | 0.006 |
| `/contract` | **78** | 100 | 100 | 100 | 2.3 s | 5.2 s | 60 ms | 0.006 |
| `/radar`, `/identity`, `/scam-check`, `/scam-check/history`, `/coach`, `/coach/plan/:id` | **not measured** | | | | | | | |

What this says and does not say:

- **Below the ≥ 90 target so far:** the dashboard (89, by one point; LCP 3.4 s and CLS 0.051, the accessibility 94 is a separate finding) and the contract page (78, LCP 5.2 s). Both need a look at what is the largest element and what blocks it.
- **Warm (repeat) view of the dashboard** scored 100 with "FCP 0.0 s". That figure is an artefact: the service worker serves the app from its precache, so Lighthouse's network simulation sees no request. It shows the shell is cached; it is not a speed claim.
- **Every signed-in run carries the warning "the page loaded too slowly to finish within the time limit"**: the page never reaches network idle, so Lighthouse waits out its limit. That is probably a request that stays open (a poll, a stream or a listener) and is worth finding: it also lengthens each run to about 90 s. The cause was not identified.
- **Two measurement mistakes to avoid** (both cost time here): (1) Lighthouse's `--port` silently launches its own unsigned Chrome if nothing is listening on that port, and then every page is the landing page; start Chromium yourself with `--remote-debugging-port=9333 --user-data-dir=<dir>` (not through Playwright's pipe) and confirm `curl 127.0.0.1:9333/json/version` before the run. (2) `--max-wait-for-load` below the default (15 s was tried) makes these pages fail with `NO_NAVSTART` (score 0); leave the default.
- **PWA installability** was seen working (the install prompt shows in the app) but the Lighthouse PWA audit set, offline reload and the manifest were not run. Lighthouse 12 no longer has a PWA category, so use the installability audits and a manual offline check.
- Signing in for the run: the Auth emulator token is written to the page's IndexedDB (`firebaseLocalStorageDb`, key `firebase:authUser:<apiKey>:[DEFAULT]`) and `nomadfinance.tour.v2.<uid>` is set to `seen` so the first-run tour does not cover the page.

## Results: Firestore reads (partial, with a gap)

Per request, from the counter, v2 run at 60 workers:

| Route | Documents read (mean / max) |
|---|---|
| `GET /coach/overview` | 2 / 2 in the run (1 when probed once) |
| `GET /scam/checks` | 8.7 / 14 |
| `POST /coach/sessions` (start) | 6 / 6 |

**These are not complete.** The counter patches `Client.get_all`, `Query.stream` and `AggregationQuery.get`. It reports **0** for `GET /coach/plans/{id}` and `GET /coach/sessions/{id}`, and about 0 for `POST /scam/analyze` and `POST …/messages`, which cannot be true (each reads at least one document). A probe of the plan route returned `x-firestore-reads: 0`. So some read path does not go through those three methods (the plan and session reads in `CoachPlanRepository` / `CoachSessionRepository` were being checked when this stopped). Until that is found, only the three rows above are usable, and the review of reads per screen is not done. Next step: print which client method `CoachPlanRepository.get` calls, patch it in `_install_counters`, and rerun `GET /__load/reads`.

## Findings so far (candidates for the report's top three)

1. **Starting a Coach session may contend in production as it does in the emulator (unverified).** `CoachSessionRepository.create_or_resume` runs a query inside a transaction. In the Firestore emulator that makes different workers' sessions contend: 2 at once take 2 s, 10 take 30 s and fail with 409 (`SessionContentionError`); reading a document in a transaction does not. Production Firestore is not known to behave that way, but it was **not verified**. The harness replaces the method with a non-transactional equivalent (same reads and writes) so the rest of the path could be measured; set `LOAD_KEEP_SESSION_TRANSACTION=1` to run the real one. To close it: run 10 simultaneous session starts for 10 demo accounts against the real database, or use a deterministic id for the active session and read it by id. Ticket D-273.
2. **The plan PDF costs 150 to 180 ms at the p95** on the first render in a single process (it is stored after the first render, so repeats are cheap). It blocks nothing else in the measured runs, but on 1 vCPU it is the largest single CPU item on the Coach path. Not ticketed yet.
3. **Cold start and the instance shape.** The first request on a new instance took 8.4 s (NF-P4-003, D-77); the Cloud Run service is 1 vCPU, 512 MiB, concurrency 80 (default), max 2 instances. The measured load is far below that: 40 % of one core and 230 MB at 100 simulated workers, but with a stand-in Gemini; real Gemini adds client-side waiting, not CPU. This points to **concurrency 80 being safe to keep and `min-instances` being the lever that matters for the demo**, but the recommendation is not written and no deploy file was changed.
4. **Dashboard and contract page below 90 mobile** (above).
5. **`POST /remittance/compare` p95 higher in v2** (open point above).

## Not done, in order, for Devam

1. Find the read path the counter misses (above), then recount reads per route and write the per-screen read review. Include the NF-HR-001 signal reads in the per-worker cost.
2. Finish Lighthouse: `/radar`, `/identity`, `/scam-check`, `/scam-check/history`, `/coach`, `/coach/plan/:id` (cold, default wait), plus a manual offline reload and the installability audits. Look at the LCP element on `/contract` and `/dashboard`; fix if small, ticket if not.
3. Rerun compare for v1.0 against v2 at 5 minutes and 3 repeats before writing a verdict.
4. Verify finding 1 against the real database (demo accounts only), or ticket it as written.
5. Write the Cloud Run recommendation: concurrency, `--min-instances`, `--max-instances`, memory. **Do not edit `backend/scripts/deploy_manual.sh`** before showing the exact diff and getting an OK (shared-file rule).
6. Write `docs/evals/perf-v2.md` (v1.0 against v2 tables, Lighthouse table, reads, top three findings fixed or ticketed) and tick the acceptance row.

## Before this is committed

On 2026-10-10, `black --check tests/load` and `ruff check tests/load` pass. CI runs `mypy app` and `mypy --strict app/services`, not the tests, so `tests/load` is outside mypy; running mypy on it directly reports unused-`type: ignore` and similar notes (20 in 3 files), which CI does not see. The full chain (`mypy app`, `mypy --strict app/services`, `pytest`) was **not** re-run on this branch after the last edits; run it from `backend/` before committing. No shared file was touched and no dependency was added; Locust is installed outside the repo.

Branch: `test/NF-HR-007-test-performance-v2` (already checked out). Suggested commit message when the report is ready:

```
test(perf): add load harness and v2 performance profiling runbook
Refs: NF-HR-007
```

The header is 65 characters (the limit is 72). If the harness is committed before the report, the same message works with the task still open.
