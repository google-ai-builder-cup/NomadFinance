# Deploy the frontend, rules and scheduler jobs

The frontend is a static site on Firebase Hosting (`https://nomadfinance-prod.web.app`). Background: `NF-P1-008-firebase-hosting-deploy.md` (first manual deploy) and `NF-P1-020-github-actions-cicd.md` (automation and one-time setup).

## Normal way: merge to `main`

| You change | Workflow that runs | Result |
|---|---|---|
| `frontend/**` | `frontend-deploy.yml` | `pnpm build`, then `firebase deploy --only hosting` |
| `frontend/firestore.rules` or `frontend/storage.rules` | `firestore-rules-deploy.yml` | rule tests, then both rule files published |
| `infra/cloud-scheduler/*.yaml` | `scheduler-deploy.yml` | one Cloud Scheduler job created or updated per non-empty file |

Watch each under GitHub → Actions. Pull requests only run the CI checks (lint, formatting, build, rule tests); nothing is deployed from a pull request.

The frontend build needs two GitHub repository **Variables**, `VITE_FIREBASE_API_KEY` and `VITE_FIREBASE_APP_ID` (Settings → Secrets and variables → Actions → Variables). The workflow stops with a message if either is empty.

## Check the result

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-prod.web.app/
curl -s -o /dev/null -w "%{http_code}\n" https://nomadfinance-prod.web.app/some/unknown/route
gcloud scheduler jobs list --project nomadfinance-prod --location asia-south1
```

Expected: `200`, `200` (the SPA rewrite serves `index.html`), and the Scheduler jobs listed as `ENABLED`. Then sign in once in a browser.

## Fallback: deploy by hand

Only if Actions is down, from `frontend/` with a `.env.local` that has the Firebase values:

```bash
pnpm build
firebase deploy --only hosting --project nomadfinance-prod
```

Rules by hand: `firebase deploy --only firestore:rules,storage --project nomadfinance-prod`. Scheduler by hand: `gcloud scheduler jobs update http <name> --flags-file=infra/cloud-scheduler/<name>.yaml`.

## Roll back

Hosting: Firebase console → Hosting → Release history → Rollback on the earlier release, then revert the commit on `main`. Rules: revert the commit; the workflow republishes the previous rules. Scheduler: revert the YAML change; the workflow updates the job back.
