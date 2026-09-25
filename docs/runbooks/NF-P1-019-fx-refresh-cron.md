# NF-P1-019 — FX Refresh Cron (Cloud Scheduler)

## Summary

Every **2 hours** (configurable in one line), **Cloud Scheduler** calls `POST /api/v1/internal/refresh-rates` on the Cloud Run backend. The endpoint fetches the mid-market rate for the six corridor pairs (`SGD_PHP`, `SGD_INR`, `AUD_INR`, `MYR_IDR`, `JPY_PHP`, `AUD_PHP`) through a **provider failover chain** (Frankfurter → ExchangeRate-API → CurrencyFreaks → Wise, ADR-006) and writes them to Firestore: the latest rate to `rates_cache/{pair}` and an hourly point to `rates_history/{pair}/points/{YYYY-MM-DDTHH}`, in the exact shape of `docs/data-model/collections/rates_cache.md`. The endpoint is public on the internet (the whole Cloud Run service is), so the app itself checks every call: only a **Google-signed OIDC token** for the `nomadfinance-scheduler` service account with the service URL as audience is accepted; anything else gets 401/403. If a base currency fails on every provider, its pairs keep their last value and the endpoint answers 503 so Scheduler logs a failure and retries (2 retries, 5 minutes apart). Frankfurter and ExchangeRate-API need no key and publish once a day; CurrencyFreaks is live with a key from Secret Manager; Wise is not configured (see ADR-006).

## Files

| File | Purpose |
|---|---|
| `backend/app/api/v1/internal.py` | `POST /api/v1/internal/refresh-rates` (hidden from `/docs`) |
| `backend/app/dependencies.py` | `require_cloud_scheduler`: 503 if not configured, 401 no/invalid token, 403 other identities |
| `backend/app/core/security.py` | `verify_google_oidc_token()` (google-auth), `TokenVerificationUnavailableError` |
| `backend/app/services/remittance/rates.py` | `refresh_rates()`: one provider call per base currency, in parallel; saves each pair |
| `backend/app/integrations/fx/` | `base.py` (interface, error codes), `frankfurter.py`, `exchangerate_api.py`, `currencyfreaks.py`, `wise.py`, `router.py` (failover chain, `get_fx_router`) |
| `backend/app/repositories/rate_repo.py` | `RateRepository.save_pair()`: cache + history header + hourly point in one batch |
| `backend/app/constants.py` | `CURRENCY_PAIRS` (pair → corridors) |
| `backend/app/schemas/remittance.py` | `RefreshRatesResponse` |
| `backend/app/config.py`, `.env.example` | `CRON_SERVICE_ACCOUNT`, `CRON_AUDIENCE` (required unless `APP_ENV=local`), `FX_TIMEOUT_SECONDS`, `CURRENCYFREAKS_API_KEY`, `WISE_API_TOKEN` |
| `backend/requirements.txt` | pins `httpx`, `google-auth`, `requests` (now imported directly) |
| `backend/scripts/deploy_manual.sh` | passes `CRON_*`; mounts the FX key secrets that exist |
| `infra/cloud-scheduler/refresh-rates.yaml` | The Scheduler job as a `gcloud --flags-file` (schedule, URL, OIDC identity, retries) |
| `infra/iam/service-accounts.md` | Who has which role |
| `docs/decisions/ADR-006-fx-provider-failover-chain.md` | Provider order, rules, status |
| tests | `tests/unit/integrations/test_fx_providers.py`, `test_fx_router.py`, `tests/unit/services/test_rates_service.py`, `tests/unit/test_config.py`, `tests/integration/api/test_internal_refresh.py`, `tests/integration/repositories/test_rate_repository.py` (emulator) |

## Flow

```
Cloud Scheduler job "refresh-rates" (asia-south1, "0 */2 * * *" UTC)
  └─ POST https://nomadfinance-api-azewstzfaa-el.a.run.app/api/v1/internal/refresh-rates
       Authorization: Bearer <OIDC token signed by Google for nomadfinance-scheduler@…, aud = service URL>
       body {}  (Google's front end rejects a POST without Content-Length)
         └─ require_cloud_scheduler  → verify signature, audience, issuer, expiry; email must equal CRON_SERVICE_ACCOUNT
              └─ refresh_rates()  (bases SGD, AUD, MYR, JPY in parallel)
                   └─ FxRouter: Frankfurter → ExchangeRate-API → CurrencyFreaks → Wise (skipped: no token)
                        first provider returning every quote wins; failures recorded as short codes
                   └─ RateRepository.save_pair() × 6 → rates_cache/{pair}, rates_history/{pair}, …/points/{hour}
              ← 200 {refreshed: 6, failed: []}   or   503 {failed: [...]} → Scheduler retries (2×, 5 min)
```

## All commands, in order

Backend commands from `backend/` with the venv active; `gcloud` commands from any terminal logged in as the team account (`gcloud config list`).

### 1. Local checks

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
black --check .
mypy app tests
```

Expected: `100 passed, 5 skipped` (emulator and live-only tests), all clean.

### 2. Repository test on the Firestore emulator (optional)

Terminal 1, from `frontend/`: `firebase emulators:start --only firestore --project demo-nomadfinance`

Terminal 2, from `backend/`:

**Windows PowerShell**
```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"; $env:GOOGLE_CLOUD_PROJECT = "demo-nomadfinance"; pytest tests/integration/repositories -v
```

**bash**
```bash
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance GOOGLE_CLOUD_PROJECT=demo-nomadfinance pytest tests/integration/repositories -v
```

Expected: `2 passed`.

### 3. One-time cloud setup (done 2026-09-25; security changes, run by a project owner)

```bash
gcloud secrets add-iam-policy-binding gemini-api-key --project nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role="roles/datastore.user" --condition=None
gcloud iam service-accounts create nomadfinance-scheduler --project nomadfinance-prod --display-name="NomadFinance Cloud Scheduler"
```

Optional FX keys (ADR-006): create the secret in the console (Secret Manager → Create secret, name `currencyfreaks-api-key` or `wise-api-token`, **Manually manage locations → asia-south1**, other options default), then:

```bash
gcloud secrets add-iam-policy-binding currencyfreaks-api-key --project nomadfinance-prod --member="serviceAccount:nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
```

Also put the key in `backend/.env.local` (`CURRENCYFREAKS_API_KEY=`) for local runs.

### 4. Deploy the backend

Once per machine, let Docker push to Artifact Registry:

```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

Then, with Docker Desktop running, from `backend/` (Git Bash):

```bash
bash scripts/deploy_manual.sh
```

Uncommitted code? Tag the image yourself so it isn't labelled with an older commit: `TAG=my-tag bash scripts/deploy_manual.sh`. PowerShell users: NF-P1-003 runbook, step 4 (its command includes the `CRON_*` values).

Expected: `Service [nomadfinance-api] revision [...] has been deployed`, and the last line lists the mounted secrets.

### 5. Create or change the Scheduler job

From the repo root:

```bash
gcloud scheduler jobs create http refresh-rates --flags-file=infra/cloud-scheduler/refresh-rates.yaml
```

**Change the interval:** edit `--schedule` in `infra/cloud-scheduler/refresh-rates.yaml` (`"0 * * * *"` hourly, `"0 */2 * * *"` every 2 h, `"0 */6 * * *"` every 6 h), then:

```bash
gcloud scheduler jobs update http refresh-rates --flags-file=infra/cloud-scheduler/refresh-rates.yaml
```

Pause / resume:

```bash
gcloud scheduler jobs pause refresh-rates --project nomadfinance-prod --location asia-south1
gcloud scheduler jobs resume refresh-rates --project nomadfinance-prod --location asia-south1
```

### 6. Run it now and check

```bash
gcloud scheduler jobs run refresh-rates --project nomadfinance-prod --location asia-south1
```

A manual run can take up to a minute to start. Then:

```bash
gcloud scheduler jobs describe refresh-rates --project nomadfinance-prod --location asia-south1 --format="value(lastAttemptTime,scheduleTime,state)"
gcloud logging read "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=\"refresh-rates\"" --project nomadfinance-prod --freshness=1h --limit 4 --format="value(timestamp,jsonPayload.@type,httpRequest.status)"
```

Expected: an `AttemptFinished` line with `200`. See the data: Firebase console → Firestore → `rates_cache` (6 documents, `fetched_at` = now) and `rates_history/<pair>/points`.

### 7. Check that nobody else can trigger it

```bash
curl -s -X POST -d "{}" -H "Content-Type: application/json" -w " [%{http_code}]\n" https://nomadfinance-api-azewstzfaa-el.a.run.app/api/v1/internal/refresh-rates
```

(PowerShell: `curl.exe`, and `-d '{}'`.) Expected: `{"detail":"Missing bearer token"} [401]`. With `-H "Authorization: Bearer $(gcloud auth print-identity-token)"` (your own Google token): `401 Invalid service token`.

## Verified results (2026-09-25)

| Check | Result |
|---|---|
| pytest / ruff / black / mypy | 100 passed, 5 skipped / clean / clean / clean |
| Repository on the Firestore emulator | 2 passed (incl. same-hour overwrite, no duplicate point) |
| Full local refresh, real providers → emulator | 6/6 pairs from Frankfurter |
| Live failover (Frankfurter forced to 404) | Switched to ExchangeRate-API, fresh rates, attempt trail recorded |
| CurrencyFreaks alone (key from settings) | 6/6 pairs; SGD→PHP 48.98 vs Frankfurter 49.03 / ExchangeRate-API 48.99 |
| Deploy | Revision `nomadfinance-api-00002-ww2`, image `backend:nf-p1-019-20260925`, secrets Gemini + CurrencyFreaks, `CRON_*` set; `/health` 200 `environment: prod` |
| Live endpoint: no token / garbage token / a real Google token for another account | 401 / 401 / 401 |
| Scheduler job | Created, `ENABLED`, `0 */2 * * *` UTC, OIDC as `nomadfinance-scheduler`, body `{}`, 2 retries |
| Forced run 13:29 UTC | Cloud Run `200` from `Google-Cloud-Scheduler`; Scheduler `AttemptFinished 200` |
| Production Firestore after the run | 6 `rates_cache` documents (provider `frankfurter`, `rate_date` 2026-09-24, attempts, corridors, `schema_version` 1); history point `2026-09-25T13` |
| First automatic run, 14:00 UTC (nobody triggered it) | Scheduler `AttemptFinished 200`; Cloud Run `200` from `Google-Cloud-Scheduler`; new history point `2026-09-25T14`; next run 16:00 UTC |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| App won't start: `CRON_SERVICE_ACCOUNT and CRON_AUDIENCE are required when APP_ENV is not local` | Deployed without them. Use `deploy_manual.sh` or the NF-P1-003 PowerShell command. |
| Scheduler `AttemptFinished` 401 | Audience or account mismatch: `--oidc-token-audience` in the YAML must equal `CRON_AUDIENCE`, `--oidc-service-account-email` must equal `CRON_SERVICE_ACCOUNT`. |
| 403 `Caller is not allowed` | Token is Google-signed but for another account. |
| 503 `Internal endpoints are not configured` | `CRON_*` not set (normal in local dev). |
| 503 with `failed: [...]` | Every provider failed for that base. Check the attempt codes; the old values are kept and Scheduler retries. |
| `411 Length Required` (HTML from Google) | A POST without body. Send `-d "{}"`; the job already sends `{}`. |
| Push `Unauthenticated request ... uploadArtifacts` | Step 4's `gcloud auth configure-docker` not done on this machine. |
| `attempts` shows `currencyfreaks: http_401` | Wrong key in the secret: add a new version in Secret Manager, redeploy. |
| `wise: not_configured` | Expected: no Wise token (ADR-006). |
| No `rates_refresh` line in Cloud Logging | App logging isn't configured yet (deferred D-06, NF-P1-028). Use the Scheduler log and Firestore. |

## Commit and PR for this task

Branch: `feature/remittance-fx-refresh-cron`. From the repo root:

```bash
git add backend infra docs
git status
```

```bash
git commit -m "feat(remittance): add FX refresh cron with provider failover" -m "Refs: NF-P1-019"
```

PR title: `feat(remittance): FX refresh endpoint, 4-provider failover, Cloud Scheduler job (NF-P1-019)`

## Not covered here

- Historical backfill so the trend chart has data on day one (`data-scripts/src/loaders/frankfurter_backfill.py`): not assigned, see deferred log
- Using the rates: NF-P2-014 (comparison), NF-P2-015 (trends), NF-P2-022 (savings)
- Rate-limit exemption for internal calls: NF-P1-027
- Structured request logging (makes `rates_refresh` visible): NF-P1-028
- CI deploy: NF-P1-020
