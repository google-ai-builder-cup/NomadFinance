# Service accounts — nomadfinance-prod

Only accounts our own code or jobs run as. Google-managed service agents (`service-54982290462@gcp-sa-*`) and the AI Studio key accounts are left out.

| Account | Used by | Granted | Why | Added in |
|---|---|---|---|---|
| `nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com` | Cloud Run `nomadfinance-api` (runtime identity) | `roles/datastore.user` (project) | Read/write Firestore (rates, later all pillars) | NF-P1-019 |
| | | `roles/secretmanager.secretAccessor` on secret `gemini-api-key` | Gemini API key | NF-P1-004 (granted 2026-09-25) |
| | | `roles/secretmanager.secretAccessor` on secret `currencyfreaks-api-key` | FX provider 3 (ADR-006) | NF-P1-019 |
| | | `roles/firebaseauth.admin` (project) | Delete the sign-in account when a user deletes their account (`DELETE /api/v1/users/me`) | NF-P1-023 (`infra/iam/grant-account-deletion-roles.sh`) |
| | | `roles/storage.objectUser` on bucket `nomadfinance-prod.firebasestorage.app` | Delete the user's uploaded files (`contracts/`, `bills/`, `exports/`) with the account | NF-P1-023 |
| `nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com` | Cloud Scheduler jobs (`infra/cloud-scheduler/`) | none | Only its identity is used: Scheduler signs an OIDC token as this account, and the backend accepts `/api/v1/internal/*` calls only from it (`CRON_SERVICE_ACCOUNT`). | NF-P1-019 |
| `nomadfinance-deploy-backend@nomadfinance-prod.iam.gserviceaccount.com` | GitHub Actions `backend-deploy.yml` (keyless, Workload Identity Federation) | `roles/run.admin` on service `nomadfinance-api`; `roles/artifactregistry.writer` on repo `nomadfinance`; `roles/iam.serviceAccountUser` on `nomadfinance-backend`; `roles/secretmanager.viewer` and `roles/serviceusage.serviceUsageConsumer` (project) | Build, push and deploy the backend on merge to `main`; the viewer role sees which secrets exist, never their values | NF-P1-020 |
| `nomadfinance-deploy-frontend@nomadfinance-prod.iam.gserviceaccount.com` | GitHub Actions `frontend-deploy.yml` | `roles/firebasehosting.admin`, `roles/firebase.viewer`, `roles/serviceusage.serviceUsageConsumer` (project) | Deploy Firebase Hosting on merge to `main` | NF-P1-020 |
| `nomadfinance-deploy-infra@nomadfinance-prod.iam.gserviceaccount.com` | GitHub Actions `firestore-rules-deploy.yml`, `scheduler-deploy.yml` | `roles/firebaserules.admin`, `roles/firebase.viewer`, `roles/cloudscheduler.admin`, `roles/serviceusage.serviceUsageConsumer` (project); `roles/iam.serviceAccountUser` on `nomadfinance-scheduler` | Publish Firestore and Storage rules; create or update Scheduler jobs | NF-P1-020 |

The three deployer accounts have no keys. GitHub proves its identity with an OIDC token and Google exchanges it (pool `github`, provider `github`). The provider accepts only a run of `google-ai-builder-cup/NomadFinance` on `refs/heads/main`, and each account trusts only that repository through `roles/iam.workloadIdentityUser`. Setup and removal: `infra/iam/setup-github-actions.sh` and `docs/runbooks/NF-P1-020-github-actions-cicd.md`.

Rules:
- One account per workload, least privilege: grant on the single resource (a secret) when possible, not the project.
- Never create or download JSON keys for these accounts; Cloud Run and Cloud Scheduler use them keylessly.
- When a task adds a grant, add a row here in the same PR.

Check what an account really has:

```bash
gcloud projects get-iam-policy nomadfinance-prod --flatten="bindings[].members" --filter="bindings.members:nomadfinance-backend@" --format="value(bindings.role)"
gcloud secrets get-iam-policy gemini-api-key --project nomadfinance-prod
```
