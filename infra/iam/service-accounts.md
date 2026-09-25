# Service accounts — nomadfinance-prod

Only accounts our own code or jobs run as. Google-managed service agents (`service-54982290462@gcp-sa-*`) and the AI Studio key accounts are left out.

| Account | Used by | Granted | Why | Added in |
|---|---|---|---|---|
| `nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com` | Cloud Run `nomadfinance-api` (runtime identity) | `roles/datastore.user` (project) | Read/write Firestore (rates, later all pillars) | NF-P1-019 |
| | | `roles/secretmanager.secretAccessor` on secret `gemini-api-key` | Gemini API key | NF-P1-004 (granted 2026-09-25) |
| | | `roles/secretmanager.secretAccessor` on secret `currencyfreaks-api-key` | FX provider 3 (ADR-006) | NF-P1-019 |
| `nomadfinance-scheduler@nomadfinance-prod.iam.gserviceaccount.com` | Cloud Scheduler jobs (`infra/cloud-scheduler/`) | none | Only its identity is used: Scheduler signs an OIDC token as this account, and the backend accepts `/api/v1/internal/*` calls only from it (`CRON_SERVICE_ACCOUNT`). | NF-P1-019 |

Rules:
- One account per workload, least privilege: grant on the single resource (a secret) when possible, not the project.
- Never create or download JSON keys for these accounts; Cloud Run and Cloud Scheduler use them keylessly.
- When a task adds a grant, add a row here in the same PR.

Check what an account really has:

```bash
gcloud projects get-iam-policy nomadfinance-prod --flatten="bindings[].members" --filter="bindings.members:nomadfinance-backend@" --format="value(bindings.role)"
gcloud secrets get-iam-policy gemini-api-key --project nomadfinance-prod
```
