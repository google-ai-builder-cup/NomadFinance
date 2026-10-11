# Deploy the backend

The backend is the Cloud Run service `nomadfinance-api` (project `nomadfinance-prod`, region `asia-south1`).
Background: `NF-P1-003-cloud-run-first-deploy.md` (first manual deploy) and `NF-P1-020-github-actions-cicd.md` (automation and one-time setup).

## Normal way: merge to `main`

`.github/workflows/backend-deploy.yml` runs when a merge changes `backend/**`. It logs in without a key (OIDC), builds a `linux/amd64` image, pushes it to Artifact Registry as `backend:<git short sha>`, deploys it, and calls `/health`. Watch it under GitHub → Actions → "Backend deploy". Run it again without a code change with **Run workflow** on `main`.

## Check the result

```bash
curl -s https://nomadfinance-api-54982290462.asia-south1.run.app/health
gcloud run revisions list --service nomadfinance-api --region asia-south1
```

Expected: `{"status":"ok","version":"2.0.0","environment":"prod"}` (the version is `app_version` in `backend/app/config.py`) and a new revision at 100% traffic.

## Fallback: deploy by hand

Only if Actions is down. Needs Docker and a logged-in `gcloud` with deploy rights:

```bash
cd backend
bash scripts/deploy_manual.sh
```

It is the same script the workflow runs.

## Roll back

A revision that fails to start never receives traffic, so a bad deploy leaves the old revision serving. If the trouble is in the Coach or the Scam Analyzer, **turn its flag off first** (`config/feature_flags`, within about 2 minutes, no deploy); go back to an older revision only when the flag does not cover it. To go back to an older working revision:

```bash
gcloud run revisions list --service nomadfinance-api --region asia-south1
gcloud run services update-traffic nomadfinance-api --region asia-south1 --to-revisions <older-revision>=100
```

Then revert the bad commit on `main`, or the next backend merge deploys it again.

**Give the traffic back afterwards.** Naming a revision stops the service following the newest one, so every later deploy builds a revision that receives no traffic while the workflow still reports success. Once the fix is deployed:

```bash
gcloud run services update-traffic nomadfinance-api --region asia-south1 --to-latest
```

The full release and rollback procedure, with a rehearsal table, is `NF-HR-011-release-v2.0.md`.

## Logs

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="nomadfinance-api"' --limit 15 --freshness 30m --format="value(timestamp,textPayload)"
```

## Keep the registry small

Old images stay in Artifact Registry (free tier is 0.5 GB). Delete tags you no longer need, never the one the live revision uses:

```bash
gcloud artifacts docker images delete asia-south1-docker.pkg.dev/nomadfinance-prod/nomadfinance/backend:<old-tag> --delete-tags
```
