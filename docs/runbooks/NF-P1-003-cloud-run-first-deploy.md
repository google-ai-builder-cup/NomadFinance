# NF-P1-003 — First Deploy to Cloud Run

## Summary

The backend image from NF-P1-002 is deployed by hand to **Cloud Run** as the service `nomadfinance-api` in project `nomadfinance-prod`, region `asia-south1` (Mumbai, next to Firestore). The flow is: build a `linux/amd64` image locally, push it to an **Artifact Registry** repo called `nomadfinance`, then run `gcloud run deploy` with `APP_ENV=prod`. The service is public (`--allow-unauthenticated`) because `/health` is public by design. It runs as a dedicated service account with no roles, scales to zero when idle and is capped at 2 instances, so it stays inside the free tier and the free credits.

Public URL: `https://nomadfinance-api-54982290462.asia-south1.run.app`

The same service also answers on a second URL, `https://nomadfinance-api-azewstzfaa-el.a.run.app`. Both are valid. `gcloud run services describe` prints the second form.

This proves the pipeline end to end before real code lands. GitHub Actions (NF-P1-020) will automate the same steps.

## Files

| File | Purpose |
|---|---|
| `backend/scripts/deploy_manual.sh` | Build (amd64), push and deploy in one go. Variables can be overridden from the environment. |
| `backend/README.md` | Deploy section: short version of this runbook |

Cloud resources created (one time, by NF-P1-003):

| Resource | Name | Notes |
|---|---|---|
| Artifact Registry repo | `nomadfinance` (Docker, `asia-south1`) | Image path `asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<tag>` |
| Service account | `nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com` | Cloud Run runtime identity. Has **no roles** yet. NF-P1-005 grants Firestore access, NF-P1-004 grants Secret Manager access. |
| Cloud Run service | `nomadfinance-api` | 1 vCPU, 512Mi, min instances 0, max instances 2, `APP_ENV=prod`, public |

## Flow

```
docker build --platform linux/amd64
  └─ image tagged <region>-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<git short sha>
docker push  ──►  Artifact Registry (asia-south1)
gcloud run deploy
  └─ new revision nomadfinance-api-0000N-xxx (runs as nomadfinance-backend SA, APP_ENV=prod)
  └─ 100% traffic to the new revision
public request ──► Cloud Run ──► gunicorn (PID 1, $PORT=8080) ──► /health 200
```

## Why linux/amd64

Cloud Run runs `linux/amd64` containers only. A plain `docker build` on an Apple Silicon Mac produces `linux/arm64`, and the deploy then fails with `exec format error` or "image must support amd64/linux". The script passes `--platform linux/amd64`, so it works the same on Mac and Windows. On an Apple Silicon Mac the build runs under emulation and is slower than the NF-P1-002 local build.

## Cost

Everything here is inside the free tier or covered by the free credits:

| Item | Free tier | This deploy |
|---|---|---|
| Cloud Run requests | 2M / month | A few health checks |
| Cloud Run compute | scale to zero, billed per request only | `--min-instances 0`, so nothing is billed while idle |
| Artifact Registry storage | 0.5 GB | about 70 MB per image |
| Cloud Build | not used in this task | none |

`--max-instances 2` is the cost guard. Leave it until real traffic needs more. Old images pile up in Artifact Registry with every deploy, so delete unused tags (see Clean up).

## All commands, in order

Commands are the same in PowerShell and bash unless both are shown. Steps 1–3 are one-time setup. From step 4 on is the routine you repeat for every manual deploy.

### 0. Prerequisites

- Docker Desktop running: `docker info --format "{{.ServerVersion}}"` prints a version.
- `gcloud` installed and logged in with an account that has deploy rights on `nomadfinance-prod`. The team uses `aibuildercup23@gmail.com`.

```bash
gcloud auth list
gcloud config set project nomadfinance-prod
gcloud config get-value project
```

Expected: the right account is marked `ACTIVE`, and the last command prints `nomadfinance-prod`.

Check the APIs this task needs are on (already enabled in NF-P0-004):

```bash
gcloud services list --enabled --format="value(config.name)" | grep -E "run|artifactregistry|cloudbuild"
```

Expected: `run.googleapis.com`, `artifactregistry.googleapis.com` and `cloudbuild.googleapis.com` appear. PowerShell has no `grep`; use `| Select-String "run|artifactregistry|cloudbuild"`.

### 1. Create the Artifact Registry repo (one time)

```bash
gcloud artifacts repositories create nomadfinance --repository-format=docker --location=asia-south1 --description="NomadFinance backend images"
```

Expected: `Created repository [nomadfinance].` If it says `ALREADY_EXISTS`, skip this step.

### 2. Create the runtime service account (one time)

```bash
gcloud iam service-accounts create nomadfinance-backend --display-name="NomadFinance backend (Cloud Run runtime)"
```

Why a new account: without `--service-account`, Cloud Run uses the default Compute Engine account, which has `roles/editor` on this project. That is far more than a web API needs. The new account has no roles, and each later task grants only what it needs.

### 3. Let Docker push to Artifact Registry (one time per machine)

```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

Expected: `Docker configuration file updated.` This adds a credential helper entry to your local Docker config. It stores no password.

### 4. Build, push and deploy

From the `backend/` folder:

```bash
cd backend
```

**bash (recommended)**
```bash
bash scripts/deploy_manual.sh
```

The script is tracked without the execute bit, so start it with `bash`, not `./`.

**Windows PowerShell** (the script is bash; run its three steps by hand):

```powershell
$IMAGE = "asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:$(git rev-parse --short HEAD)"
docker build --platform linux/amd64 -t $IMAGE .
docker push $IMAGE
gcloud run deploy nomadfinance-api `
  --project nomadfinance-prod `
  --region asia-south1 `
  --image $IMAGE `
  --service-account nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com `
  --set-env-vars "APP_ENV=prod" `
  --allow-unauthenticated `
  --cpu 1 --memory 512Mi `
  --min-instances 0 --max-instances 2
```

What the script's settings mean:

| Flag | Why |
|---|---|
| `--set-env-vars APP_ENV=prod` | The image has no default for `APP_ENV` and exits without it (see NF-P1-002). |
| `--allow-unauthenticated` | Grants `roles/run.invoker` to `allUsers`. Needed for a public URL. Fine for `/health`; real endpoints check Firebase tokens in the app (NF-P1-005). |
| `--min-instances 0` | Scale to zero when idle, so no idle cost. The first request after idle is a cold start of a few seconds. |
| `--max-instances 2` | Hard cost cap. |
| `--service-account` | Runtime identity from step 2. |
| `PORT` | Not set by us. Cloud Run injects it (8080) and gunicorn already reads it. |

Image tag: the script uses the short git SHA. It does not include uncommitted changes, so commit before you deploy anything you want to trace. Override with `TAG=my-tag bash scripts/deploy_manual.sh`.

The first deploy takes a few minutes (amd64 build under emulation plus push). It ends with:

```
Service [nomadfinance-api] revision [nomadfinance-api-00001-xxx] has been deployed and is serving 100 percent of traffic.
Service URL: https://nomadfinance-api-54982290462.asia-south1.run.app
```

### 5. Verify the public URL

**Windows PowerShell**
```powershell
Invoke-RestMethod https://nomadfinance-api-54982290462.asia-south1.run.app/health
```

**bash**
```bash
curl -s https://nomadfinance-api-54982290462.asia-south1.run.app/health
```

Expected: `{"status":"ok","version":"0.1.0","environment":"prod"}`. `environment` must be `prod`, which proves `APP_ENV` reached the container.

Also check:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-api-54982290462.asia-south1.run.app/docs
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-api-54982290462.asia-south1.run.app/openapi.json
curl -s -w "\n%{http_code}\n" https://nomadfinance-api-54982290462.asia-south1.run.app/nope
```

Expected: `200`, `200`, then `{"detail":"Not Found"}` and `404`. Open `/docs` in a browser as well: Swagger UI loads and `GET /health` → "Try it out" → "Execute" returns 200. PowerShell users: replace `curl` with `curl.exe`.

### 6. Check the service configuration

```bash
gcloud run services describe nomadfinance-api --region asia-south1 --format="yaml(status.url,status.latestReadyRevisionName,spec.template.spec.serviceAccountName,spec.template.spec.containers[0].resources,spec.template.spec.containers[0].env,spec.template.metadata.annotations)"
```

Expected: `serviceAccountName: nomadfinance-backend@...`, `cpu: '1'`, `memory: 512Mi`, `APP_ENV: prod`, `autoscaling.knative.dev/maxScale: '2'`. There is no `minScale` line, which means 0.

```bash
gcloud run services get-iam-policy nomadfinance-api --region asia-south1
```

Expected: `allUsers` with `roles/run.invoker`.

Check the pushed image is amd64 and small:

```bash
docker image inspect asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<tag> --format "{{.Os}}/{{.Architecture}}"
gcloud artifacts docker images list asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance
```

Expected: `linux/amd64`, and the image appears in the list.

### 7. Read the logs

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api"' --limit 15 --freshness 30m --format="value(timestamp,textPayload,httpRequest.requestMethod,httpRequest.requestUrl,httpRequest.status)"
```

Expected: gunicorn lines (`Booting worker`, `Application startup complete.`) and one request line per `curl` above. The same logs are in the Cloud Console under Cloud Run → `nomadfinance-api` → Logs.

## Redeploy, rollback, clean up

**Redeploy after a code change.** Commit, then repeat step 4. Cloud Run creates a new revision and shifts 100% of traffic once it is healthy. A revision that fails to start is not given traffic, so a bad deploy leaves the old revision serving.

**Roll back.** List revisions, then point traffic at an older one:

```bash
gcloud run revisions list --service nomadfinance-api --region asia-south1
gcloud run services update-traffic nomadfinance-api --region asia-south1 --to-revisions nomadfinance-api-00001-6sg=100
```

Replace the revision name with the one you want. Use `--to-latest` to go back to newest.

**Delete old images** (keeps Artifact Registry under the 0.5 GB free tier):

```bash
gcloud artifacts docker images delete asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<old-tag> --delete-tags
```

Never delete the tag the live revision uses.

**Take the service down** (only if you must; the public URL stops working):

```bash
gcloud run services delete nomadfinance-api --region asia-south1
```

Confirm with the team first, because the demo link points here.

## Verified results (2026-09-24)

| Check | Result |
|---|---|
| Image platform | `linux/amd64`, about 68 MB compressed in the registry |
| Deploy | Revision `nomadfinance-api-00001-6sg`, 100% traffic |
| `GET /health` (public URL) | `200 {"status":"ok","version":"0.1.0","environment":"prod"}`, about 2 s on a cold start |
| `GET /health` (second URL form) | 200, same body |
| `/docs`, `/openapi.json` | 200, 200 |
| Unknown path | 404 `{"detail":"Not Found"}` |
| Service account | `nomadfinance-backend@nomadfinance-prod.iam.gserviceaccount.com` |
| Resources and scaling | 1 vCPU, 512Mi, max instances 2, min instances 0 |
| Access | `allUsers` has `roles/run.invoker` |
| Logs | Gunicorn boot, `Application startup complete.`, one line per request |

## Definition of Done (Documentation and DevOps)

- [x] Public URL answers `/health` with 200 and `environment: "prod"`
- [x] Image built for `linux/amd64` and stored in Artifact Registry
- [x] Runs as a dedicated service account, not the default Compute account
- [x] Cost guards set (min 0, max 2)
- [x] Steps documented here and in `backend/README.md`; `deploy_manual.sh` repeats them
- [x] No secrets in the repo (none needed: only `APP_ENV=prod`)
- [x] Markdown, consistent headings and code blocks
- [ ] Reviewed by at least one teammate
- [ ] Committed to `/docs`

## Commit

Branch: `chore/ci-cloud-run-first-deploy`

```bash
git add backend/scripts/deploy_manual.sh backend/README.md docs/runbooks/NF-P1-003-cloud-run-first-deploy.md
git commit -m "chore(backend): add manual Cloud Run deploy script and runbook" -m "Refs: NF-P1-003"
```

Before pushing, run `git status` and confirm nothing else is staged.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `exec format error` or "must support amd64/linux" on deploy | The image was built for arm64. Rebuild with `--platform linux/amd64` (the script does this). |
| Revision fails: "container failed to start and listen on the port" | Read the logs (step 7). Most often `APP_ENV` is missing (`app_env Field required`). Redeploy with `--set-env-vars APP_ENV=prod`. |
| `denied: Permission ... artifactregistry.repositories.uploadArtifacts` on push | Wrong `gcloud` account, or step 3 was skipped. Check `gcloud auth list`, rerun `gcloud auth configure-docker asia-south1-docker.pkg.dev`. |
| `name unknown: Repository "nomadfinance" not found` | Step 1 was skipped, or the region in the image path is wrong. |
| Browser or `curl` returns 403 "Forbidden" on a working service | The public invoker binding is missing. Rerun the deploy with `--allow-unauthenticated`, or `gcloud run services add-iam-policy-binding nomadfinance-api --region asia-south1 --member=allUsers --role=roles/run.invoker`. An organisation policy can block `allUsers`; if so, ask the project owner. |
| First request after idle takes a few seconds | Normal cold start with min instances 0. Do not raise min instances unless a demo needs it, since that is billed while idle. |
| `Service account ... does not exist` on deploy | Step 2 was skipped, or the name has a typo. |
| `./scripts/deploy_manual.sh: Permission denied` | The script has no execute bit. Run `bash scripts/deploy_manual.sh`. |
| Docker build very slow on Apple Silicon | Expected for the emulated amd64 build. Later builds reuse the layer cache. |
| `gcloud` asks to enable an API | Say yes only if the API is one of Cloud Run, Artifact Registry or Cloud Build; otherwise ask the project owner. |

## Not covered here

- CI build and deploy on merge (OIDC, no JSON keys): NF-P1-020
- Gemini key from Secret Manager and the Gemini client: NF-P1-004
- Firebase Admin, Firestore access and token verification: NF-P1-005
- CORS and rate limiting: NF-P1-027
- Structured request logging: NF-P1-028
- Cloud Scheduler calling internal endpoints: NF-P1-019
- Declarative service config in `infra/cloud-run/`
