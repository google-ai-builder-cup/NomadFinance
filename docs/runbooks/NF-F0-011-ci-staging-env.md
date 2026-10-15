# NF-F0-011 — Staging environment: dropped, not built

**Status: not built, on purpose. Decided 2026-10-06 (Pranjal, for the team).** There is no staging environment, and none is planned before the prototype freeze on 17 Oct 2026. Do not build one, and do not write a task that depends on one, unless the team reopens this.

Anyone picking up a Future Scope task, and any tool they use to plan or write code, should read this page before following a tracker line that says "on staging".

## What was decided and why

The tracker row asked for a second environment beside production: a Cloud Run service `nomadfinance-api-staging`, a Firebase Hosting preview channel `staging`, a separate Firestore database (or a `stg_` prefix), staging secrets, a deploy-on-merge workflow, and a production deploy that is manual and approval-gated.

It was dropped because the hackathon deadline leaves no time for it. The submission freeze is 17 Oct (tracker: NF-P4-014 on the 17th, portal on the 18th), and the work still open before then is the demo, deck, README and final checks (NF-P4-005 to -020). Staging would have cost most of a task of 4 hours plus Google Cloud and GitHub settings that only a project owner can change, with no user-visible benefit for the prototype.

Nothing was built or changed for it. No branch work, workflow, script, secret, database or setting exists. The branch `chore/NF-F0-011-ci-staging-env` has no commits and can be deleted.

## What this means today

| Fact | Consequence |
|---|---|
| **There is one environment: production** (`nomadfinance-prod`). | Anything that "ran on staging" in a tracker line has nowhere to run. |
| **Every merge to `main` deploys to production.** `backend-deploy.yml` (on `backend/**`), `frontend-deploy.yml` (on `frontend/**`) and `firestore-rules-deploy.yml` (on the rules files) all run on push, with no approval step. | A merge is a release. Merge nothing you would not want live. Near the freeze, merge only what the demo needs. |
| **New Future Scope code ships behind flags that default to off** (`GET /api/v2/flags`, NF-F0-005; no `config/feature_flags` document means everything is off). | Merging unfinished coach or scam code does not change what users see, as long as the flag stays off. |
| **Production can be tried by named people only**, with `enabled: false` and the tester's uid in `allow_uids` (`docs/data-model/collections/config.md`). | This replaces "try it on staging". Everyone else still gets the module as off. |
| The **local emulators** (Firestore and Auth) and the test mocks are the only place to run a change without touching production data. | `pnpm test:rules`, the backend `tests/integration` run, and `firebase emulators:start` still work as before. |

## Tasks whose tracker line mentions staging

The tracker (`.claude/tasks.md`, a local file that is not in git) still says "staging" in these rows. Treat the line as the substitute shown here.

| Task | What the tracker says | Do this instead |
|---|---|---|
| NF-F0-004 | Rules and indexes deployed to staging | Done on production only (rules by the workflow on merge; indexes and TTL by hand, see its runbook) |
| NF-F0-014 | Playwright project "running against staging" | Run Playwright against the local app and emulators, or against production with a test account while the flag is allow-listed |
| NF-F0-016 | Dashboard and alert tested "on staging" | Build it in production. Test the alert by lowering the threshold temporarily, not by exhausting a quota |
| NF-SA-007, NF-SA-013, NF-SA-020 | p95 latency, E2E, adversarial suite "on staging" | Measure and run against local emulators and mocks, then once on production behind the allow-list |
| NF-FC-009, NF-FC-015, NF-FC-024, NF-FC-025 | First-token latency, persona replay, E2E "on staging" | Same: emulators and mocks first, then one allow-listed check on production |
| NF-HR-003 | Demo data seed (staging data) | Seed the demo users in production, or the emulators for tests |
| NF-HR-011 | Rollback rehearsed on staging, production deploy with flags off | Rehearse on production while the flag is off for everyone: flag off, previous Cloud Run revision, previous Hosting release (`deploy-backend.md`, `deploy-frontend.md`) |

A task that says "p95 under N s on staging" is checked on production, with a note that it is production.

## Where the docs still say "staging"

These mentions were written before the decision. They are now historical, and none of them needs a code change.

| Where | What to read it as |
|---|---|
| `docs/data-model/collections/config.md` ("Staging and production each have their own copy") | One copy only, in production |
| `docs/runbooks/NF-F0-005-backend-feature-flags.md`, `NF-F0-004-data-rules-indexes-v2.md`, `NF-F0-003-data-schema-v2.md`, `NF-F0-006-frontend-flags-routes.md` | Everything that says "staging" or "NF-F0-011" is production only |
| `docs/data-model/firestore-schema.md` ("production, and staging when NF-F0-011 creates it") | TTL policies are set once, in production (D-103) |
| `backend/app/config.py` allows `APP_ENV=staging` | Valid but unused. Nothing sets it |
| `docs/runbooks/NF-P1-018-labor-law-load.md` ("`labor_laws_staging`") | An unrelated scratch collection name, not an environment |
| `docs/api/endpoints.md` (`environment`: `local`, `staging` or `prod`) | The `/health` field accepts the value, and only `local` and `prod` occur |

## If the team reopens this after the prototype

The analysis done on 2026-10-06 is worth keeping, because it shows where the work is. Nothing below was built.

- **Separate data:** a named Firestore database `staging` in the same project is the least work. It needs a `FIRESTORE_DATABASE` setting where `repositories/base.py` builds the client, a `VITE_FIRESTORE_DATABASE` setting in `frontend/src/lib/firestore.ts`, a database option on the data loaders, and `frontend/firebase.json` changed so rules and indexes deploy to both databases. A `stg_` prefix would touch every repository path, every rule and every frontend query, so it is not recommended. A separate Google project is cleaner, but needs its own Auth, billing and federation setup.
- **Shared with production anyway:** in the same project, staging uses the same Firebase Auth users, and a Hosting preview channel's address has to be added to Auth's authorized domains by hand.
- **Deploys today:** the three deploy workflows run on `main` only, and Google accepts a login only from `main` (the federation condition from NF-P1-020). A staging deploy on merge and a manual, approval-gated production deploy would both run on `main`, so that condition does not need to change. The production workflows would need their push trigger removed and a GitHub Environment with required reviewers.
- **`backend/scripts/deploy_manual.sh`** is production-only (service name, runtime account, secrets are fixed). It would need an `ENVIRONMENT` switch.
- **Secrets:** a separate `-staging` secret for the Gemini key avoids staging load using production's free-tier quota.
- **Shared files** (workflows, `firebase.json`) need the owner's approval for each diff, as for any change to them.

Not part of this page: the production risk of auto-deploy on merge is the thing to manage in the meantime (see "What this means today").
