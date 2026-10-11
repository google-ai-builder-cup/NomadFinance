# NF-HR-010 — Gemini quota and cost guard

## Summary

Every Gemini model has one daily request quota that all features and all workers share. Before this task a run of Coach plans could use up the reasoning model for everyone, a daily 429 was retried three times on every call (each retry is a request against the quota that is already gone), and a spent day looked like a busy minute to the worker.

Now the backend keeps a **daily budget per feature and model tier**, refuses a request that is over its share (or that Google has already refused for the day) before it is sent, and answers the worker with the usual `503 ai_busy`, a `Retry-After` of the seconds until the quota is back, and words that say "later", not "in a minute". The scam explainer already falls back from the reasoning to the fast tier on this error, so a Scam check still gets an explainer when only the reasoning share is gone.

Around that: the routing is reviewed against the daily limits with a measured, re-runnable projection (`backend/scripts/project_demo_usage.py`); the cache hit rate is measurable (a metric and a dashboard chart) and one uncached call is cached; and the demo-day pre-warm plan is written below.

**What is built and what is not.** The code, the tests and the definitions are done. **The budget is off in production until someone reads each model's real daily limit in Google AI Studio** and puts it in `infra/monitoring/quota-limits.json` (D-122, which also arms the NF-F0-016 alerts). Nothing here invents a limit. The "projected usage under 60% of the daily limit" line is met against the design document's figures, marked ASSUMED, and is confirmed only when the real numbers are in (D-286).

## Where everything is

| What | Where |
|---|---|
| The budget, the shares, the Pacific quota day | `backend/app/integrations/gemini/budget.py` |
| The error (`GeminiBudgetExhaustedError`, a rate-limit error) and `is_retryable` | `backend/app/integrations/gemini/errors.py` |
| Every request goes through the budget: calls, streams, embeddings | `client.py`, `conversation.py`, `embeddings.py` in the same folder |
| The 503 answer: message and `Retry-After` | `backend/app/core/errors.py` |
| The daily counts, shared by all instances | `backend/app/repositories/gemini_usage_repo.py`, Firestore `gemini_usage/{day}` |
| Settings `GEMINI_RPD_REASONING`, `_EXTRACTION`, `_CLASSIFICATION`, `_EMBEDDING` | `backend/app/config.py`, `backend/.env.example` |
| Limits file to settings, at deploy time | `infra/monitoring/rpd_env.py`, `backend/scripts/deploy_manual.sh` |
| Cache: the small TTL cache, the hit/miss log line, the recommendation cache | `backend/app/core/cache.py`, `backend/app/services/remittance/recommender.py` |
| Metrics `nf_gemini_budget_blocks`, `nf_cache_lookups` and two dashboard charts | `infra/monitoring/` |
| The projection | `backend/scripts/project_demo_usage.py` |
| Collection doc | `docs/data-model/collections/gemini_usage.md` |

## How it behaves

1. A request to Gemini (each attempt, retries included, because Google counts them) asks the budget first: `budget.attempt(feature, tier)`.
2. **Refused with `source: google`** if Google answered a per-day 429 for that tier's model earlier today (this instance, or any other: it is written to `gemini_usage/{day}.exhausted`). The request is not sent.
3. **Refused with `source: budget`** if the feature has already sent its share of the tier's daily limit. A share is `SHARES[tier][feature]` times `GEMINI_RPD_<TIER>`, rounded down, at least 1. A feature missing from the table gets 5%. The shares leave 5 to 20% of each model free for retries, other users of the key and what is not listed.
4. Otherwise the request is counted (`gemini_usage/{day}.calls.<feature>.<tier>`, a server-side increment) and sent. If Google then answers a per-day 429, the tier is closed for the rest of the day and the call is **not retried** (before: three attempts).
5. A refusal never reaches Google, so it writes no `gemini_call_failed` line and is not counted by `nf_gemini_requests`; it writes `gemini_budget_blocked`, which `nf_gemini_budget_blocks` counts.
6. The worker gets `503 ai_busy` (v1 routes: `{"detail": ...}`), `Retry-After: <seconds to midnight Pacific>`, and "The AI service has reached its limit for today. Please try again later." The frontend shows its `ai_busy` text and a Try again button; pressing it costs nothing (D-288).

What the features do with it, with no change of their own:

| Feature | When its share or the model is spent |
|---|---|
| Scam Analyzer, reasoning tier | The explainer is written on the fast tier instead (`explainer.py` falls back on any rate-limit error). The worker still gets verdict and explainer |
| Scam Analyzer, fast tier | `503 ai_busy`: no verdict can be made. A message checked before is still answered from the stored check, with no Gemini call |
| Coach turn (reply, extraction) | `503 ai_busy` before any piece, or an `error` event; the session is intact and the same `Idempotency-Key` works after the reset |
| Coach plan | `503 ai_busy`; nothing is stored; the answers stay confirmed |
| Contract complaint letter | The existing `complaint_pending_reason: ai_daily_limit` ("comes back tomorrow") |

**Fail-open.** The budget must never be the reason a request fails: a Firestore error, a missing credential or a store call over 2 seconds is logged (`gemini_budget_store_unavailable`) and the instance goes on with its own count.

## Firestore, Firebase and Google Cloud: what changed and what did not

| Area | Change | Action for a person |
|---|---|---|
| Firestore | New collection `gemini_usage/{YYYY-MM-DD}` (backend only). No index (documents are read by id). No TTL (a few hundred bytes a day; the history is useful). | None. Created by the first counted request |
| `frontend/firestore.rules` | **Comment only.** Nothing matches `gemini_usage`, so it is denied to browsers by default. Rules tests (181) pass and now name the collection | None. The rules deploy workflow runs on merge; the content is unchanged |
| `firestore.indexes.json`, `firebase.json`, `storage.rules` | Unchanged | None |
| Firebase Auth, Hosting, Storage | Unchanged | None |
| IAM | Unchanged. The runtime account has `roles/datastore.user` on the project, which covers `gemini_usage` | None |
| Secret Manager | Unchanged. The limits are numbers, not secrets, and come from a file in the repository | None |
| Cloud Run | `deploy_manual.sh` now appends `GEMINI_RPD_*` to `--set-env-vars` (that flag **replaces** every variable, so a limit set by hand would be wiped by the next deploy). `--min-instances 0` and `--max-instances 2` are untouched (D-77 is still a decision) | After D-122: run the **Backend deploy** workflow by hand (see the gotcha below) |
| Cloud Monitoring | Two new log-based metrics and two charts. No new alert: the NF-F0-016 alert at 80% of the limit is the early warning | Re-run `infra/monitoring/setup-monitoring.sh` once (safe to repeat) |
| Cloud Scheduler | Unchanged. No warm-up job: it would run every day for ever once merged | None |
| GitHub Actions | Unchanged (shared files) | See the gotcha |

**Gotcha: `backend-deploy.yml` only runs when `backend/**` changes**, so editing `infra/monitoring/quota-limits.json` alone does not redeploy and the guard stays off. After filling in the limits, run **Actions → Backend deploy → Run workflow**. (Adding `infra/monitoring/quota-limits.json` to that workflow's `paths:` would make it automatic; it is a shared file, so it is proposed here and not done.)

## The routing, checked against the limits

Every Gemini request the app can make (the left columns are checked against the code by `tests/integration/api/test_gemini_journey_counts.py`):

| Feature | Operation | Tier | Model (default) | Per journey |
|---|---|---|---|---|
| coach | `coach.reply` | classification (setting) | gemini-3.1-flash-lite | 1 + one per text turn (11.7 turns on average) |
| coach | `coach.extract` / `coach.review` | classification (setting) | gemini-3.1-flash-lite | one per text turn |
| coach | `coach.guard` | classification (setting) | gemini-3.1-flash-lite | 0.25: only for the 3 of 140 persona messages the rules cannot judge |
| coach | `coach.summarise` | classification | gemini-3.1-flash-lite | 0.3: only once the 24-turn history is passed |
| coach | `coach.plan` | **reasoning** (setting) | gemini-3.5-flash | 1.33 (a third of first answers were rejected, D-220) |
| coach | `coach.translate_plan` | classification (setting) | gemini-3.1-flash-lite | 0.8 (8 of 12 personas read the plan in another language) |
| scam | `scam.classify` | classification | gemini-3.1-flash-lite | 1 |
| scam | `scam.explain` | **reasoning**, falls back to classification | gemini-3.5-flash | 1 per scam |
| scam | `scam.reassure` | classification | gemini-3.1-flash-lite | 1 per message that is not a scam |
| scam | `scam.embed` | embedding | gemini-embedding-001 | 1 per new message |
| scam | `scam.read_screenshot` | extraction | gemini-3.5-flash-lite | 1 per screenshot |
| contract | detect, extract | extraction | gemini-3.5-flash-lite | 1 each |
| contract | compare, complaint | **reasoning** | gemini-3.5-flash | 1 each |
| contract | translate | classification | gemini-3.1-flash-lite | 0.67 |
| radar | `radar.extract_entity` | extraction | gemini-3.5-flash-lite | 1 per report |
| radar | `radar.validate`, `radar.categorize` | classification | gemini-3.1-flash-lite | 1 each per report |
| radar | `radar.embed` | embedding | gemini-embedding-001 | 1 per report |
| radar | `radar.alert_notification` | classification | gemini-3.1-flash-lite | 2 (up to six languages for each new alert) |
| fib | `fib.extract_bill` | extraction | gemini-3.5-flash-lite | 1 per bill |
| fib | `fib.categorize` | classification | gemini-3.1-flash-lite | 1 per batch of entries |
| fib | `fib.synthesize_narrative` | **reasoning** | gemini-3.5-flash | 1 per profile update (weekly job) |
| remittance | `remittance.recommend` | classification | gemini-3.1-flash-lite | 1 per new comparison (cached 30 minutes) |

**Findings.**

- The reasoning tier, which the design called the bottleneck, is not: a Coach interview is 1.3 requests on it. The Coach's demand is on the **fast tier**: the reply and the slot extraction each run once per turn, about 26 requests an interview.
- The Coach reply is already on the cheapest tier. **Decision (design 11, question 4): it stays there.** The lever kept ready is `GEMINI_COACH_REPLY_TIER=extraction`, which moves the reply to the second Flash-Lite model and its own daily quota (D-287: not yet timed).
- A scam message is cached per worker (NF-SA-012, design question 3), a Coach plan by its answers, a contract analysis by its content hash and the law version; `remittance.recommend` was the one common call with no cache at all.

## The demo-day projection

```bash
# from backend/ (the figures marked ASSUMED are the design document's: 500 / 1500 / 1500 / 1500)
python scripts/project_demo_usage.py                                 # 30 visitors, default routing
python scripts/project_demo_usage.py --visitors 20
python scripts/project_demo_usage.py --coach-reply-tier extraction   # 30 visitors, reply moved
python scripts/project_demo_usage.py --rpd reasoning=500 --rpd classification=1000   # real figures
```

The scenario (editable by flags; the assumptions are the first lines of the output): 3 rehearsals and 1 live run of the whole worker journey (Coach, Contract Shield, three scam checks, a Radar report, two comparisons, a Financial Identity update; the team's scam checks are the NF-HR-003 seeds, so cache hits); 30 visitors who each run one Coach interview, three new scam checks (two scams), half of them one contract, and one comparison (half cache hits); retries add 10%.

| Routing, 30 visitors | reasoning | extraction | classification | embedding |
|---|---:|---:|---:|---:|
| Default (reply on classification) | 162 (32%) | 60 (4%) | **1,150 (77%)** | 103 (7%) |
| Reply on extraction | 162 (32%) | 534 (36%) | 676 (45%) | 103 (7%) |

(Shares of the ASSUMED limits.) **Result:** the default routing stays under 60% of every model up to **22 visitors who run their own interview**; with the reply on the second Flash-Lite model, up to **39**. The per-feature budgets are sized to the same numbers, so the guard does not refuse anything inside those limits (the output's second table). Beyond them the guard does what it is for: the Coach is the one cut off, with a calm "try later", and the Scam Analyzer, Contract Shield and Radar keep working. A visitor who opens a seeded demo worker instead of starting an interview costs nothing.

## Cache

| Cache | Where | Hit means | Added by this task |
|---|---|---|---|
| Stored scam checks | Firestore, per worker, 90 days | verdict and explainer without a call (1 to 3 requests saved) | the hit/miss line |
| Coach plan | Firestore, by the answers' hash | 1 to 3 requests saved | the hit/miss line |
| Contract analysis | Firestore, by content hash, law and prompt versions | 4 to 6 requests saved | the hit/miss line |
| Remittance recommendation | memory, per instance, 30 minutes, 256 entries | 1 request saved | **the cache itself** (input holds no worker data; the checks run on a cached answer too; a bad answer is not kept) |

Every lookup writes `cache_lookup feature=… name=… result=hit|miss`, counted by `nf_cache_lookups` and charted per feature; the hit rate is hits over hits plus misses. A shared scam cache stays out (decided per worker, design question 3).

## Demo-day pre-warm plan

1. **A week before.** Read each model's requests per day in AI Studio (Rate limits). Fill `infra/monitoring/quota-limits.json` (D-122). Merge, then **run the Backend deploy workflow by hand**. Run `setup-monitoring.sh` and the forced-breach test of NF-F0-016. Run `python backend/scripts/project_demo_usage.py`: it must print no ASSUMED and no OVER, or you change the visitor cap or the routing (D-286). If the reply moves to `extraction`, time it first (D-287).
2. **Two days before.** Reseed the demo workers (D-271): their scam checks and plans make the team's runs cache hits (NF-HR-003 tests this). Decide whether visitors start interviews or open the seeded workers.
3. **The evening before.** `gcloud run services update nomadfinance-api --min-instances 1 --region asia-south1 --project nomadfinance-prod` (D-77: removes the 8 s first request; billed while idle). **A deploy after this resets it to 0** (`deploy_manual.sh` passes `--min-instances 0`), so freeze deploys. Run the whole journey once with the demo workers and check `/health`. Recommendations are cached for 30 minutes only: repeat the two comparisons shortly before the demo.
4. **The morning.** Note the reset time: Google's day turns at midnight Pacific, which is **12:30 IST** until 1 November and **13:30 IST** after (16:00 in Singapore). Rehearse before the reset, then present after it, so the live run has a fresh day. Read today's counts (below) and AI Studio's usage page.
5. **During.** Watch the three charts: Gemini requests per model, refused requests, cache lookups. A refusal on the screen means a feature has used its share: stop visitor interviews, keep the live run going. The fallback is the backup recording (NF-HR-016).
6. **After.** Put `--min-instances` back to 0 (`gcloud run services update … --min-instances 0`).

## Commands

```bash
# The simulated exhaustion in both features (no emulator, no key):
cd backend && pytest tests/integration/api/test_quota_exhaustion.py -v
# Through the real wiring with Firestore: the counts, two instances, a daily 429 closing a model.
# PowerShell:  $env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID="demo-nomadfinance"
# bash:        export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance
#   (emulators: from frontend/, firebase emulators:start --only auth,firestore,storage --project demo-nomadfinance)
pytest tests/integration/api/test_quota_exhaustion_firestore.py tests/integration/repositories/test_gemini_usage_repository.py -v
# Today's counts in production (application default credentials for the project):
python -c "from datetime import UTC, datetime; from app.integrations.gemini.budget import budget_day; from app.repositories.base import get_firestore_client as c; d=budget_day(datetime.now(UTC)); print(d, c().collection('gemini_usage').document(d).get().to_dict())"
# Switch the guard off at once (a new revision; the next deploy puts the limits back unless quota-limits.json is changed):
gcloud run services update nomadfinance-api --project nomadfinance-prod --region asia-south1 --remove-env-vars GEMINI_RPD_REASONING,GEMINI_RPD_EXTRACTION,GEMINI_RPD_CLASSIFICATION,GEMINI_RPD_EMBEDDING
```

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The refusal is a subclass of `GeminiRateLimitError`. | The scam explainer's fallback, the v1 and v2 error handlers, the letter's `ai_daily_limit` and the Coach's error event all handle it with no change |
| 2 | Same `503 ai_busy` code; the message and `Retry-After` differ. | The v2 contract has no other code, the frontend ignores `Retry-After` for `ai_busy`, and six-language text should be read by a native speaker (D-288) |
| 3 | A daily 429 is not retried and closes the tier for the day. | Each retry was a request against a quota that was gone |
| 4 | Counts in Firestore, one document a day, server-side increments; read every 15 s. | Memory counts are per instance and reset when an instance stops; there are up to two, and the service scales to zero |
| 5 | The budget is a share of a limit read from `quota-limits.json`, and is off while the limit is null. | The real limits are not in the repository (ADR-002); one file feeds the alerts and the guard |
| 6 | Limits as four plain-integer settings. | `--set-env-vars` splits on commas, which a JSON value contains |
| 7 | The quota day is midnight Pacific, written out in 12 lines. | The slim image and Windows carry no time zone database, and a new dependency is a shared-file change |
| 8 | Fail-open on any store problem. | The guard must not be the reason a worker's request fails |
| 9 | Cache only the recommendation; instrument the others. | It was the one uncached call; the others are stored already, and the shared scam cache was decided against |
| 10 | No new alert, no warm-up job. | The 80% alert exists; a scheduler job would run daily for ever |

## What was verified

| Check | Result |
|---|---|
| `black --check`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| Backend suite without the emulator | 3,810 passed, 206 skipped (CI's first step) |
| Backend integration suite with the Firestore and Auth emulators | 757 passed, 1 failed, 99 skipped (CI's second step). The one failure is `test_scam_history.py` by timing on this Windows machine (D-289), which fails the same way on an untouched copy of `main` |
| Tests added | +106 (4,016 collected, 3,910 before) |
| Coverage gate (`scripts/check_coverage.py`) | passes: `app` 97.6% (needs 93%); `budget.py` 98%, `gemini_usage_repo.py`, `cache.py`, `client.py`, `errors.py` 100% |
| Firestore rules tests (`vitest`, emulator) | 181 passed, with `gemini_usage` named in the denial tests |
| Six deliberate breakages (daily 429 retried; refusal counted as a request; another instance's count ignored; another instance's closed tier ignored; wrong `Retry-After`; embedding 429 not flagged daily) | each one made a test fail |
| `deploy_manual.sh` | `bash -n` clean; `rpd_env.py` prints nothing while the limits are null, and `GEMINI_RPD_*` pairs once they are set (tested) |
| Two scam-history tests | fail on Windows by timing, on an untouched copy of `main` too (D-289); they passed under coverage |

**Not verified, because it needs the project or a key:** that Google accepts the two new metrics and charts (re-run `setup-monitoring.sh`); a run against the real API with a real key and a tiny limit; the real daily limits; the time to the first piece of the Coach reply on the second Flash-Lite model (D-287).

## Definition of Done

Tracker line:

- [x] Simulated quota exhaustion degrades gracefully in both features: `test_quota_exhaustion.py` (9 tests: Scam falls back a tier, is a calm 503, still serves a stored check; Coach turn and plan are a calm 503 and work again after the day turns) and `test_quota_exhaustion_firestore.py` (3 tests through the real wiring)
- [x] Projected demo-day usage under 60% of the daily limit per model: **against the ASSUMED design-document limits**, up to 22 visitors (39 with the reply moved)
- [ ] The same against the real limits: needs D-122, then D-286

Firestore Schema Change:

- [x] Migration: none needed, the collection starts empty
- [x] Security rules reflect the collection (denied by default; comment and tests updated; `firestore.rules` is a shared file, the diff was approved)
- [x] `docs/data-model/` updated (`firestore-schema.md`, `collections/gemini_usage.md`)
- [x] Emulator tests pass
- [x] Version metadata: `schema_version: 1` on the document; no cached data depends on it

Documentation:

- [x] Markdown, consistent headings and code blocks, in `docs/`
- [ ] Reviewed by a teammate (the tracker names Aditya)
- [x] No attribution

## Commit

Branch: `chore/NF-HR-010-ci-quota-guard`.

```bash
git commit -m "feat(gemini): add per-feature daily budget and quota-exhaustion degrade" -m "Refs: NF-HR-010"
git commit -m "feat(cache): cache recommendations and add budget and cache metrics" -m "Refs: NF-HR-010"
git commit -m "docs(quota): add demo-day projection, routing review and pre-warm plan" -m "Refs: NF-HR-010"
```

PR title: `feat(gemini): per-feature daily quota budget, graceful degrade and demo-day projection (NF-HR-010)`

## Noticed, not fixed

- `backend-deploy.yml` does not run when only `infra/monitoring/quota-limits.json` changes (see the gotcha); a one-line `paths:` addition would fix it. Shared file.
- Two scam-history tests fail on Windows by timing (D-289).
- Section 6 of `docs/future-scope/design.md` still lists the Coach reply as `REASONING` (D-290).
- `deploy_manual.sh` resets `--min-instances` to 0 on every deploy, so the evening-before setting is lost if anything is deployed after it (D-77 is where the decision lives).
- `backend/` and `/infra/` are code-owner paths: this change needs a teammate's review.
