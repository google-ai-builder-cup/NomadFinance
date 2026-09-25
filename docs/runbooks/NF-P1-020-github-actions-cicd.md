# NF-P1-020 — GitHub Actions CI/CD

## Summary

Merging to `main` now deploys the app, and every pull request is checked first. Eight workflows in `.github/workflows/` do the work:

| Workflow | Runs on | What it does |
|---|---|---|
| `backend-ci.yml` | PR and push to `main` touching `backend/**` | `ruff`, `black --check`, `mypy app`, `pytest`, and a `docker build` of the image |
| `frontend-ci.yml` | PR and push touching `frontend/**` | `pnpm lint`, `pnpm format:check`, `pnpm build` (type-check + Vite); a second job runs the Firestore and Storage rule tests on the emulators |
| `data-ci.yml` | PR and push touching `data-scripts/**` | `ruff`, `black`, `mypy`, `pytest`, then the labor-law checker with `--require-all` and dry runs of both loaders |
| `security-scan.yml` | every PR, push to `main`, and Mondays 03:00 UTC | `pip-audit` on both Python requirement files, `pnpm audit` (high and above) |
| `backend-deploy.yml` | push to `main` touching `backend/**` (or run by hand) | builds the image, pushes it to Artifact Registry, deploys `nomadfinance-api` to Cloud Run, then calls `/health` |
| `frontend-deploy.yml` | push to `main` touching `frontend/**` (or by hand) | `pnpm build` then `firebase deploy --only hosting`, then fetches the live site |
| `firestore-rules-deploy.yml` | push to `main` touching `frontend/firestore.rules` or `storage.rules` (or by hand) | runs the rule tests, then deploys both rule files |
| `scheduler-deploy.yml` | push to `main` touching `infra/cloud-scheduler/**` (or by hand) | creates or updates one Cloud Scheduler job per non-empty YAML file |

No JSON key exists anywhere. Deploys log in with **OIDC (Workload Identity Federation)**: GitHub gives the job a short-lived signed token, and Google trades it for a short-lived access token for one deployer service account. Google accepts the token only from **this repository, on the `main` branch**. So another branch, a fork or a pull request cannot deploy, even for someone who can push branches to the repository. (The repository is private, so forks are not a concern today; the restriction is still the safer default and costs nothing.)

The tracker asked for two deploy workflows. The other six were added at the team's request in the same task, because no other task covered them (the four CI files existed as empty stubs).

## Files

| File | Purpose |
|---|---|
| `.github/workflows/*.yml` (8 files, listed above) | The workflows. All of `.github/workflows/` needs review from every code owner (`CODEOWNERS`). |
| `infra/iam/setup-github-actions.sh` | One-time Google Cloud setup: the federation pool and provider, three deployer accounts and their roles |
| `infra/iam/service-accounts.md` | Rows for the three deployer accounts |
| `docs/runbooks/deploy-backend.md`, `deploy-frontend.md` | Short deploy, verify and rollback procedures (were empty stubs) |
| `backend/scripts/deploy_manual.sh` | Comment updated only. The backend workflow **runs this same script**, so CI and manual deploys cannot drift apart |
| `frontend/index.html`, `frontend/src/pages/Landing.tsx` | Formatting only (Prettier). They were merged unformatted and would have made `format:check` fail on the first run |

Shared files were changed only as agreed: the workflow files. No `requirements*`, `package.json`, `Dockerfile`, `firebase.json` or rules file changed.

## How the login works

```
GitHub run on main  ──►  GitHub OIDC token (says: repo google-ai-builder-cup/NomadFinance, ref refs/heads/main)
        │
        ▼   google-github-actions/auth
Google Security Token Service ──► provider "github" checks the token and the repo+branch condition
        │
        ▼   impersonate
nomadfinance-deploy-<backend|frontend|infra>@nomadfinance-prod  ──► short-lived access token (about 1 hour)
        │
        ▼
gcloud / docker / firebase-tools use it for that job only
```

| Deployer account | Used by | Roles (least privilege) |
|---|---|---|
| `nomadfinance-deploy-backend` | `backend-deploy.yml` | `run.admin` on the service `nomadfinance-api` only; `artifactregistry.writer` on the repo `nomadfinance` only; `iam.serviceAccountUser` on `nomadfinance-backend` only; `secretmanager.viewer` (metadata: it cannot read a value); `serviceusage.serviceUsageConsumer` |
| `nomadfinance-deploy-frontend` | `frontend-deploy.yml` | `firebasehosting.admin`, `firebase.viewer`, `serviceusage.serviceUsageConsumer` |
| `nomadfinance-deploy-infra` | `firestore-rules-deploy.yml`, `scheduler-deploy.yml` | `firebaserules.admin`, `firebase.viewer`, `cloudscheduler.admin`, `serviceusage.serviceUsageConsumer`; `iam.serviceAccountUser` on `nomadfinance-scheduler` only |

Each account trusts only this repository's identity (`roles/iam.workloadIdentityUser`). The runtime accounts (`nomadfinance-backend`, `nomadfinance-scheduler`) are unchanged.

## One-time setup (do this before the first merge)

Three things, in this order. Steps 1 and 2 need a project owner.

### 1. Google Cloud: run the setup script

From the repo root, with the team account logged in:

```bash
gcloud auth list                       # aibuildercup23@gmail.com should be ACTIVE
gcloud config set project nomadfinance-prod
bash infra/iam/setup-github-actions.sh
```

Expected: sections `== 1. APIs` to `== 7. ...`, each binding echoed, and at the end the provider name
`projects/54982290462/locations/global/workloadIdentityPools/github/providers/github`. That exact string is already in the workflow files. Running the script again is safe.

Check:

```bash
gcloud iam workload-identity-pools providers describe github --project nomadfinance-prod --location global --workload-identity-pool github --format="yaml(name,state,attributeCondition)"
gcloud iam service-accounts list --project nomadfinance-prod --format="value(email)" | grep deploy
```

Expected: `state: ACTIVE`, the condition naming this repo and `refs/heads/main`, and three `nomadfinance-deploy-*` accounts. PowerShell: use `Select-String deploy` instead of `grep`.

### 2. GitHub: two repository variables

Repository → Settings → Secrets and variables → Actions → **Variables** tab → New repository variable:

| Name | Value |
|---|---|
| `VITE_FIREBASE_API_KEY` | `apiKey` from `firebase apps:sdkconfig WEB --project nomadfinance-prod` (also in your `frontend/.env.local`) |
| `VITE_FIREBASE_APP_ID` | `appId` from the same command |

These are public identifiers that ship in the browser bundle, but they are kept out of the repository so a Google API key is never committed (secret scanners flag them). Variables, not Secrets: they must be readable in the build step. The frontend workflow stops with a clear message if either is empty; without that check it would deploy a site nobody can sign in to.

### 3. GitHub: settings worth turning on (recommended)

- Settings → Branches → add a rule for `main`: require a pull request and require these checks to pass: `Backend CI / checks`, `Frontend CI / checks`, `Frontend CI / rules`, `Data scripts CI / checks`, `Security scan / python-dependencies`, `Security scan / frontend-dependencies`. A check only appears in the list after it has run once on some pull request.
- Secret scanning and Push protection (Settings → Code security) catch keys before they land, which no workflow can do. On a **private** repository they need GitHub Advanced Security, a paid add-on; without it, rely on the rule "no secrets in the repo" and the review.
- Settings → Actions → General: "Workflow permissions" = read repository contents only (the workflows ask for what they need).

## First run

The federation accepts only `main`, so the login and deploy are first exercised **after the pull request merges**. A failed deploy job harms nothing: Cloud Run keeps serving the old revision, and Firebase Hosting keeps the old release.

After the merge:

1. GitHub → Actions. The deploy workflows whose folders the merge touched start on their own (`.github/workflows/...` paths are in each trigger, so all deploy workflows run once on the merge that adds them).
2. Open one run and read the "Build, push and deploy" step. You should see the image pushed to `asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<sha>` and `Deployed ...`.
3. The last step prints `{"status":"ok","version":"0.1.0","environment":"prod"}`.
4. Check the revision: `gcloud run revisions list --service nomadfinance-api --region asia-south1` shows a new one at 100% traffic.
5. Frontend: open `https://nomadfinance-prod.web.app/` and sign in once.

If something fails, the run log names the missing permission. Troubleshooting is below.

## Day to day

- Open a pull request. The CI workflows for the folders you touched run. Fix red checks before merging.
- Merge to `main`. The matching deploy workflow runs. Nothing else to do.
- Run a deploy by hand: Actions → the workflow → **Run workflow** → branch `main`.
- Manual deploys still work: `bash backend/scripts/deploy_manual.sh` and `firebase deploy --only hosting` (see `deploy-backend.md`, `deploy-frontend.md`). Use them only if Actions is down.

**Roll back the backend** (a bad revision that started fine):

```bash
gcloud run revisions list --service nomadfinance-api --region asia-south1
gcloud run services update-traffic nomadfinance-api --region asia-south1 --to-revisions <older-revision>=100
```

Then revert the commit on `main`, or the next backend merge redeploys the code again. **Roll back the frontend:** Firebase console → Hosting → Release history → Rollback on the earlier release, then revert the commit.

**Change a Scheduler job:** edit `infra/cloud-scheduler/<name>.yaml` and merge. The workflow updates the job named after the file. A file must be a `gcloud scheduler jobs create http --flags-file` file (see `refresh-rates.yaml`). Empty files are skipped.

**Change the rules:** edit `frontend/firestore.rules` or `storage.rules`, add or update tests in `frontend/tests/rules/`, merge. CI runs the rule tests on the pull request; the deploy workflow runs them again before publishing.

## Remove it (if you need to)

```bash
gcloud iam workload-identity-pools delete github --project nomadfinance-prod --location global
gcloud iam service-accounts delete nomadfinance-deploy-backend@nomadfinance-prod.iam.gserviceaccount.com
gcloud iam service-accounts delete nomadfinance-deploy-frontend@nomadfinance-prod.iam.gserviceaccount.com
gcloud iam service-accounts delete nomadfinance-deploy-infra@nomadfinance-prod.iam.gserviceaccount.com
```

Deleting the pool stops all deploys at once; manual deploys keep working.

## What was verified, and what was not

Verified on a laptop before this change:

| Check | Result |
|---|---|
| Backend `ruff`, `black --check`, `mypy app`, `pytest` | Pass; `100 passed, 5 skipped`. Also pass from a clean copy with no `.env` files, as on a CI runner |
| Data-scripts `ruff`, `black`, `mypy`, `pytest`, `labor_law --require-all`, both loader dry runs | Pass (`66 passed`) |
| Frontend `pnpm lint`, `pnpm format:check`, `pnpm build` with placeholder Firebase values | Pass, after the two formatting-only fixes |
| `pnpm test:rules` (Firestore and Storage rules on the emulators) | Pass |
| `pip-audit` on `backend/requirements.txt` and `data-scripts/requirements.txt` | No known vulnerabilities |
| `pnpm audit --prod --audit-level high` | Exit 0 (two moderate advisories, see "Noticed") |
| All eight workflow files parse as YAML | Yes |
| First run on GitHub (the pull request) | Backend CI, data-scripts CI, the frontend `checks` job, `pip-audit` and `pnpm audit` passed. Two things failed and were fixed: the rules tests (`firebase: not found`, fixed by installing `firebase-tools` in the two workflows that run them) and the CodeQL upload (private repository without Advanced Security, so the CodeQL job was removed) |
| `setup-github-actions.sh` | `bash -n` clean |

**Not verified until the first run on GitHub** (these cannot run on a laptop): the OIDC login itself, the deployer accounts' roles, `docker push` from the runner, and `firebase-tools` deploying with federated credentials. If a role is missing, the log shows the exact permission; add the role to the script and to the table above and run the script again.

## Definition of Done

DevOps (Documentation checklist plus task specifics):
- [x] Backend workflow: Docker build, push to Artifact Registry, Cloud Run deploy, health check
- [x] Frontend workflow: Vite build, Firebase Hosting deploy, live-site check
- [x] OIDC federation, no JSON keys; restricted to this repo's `main`
- [x] Least-privilege deployer accounts, documented in `infra/iam/service-accounts.md`
- [x] CI workflows (backend, frontend, data-scripts), a security scan, rules deploy and Scheduler deploy
- [x] Steps documented here, in `deploy-backend.md` and in `deploy-frontend.md`
- [x] No secrets in the repository (the two Firebase identifiers live in GitHub variables)
- [x] Markdown, consistent headings and code blocks, no AI attribution
- [x] `setup-github-actions.sh` run by a project owner on 2026-09-26 (step 1); checked read-only afterwards: provider `ACTIVE` with the repo-and-`main` condition, three deployer accounts with exactly the roles in the table, and only this repository allowed to impersonate them
- [ ] GitHub variables set (step 2)
- [ ] First run on `main` green (see "First run")
- [ ] Reviewed by at least one teammate

## Commit

Branch: `chore/ci-github-actions`.

```bash
git add .github/workflows infra/iam/setup-github-actions.sh infra/iam/service-accounts.md infra/README.md \
  backend/scripts/deploy_manual.sh docs/runbooks/NF-P1-020-github-actions-cicd.md \
  docs/runbooks/deploy-backend.md docs/runbooks/deploy-frontend.md \
  frontend/index.html frontend/src/pages/Landing.tsx
git commit -m "chore(ci): add GitHub Actions CI, security scan and OIDC deploy workflows" -m "Refs: NF-P1-020"
```

`.github/CODEOWNERS` also shows a change in your working tree (the `@pranjal-username` placeholder replaced by `@pranjalparmar23`). It is not part of this task's edits; add it only if you want it in this pull request.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Unable to acquire impersonated credentials` / `Permission 'iam.serviceAccounts.getAccessToken' denied` | The federation binding is missing or the run is not on `main`. Re-run the setup script; check the run was triggered from `main` (a pull request or another branch is refused on purpose) |
| `The given credential is rejected by the attribute condition` | The run is not `google-ai-builder-cup/NomadFinance` on `refs/heads/main` (for example, a fork, or the repo was renamed). Update `REPO` in the script and re-run it |
| `Set the repo variable VITE_FIREBASE_API_KEY` | Step 2 not done, or the variable is a Secret instead of a Variable |
| `denied: Permission ... artifactregistry.repositories.uploadArtifacts` | `artifactregistry.writer` on the `nomadfinance` repo is missing for the backend deployer; re-run the script |
| `Permission 'iam.serviceaccounts.actAs' denied` on `gcloud run deploy` | `iam.serviceAccountUser` on `nomadfinance-backend` is missing; re-run the script |
| Backend deploy works but a secret is not mounted | The script mounts an optional secret only if it can see it. Check `secretmanager.viewer` on the backend deployer |
| `firebase deploy` says `Error: Failed to get Firebase project` or a 403 | The frontend or infra deployer lacks `firebase.viewer` / `serviceusage.serviceUsageConsumer`; re-run the script |
| Rules deploy 403 on `firebaserules.releases.update` | `firebaserules.admin` missing on the infra deployer |
| `pnpm test:rules` fails in CI only | The emulator jar could not download, or Java is older than 11. The workflow installs Temurin 21; re-run the job |
| Scheduler job `update` rejects the file | The YAML no longer matches `gcloud scheduler jobs update http` flags. Try the same command locally with the file |
| `firebase: not found` in the rules tests | `pnpm test:rules` calls a global `firebase` that `package.json` does not install. The workflows run `npm install --global firebase-tools@15.31.0` first; keep that version in step with the deploy command |
| Code scanning upload refused ("Advanced Security must be enabled") | Code scanning (CodeQL) is not available on a private repository without GitHub Advanced Security. The CodeQL job was removed for this reason; add it back only if the repo goes public or Advanced Security is bought |
| Security scan fails the `pip-audit` step | A pinned dependency has a new advisory. Bump the pin in the requirements file, or add a reasoned ignore |
| A workflow did not start on merge | Its `paths:` filter did not match the changed files. Use **Run workflow** |

## Not covered here

- Frontend unit tests (none exist yet; only the rule tests)
- Backend integration tests that need real Google services
- Deploying Firestore indexes (`firestore.indexes.json` is not referenced by `frontend/firebase.json`, and that file was left alone)
- Preview deployments for pull requests
- Cloud Scheduler jobs other than `refresh-rates` (their YAML files are still empty placeholders for later tasks)
- CodeQL code scanning and GitHub secret scanning: both need Advanced Security on a private repository
- Upgrading `react-router` to 7.x for two moderate advisories
