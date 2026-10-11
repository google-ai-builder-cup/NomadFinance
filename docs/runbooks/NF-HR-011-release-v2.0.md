# NF-HR-011 — Release v2.0: changelog, tag, flagged rollout, rollback

Owner Aditya, reviewer Pranjal. Branch `release/v2.0`. Written 2026-10-11.

## Summary

v2.0 is the Scam Analyzer and the Financial Coach, plus the platform work around them (`/api/v2`, flags, redaction, observability, the Gemini budget guard) and the hardening passes of NF-HR-004 to -010. Everything is already merged to `main`: `release/v2.0`, `main` and `origin/main` all point at `abcf536`, and because every merge to `main` deploys to production (NF-F0-011), **the code is already live**. What is left is to put a version on it, write down what it contains, rehearse going back, and turn the modules on in a controlled order.

**Built in this task**

| What | Where |
|---|---|
| Changelog builder (reads git, writes nothing but `CHANGELOG.md`) and its 31 tests | `infra/release/generate_changelog.py`, `backend/tests/unit/test_release_changelog.py` |
| The v2.0.0 changelog: 82 commits, 71 pull requests (#108 to #178), since `6117b4f` (v1.0) | `CHANGELOG.md`, highlights in `infra/release/highlights-2.0.0.md` |
| Version `2.0.0` in `app_version` (so `/health` says which build is live), `backend/pyproject.toml`, `frontend/package.json` | the files themselves; `docs/api/endpoints.md` example |
| This runbook: gate, release steps, rollback, rehearsal record, staged enable | here |
| The missing step in the Cloud Run rollback (`--to-latest`) | `docs/runbooks/deploy-backend.md` |

**Not done, because only a person can do it** (git, GitHub and production writes are not mine to run): merging NF-HR-005 and -006, the release PR, the tag and the GitHub Release, the rollback rehearsal, and the staged enable with its two 30-minute watches. Each is a numbered step below with the exact command, and a blank record to fill in.

## What production looked like on 2026-10-11

Read-only checks of `nomadfinance-prod`, before any change in this task.

| Item | Result |
|---|---|
| `/health` | `{"status":"ok","version":"0.1.0","environment":"prod"}` (hence the version bump) |
| Cloud Run `nomadfinance-api` | Revision `00081-hj7` at 100% since 14:28 UTC (the same minute as the Hosting release), `maxScale=2`, concurrency 80, startup CPU boost on. Earlier revisions 00074 to 00080 are kept |
| Firebase Hosting | Latest release 2026-10-11 14:28 UTC, 147 files, made by the deploy service account |
| Firestore rules | Re-released 14:29 UTC (Firestore and Storage) |
| **`config/feature_flags`** | **`coach` `enabled: true` and `scam` `enabled: true`, both for everyone** (`scam.allow_uids` also lists one tester). Last edited by PP, 2026-10-09. So the tracker's "deploy with flags off, then enable one at a time" had not happened. See "Staged enable" for how this task handles it |
| TTL policies | `coach_sessions`, `scam_checks` and `scam_indicators`, all on `expires_at`: ACTIVE (closes the check in D-103) |
| Composite and vector indexes | 6, all READY, including `scam_patterns.embedding` (768) and `report_embeddings` |
| Single-field exemptions | `coach_plans.departure_date` and `scam_checks.created_at` both have the collection-group scope (D-114 part, D-164 part) |
| Seeded collections | `cost_baselines` 6, `scam_taxonomy` 15, `complaint_templates` 6, `labor_laws` 6, `scam_stats` 7, `radar_entities` 19, `radar_reports` 43 |
| **`scam_patterns`** | **0 documents.** The feature page lists this load as optional; without it "Seen N times" has nothing to search (D-135, D-271) |
| Cloud Scheduler | `coach-checkins`, `fib-recompute`, `scam-stats`, `refresh-rates`, `radar-aggregation`: ENABLED, last runs on time. `labor-law-check` does not exist (its YAML is an empty file) |
| `quota-limits.json` | Every `rpd` is `null`: the NF-HR-010 budget guard is off and the daily-limit alerts are skipped (D-122, D-286) |

**Could not be read:** the Cloud Run service's environment and `min-instances` (the permission classifier refused the command, as it did for NF-HR-004, D-276), the monitoring dashboard and alerts (the command needed a gcloud component that was not installed, and nothing was installed), GitHub Actions status and branch protection (`gh` is not installed here).

## Go / no-go gate

Nothing below is a decision made by this document: it is the list to walk through before the tag. **Blocker** means do not tag until it is cleared.

| # | Item | State | Owner | Clear it by |
|---|---|---|---|---|
| G1 | NF-HR-004 (#175), -007 (#174), -008 (#176, no open High), -009 (#177) merged | Done | | |
| G2 | **Blocker.** NF-HR-005 merged | Not done: no `fix/regression-suite-b` on origin | Aditya | Merge it |
| G3 | **Blocker.** NF-HR-006 merged | Not done: no `fix/regression-suite-c` on origin | Pranjal | Merge it |
| G4 | **Blocker.** `main` is green: the five required checks (`Backend checks`, `Frontend checks`, `Frontend rules tests`, `Data scripts checks`, `Commit policy`) on the latest `main` commit | Not checked (no `gh` here) | Aditya | GitHub, Actions, branch `main` |
| G5 | **Blocker.** Read the Cloud Run service (D-276): environment variable names, `min-instances`, latest revision | Refused to me | Devam | Command below |
| G6 | Signed-in smoke test of production (D-274) | Not done | Devam | The list in D-274 |
| G7 | Daily limits set, backend redeployed by hand, monitoring script run (D-122, D-286) | Not done | Pranjal | `docs/runbooks/NF-HR-010-gemini-quota-guard.md`, "Demo-day pre-warm" |
| G8 | Scam patterns loaded (D-135, D-271) | Not done: 0 documents | Devam or Aditya | `python -m src.loaders.scam_patterns` from `data-scripts/` |
| G9 | Branch protection on `main` (D-116) | Not checked; four commits reached `main` with no pull request (`27ecde0`, `d27c8d0`, `71e8620`, `2a45703`) | Devam | GitHub, Settings, Branches |
| G10 | The tester `allow_uids` entry on `scam` is known and intended | Unknown | Pranjal (PP edited it) | Look at the document |

G7 to G10 are not tag blockers, but turn each into a decision before the modules stay on for everyone: with G7 open a spent Gemini quota shows workers "try again later" with no early warning, and with G8 open the Scam Analyzer works but never says "seen before".

For G5, names only, no secret values (secrets show as references):

```bash
gcloud run services describe nomadfinance-api --region asia-south1 --project nomadfinance-prod --format="yaml(spec.template.metadata.annotations,spec.template.spec.containers[0].env)"
```

Expected: `APP_ENV=prod`, `CRON_SERVICE_ACCOUNT`, `CRON_AUDIENCE`, the secret references `GEMINI_API_KEY` and `RADAR_REPORTER_HASH_SECRET`, `autoscaling.knative.dev/maxScale: '2'`, and `minScale` absent (zero) unless D-77 was decided.

## Release steps

Dates: the tracker says 2026-11-16, but the prototype freeze is 2026-10-17 (NF-F0-011). Do these before the demo, not on the day.

**1. Code freeze.** Tell the team: until the tag, `main` takes only the NF-HR-005 and -006 fixes and fixes found by the rehearsal. Every merge deploys.

**2. Clear G2 to G5.**

**3. Rebuild the changelog** after the last merge, so it lists the fixes that landed late. From the repo root:

```bash
python infra/release/generate_changelog.py --base 6117b4f9 --version 2.0.0 --highlights infra/release/highlights-2.0.0.md --write
```

It replaces only the block between the two `2.0.0` markers, sets the date to today, and changes nothing else. Read the diff: a late fix appears as a new line, and `git diff --stat CHANGELOG.md` is empty if nothing landed. The commit that carries the changelog is not listed in it; it is the one the tag points at. `--base 6117b4f9` is v1.0 (the last commit before PR #108, the same anchor NF-HR-007 used). Optionally mark it so the next release needs no `--base`: `git tag -a v1.0.0 6117b4f9 -m "NomadFinance v1.0.0"` and `git push origin v1.0.0`.

**4. Release pull request.** Open `release/v2.0` into `main` (title and description are in "Commit" below), get Pranjal's approval, merge. The merge changes `backend/` and `frontend/`, so **it starts a backend deploy and a frontend deploy**; flags and data are not touched. Watch GitHub, Actions, "Backend deploy" and "Frontend deploy" go green. Then:

```bash
curl -s https://nomadfinance-api-54982290462.asia-south1.run.app/health
```

(PowerShell: `curl.exe`, because `curl` there is another command.) Expect `"version":"2.0.0"`. This is the release revision; the revision it replaced (`00081-hj7` unless something else merged first) is the rollback target.

**5. Tag.** On `main`, at the merge commit of the release pull request:

```bash
git switch main
git pull
git tag -a v2.0.0 -m "NomadFinance v2.0.0"
git push origin v2.0.0
```

**6. GitHub Release.** Releases, Draft a new release, tag `v2.0.0`, title `NomadFinance v2.0.0`, description = the text of `infra/release/highlights-2.0.0.md` plus a link to `CHANGELOG.md`. With the GitHub CLI: `gh release create v2.0.0 --verify-tag --title "NomadFinance v2.0.0" --notes-file infra/release/highlights-2.0.0.md`.

**7. Rehearse the rollback, then stage the enable** (next two sections). The tracker's "Done when" is met only after both are recorded below.

## Rollback

**Flag off first, always.** The code is inert behind a flag, so switching the flag is the fastest and least disruptive way back; the code levers below are for a problem the flag does not cover (the deploy itself, or something outside the two modules).

| Lever | Use it when | Takes effect in | Costs |
|---|---|---|---|
| 1. Flag off | A module misbehaves, or Gemini or quota trouble shows in one of them | 60 s on the server, plus up to 60 s for an open page (`staleTime` 60 s) | Nothing is lost: data the module wrote stays and is not shown |
| 2. Previous Cloud Run revision | The new revision itself is bad (errors on v1 routes, start-up failures, wrong config) | Seconds | Loses that revision's code, including v2 routes if you go below the v2 line |
| 3. Previous Hosting release | The new web build is bad | Seconds for the site, but see the note | A phone that already loaded the new build keeps it until it accepts the update prompt (`registerType: "prompt"`) |
| 4. Rules or Scheduler | A rules change or a job misbehaves | One workflow run | Revert the commit; the workflow republishes the previous file |

**1. Flag off.** Firebase console, Firestore Database, `nomadfinance-prod`, `config`, `feature_flags`. For each module to turn off: `flags.<name>.enabled` = `false` and clear `allow_uids` (write down the uids first if you will want them back). Set `updated_by` to your initials and `updated_at` to now. A browser cannot write this document and no API changes it (rules from NF-F0-004). Check: a signed-in test account, in a private window, no longer shows the Coach or Scam Check entries within about two minutes, and a direct call answers the standard 404 envelope:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://nomadfinance-api-54982290462.asia-south1.run.app/api/v2/scam/analyze -H "Authorization: Bearer <test account ID token>" -H "Content-Type: application/json" -d "{}"
```

Expect `404` with the scam flag off. The guard sits on the whole `/api/v2/scam` router, so it answers before the body is read; a `422` would mean the flag is still on, and a `401` means the token is wrong or expired.

**2. Previous Cloud Run revision.**

```bash
gcloud run revisions list --service nomadfinance-api --region asia-south1 --project nomadfinance-prod --limit 5
```

```bash
gcloud run services update-traffic nomadfinance-api --region asia-south1 --project nomadfinance-prod --to-revisions <previous revision>=100
```

Check `/health`: a revision from before this release says `0.1.0`, the release says `2.0.0`. Roll back only to a revision from the v2 line (any revision from 2026-10-06, when the flag service, PR #112, merged): a pre-v2 revision has never been run against the v2 documents (new collections, `source` values on `radar_reports`, `signal_sharing` and goals on the Financial Identity profile).

**After a rollback, give the traffic back to the newest revision, or no later deploy will ever go live:**

```bash
gcloud run services update-traffic nomadfinance-api --region asia-south1 --project nomadfinance-prod --to-latest
```

Pinning traffic to a named revision stops the service following the newest one; `backend-deploy.yml` would then keep building revisions that receive no traffic and still report success. If the bad revision came from a commit, revert it on `main` before this step, or the next backend merge deploys it again.

**3. Previous Hosting release.** Firebase console, Hosting, Release history, the earlier release, Rollback. To see which build is live from outside, read the main bundle name before and after (it contains a content hash):

```bash
curl -s https://nomadfinance-prod.web.app/ | grep -o 'assets/index-[^"]*\.js'
```

To go forward again, roll back to the newest release in the same list, or run "Frontend deploy" on `main` (Actions, Run workflow). A revert commit on `main` is still needed or the next frontend merge redeploys the bad build.

**4. Rules and Scheduler.** Revert the commit; `firestore-rules-deploy.yml` and `scheduler-deploy.yml` publish the previous files. To stop a job without a deploy: `gcloud scheduler jobs pause coach-checkins --project nomadfinance-prod --location asia-south1` (and `resume` after). With the `coach` flag off the check-in job answers 200 and sends nothing (D-231), so pausing is optional.

**Data.** v2 only adds collections and fields, and nothing needs undoing. The one thing to watch is the second-level effect of lever 2 just described.

## Rollback rehearsal

There is no staging (NF-F0-011), so this runs on production. It takes both modules dark for everyone for about 20 minutes, then it becomes the start of the staged enable below, so do them in one sitting, **well before the demo, at a quiet hour**, with two people (one acts, one writes). Prerequisites: the release is deployed (step 4) so that "previous" and "latest" differ.

| # | Do | Expect | Time | Result / who |
|---|---|---|---|---|
| R0 | Note: both flags' `enabled` and `allow_uids`; `gcloud run revisions list` (latest and previous); the main bundle name; the Hosting "Current" release | Written down, so you can put everything back | | |
| R1 | Lever 1: both flags off, `allow_uids` cleared | | | |
| R2 | In a private window with a test account, within 2 minutes | No Coach or Scam Check in the tab bar or sidebar; typing `/coach` or `/scam-check` redirects to `/dashboard`; the `curl` above answers `404`; Remittance X-Ray, Contract Shield, Financial Identity and Exploitation Radar work as in v1.0 | | |
| R3 | Lever 2: traffic to the previous revision | `/health` says `0.1.0`; a v1 call still works | | |
| R4 | `--to-latest` | `/health` says `2.0.0`; `gcloud run services describe nomadfinance-api --region asia-south1 --project nomadfinance-prod --format="value(status.traffic)"` shows the latest revision with `latestRevision: true` | | |
| R5 | Lever 3: Hosting rollback to the previous release, then forward again | Bundle name changes then returns; the site loads both times | | |
| R6 | Write the three durations and anything surprising | Proposed targets: dark in 2 minutes, Cloud Run in 5, Hosting in 5 | | |

Fill the table in the pull request that records the rehearsal (or edit this file): the tracker asks that it is "recorded".

## Staged enable

The tracker says: flags off at deploy, then enable one at a time, Scam Analyzer then Coach, 30 minutes of watching each. Production already has both on (see above). So the rehearsal doubles as the reset: after R2 both modules are off, and this section starts from there. If the team prefers to keep the modules on, skip the reset, record that the staged rollout was bypassed on 2026-10-07 to 09, and still do R3 to R6.

| Step | Do | Watch for | Next only if |
|---|---|---|---|
| E1 | `flags.scam.enabled` = `true`. Wait two minutes, then run the happy path in a private window: sign in, paste a known scam, read the verdict and the steps, open the history | Watch 30 minutes with the checks below | Nothing in "Stop and flag off" happened |
| E2 | `flags.coach.enabled` = `true`. Happy path: start an interview, answer a few questions, reach the score, open the plan and its PDF | Watch 30 minutes | Same |
| E3 | Both on. Hand over to NF-HR-017 (48-hour watch) | | |

**Checks, every 5 minutes.** Logs Explorer (paste the filter; PowerShell 5.1 strips the double quotes of a filter passed to `gcloud`, so use Logs Explorer, or Git Bash for the CLI form):

```
resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api" AND jsonPayload.message=~"^request_completed " AND jsonPayload.feature="scam" AND jsonPayload.status_class="5xx"
```

Change `scam` to `coach` for E2, `5xx` to `4xx` to see rejections (a 429 from the hourly limit is normal). Two more filters: `jsonPayload.message=~"^gemini_call_failed "` (a call that gave up) and `jsonPayload.message=~"^gemini_budget_blocked "` (the guard refused a request, which should not happen before a daily limit is reached). The same in Git Bash:

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api" AND severity>=ERROR AND jsonPayload.feature="scam"' --project nomadfinance-prod --freshness 30m --limit 30 --format="value(timestamp,jsonPayload.message)"
```

The dashboard "NomadFinance: requests, errors and Gemini usage" shows the same per feature once `setup-monitoring.sh` has been run (D-122); two charts were added by NF-HR-010 (`nf_gemini_budget_blocks`, `nf_cache_lookups`). Today's Gemini counts are in `gemini_usage/<day>` (the command is in the NF-HR-010 runbook, "Commands").

**Stop and flag off** (proposed; Aditya and Pranjal may change the numbers):

- a server error on the module's routes that is not explained by a `gemini_call_failed` or `gemini_budget_blocked` line with the same `request_id` (a Gemini `503 ai_busy` is a graceful answer, not a fault, but more than a handful in ten minutes means the quota is going);
- any error on a v1 route that started after the flag was switched on;
- the happy path above fails, or a screen shows a stack trace, a blank page or the wrong language;
- the daily-limit alert fires (once G7 is done), or `gemini_usage` shows a model near its limit;
- more than a few workers' reports of "cannot work out your score" or "try again later" in the first 30 minutes.

| Step | Started | Ended | Watched by | Notes / anything found |
|---|---|---|---|---|
| E1 Scam on | | | | |
| E2 Coach on | | | | |

## What was checked in this task

| Check | Result |
|---|---|
| `black --check` and `ruff check` on the generator and its tests (line length 100) | clean |
| `mypy` on the generator (`--disallow-untyped-defs`) | clean |
| `pytest tests/unit/test_release_changelog.py` | 31 passed |
| Generator against the real history, `--base 6117b4f9` | 82 commits, 71 pull requests; counts by type match `git log` (51 feat, 9 docs, 6 fix, 4 chore, 11 test lines for 12 test commits, one being a duplicate message); a second run changes nothing |
| Four commits with no pull request | Confirmed as direct commits on `main`'s first-parent line, so shown by sha |
| Version bump | `git diff`: one line in each of the four files; `test_health.py` reads `app_version` from settings, so no test pins the old value |
| Production reads | Listed above. Nothing in production was changed, and no git write was run |

Not run: the full backend and frontend suites (the changes are a version string, a script that no deploy runs and its test; CI runs both suites on the pull request), the rehearsal and the staged enable.

## Definition of Done

Documentation (tracker): Markdown, consistent formatting, committed under `/docs`, no tool attribution: done. Reviewed by a teammate: pending (Pranjal). Feature-flagged module: rollback path stated, flag off first: done (section above).

Tracker "Done when":

- [ ] `v2.0.0` tag on a green `main`: **not done** (G2 to G5, then steps 3 to 5)
- [ ] Rollback rehearsal recorded: **not done** (the table above is empty)
- [ ] Flags enabled one at a time, Scam Analyzer then Coach, 30-minute watch each: **not done** (E1, E2)
- [x] `CHANGELOG.md` built from Conventional Commits
- [x] Rollback runbook written, including the Cloud Run trap
- [x] `/health` and both package versions say 2.0.0 once the pull request is merged

## Commit

Branch: `release/v2.0`

```
chore(release): add v2.0.0 changelog, version bump and rollback runbook
Refs: NF-HR-011
```

PR title: `chore(release): v2.0.0 changelog, version bump and rollback runbook (NF-HR-011)`

## Noticed, not fixed

Logged in `docs/deferred-items.md` as D-291 to D-296.

- The flags were switched on before any release process (D-291).
- NF-HR-005 and -006 are not merged (D-292).
- The steps only a person can do: tag, GitHub Release, rehearsal, staged enable (D-293).
- Four commits reached `main` without a pull request (D-294).
- `docs/runbooks/incident-response.md` is empty; this page covers rollback only (D-295).
- The history has two merged subjects that read badly in the changelog (PR #109 joins two subjects, PR #113 lists a second one after a comma) and one typo (`deffered updated`). History is published, so they stay (D-296).
- `data-scripts/pyproject.toml` still says `0.1.0`; nothing deploys it, so it was left.
- `infra/README.md` says six cron jobs, but `labor-law-check.yaml` is an empty file, so five exist.
