# NomadFinance — Backend

FastAPI service on Cloud Run.

## Stack
- Python 3.11, FastAPI, Uvicorn + Gunicorn
- Firebase Admin SDK, google-genai, httpx, Pydantic v2
- Firestore, Cloud Storage, Cloud Run

## Structure
- `app/api/v1/` — REST endpoints per pillar (thin — delegate to services), and the scheduler-only `/internal` routes
- `app/api/v2/` — Scam Check, Financial Coach and feature-flag routes (conventions: `docs/api/v2-conventions.md`)
- `app/services/` — Business logic per pillar
- `app/repositories/` — Firestore access layer
- `app/integrations/` — External API clients (Gemini, FX providers, ILO, FCM)
- `app/schemas/` — Pydantic v2 models (API + Firestore contracts)
- `app/prompts/` — Versioned YAML Gemini prompt templates
- `app/core/` — Cross-cutting: auth, logging, middleware, errors, cache
- `app/utils/` — Shared helpers

## Local Dev
Requires Python 3.11.9. Run everything from `backend/`.

1. Create a virtualenv and install dependencies:
   - PowerShell: `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1`
   - bash: `python3.11 -m venv .venv && source .venv/bin/activate`
   - then: `pip install -r requirements-dev.txt`
2. Copy `.env.example` to `.env.local` and fill in `GEMINI_API_KEY` and `RADAR_REPORTER_HASH_SECRET` (`APP_ENV`, `GEMINI_API_KEY` and `RADAR_REPORTER_HASH_SECRET` are required; the app refuses to start without them)
3. Run Firebase Emulator (the emulator variables are shell variables, not `.env.local` lines; the complete walk-through is in the [root README](../README.md#run-it-on-your-machine), and see also [`docs/runbooks/NF-P1-001-local-dev-setup.md`](../docs/runbooks/NF-P1-001-local-dev-setup.md))
4. Start the API: `./scripts/run_local.sh` (bash) or `uvicorn app.main:app --reload --port 8080`
5. Check `http://127.0.0.1:8080/health` and Swagger at `http://127.0.0.1:8080/docs`

Checks before every push: `pytest`, `ruff check .`, `black --check .`, `mypy app`.

After you add or change a route, or a request or response model, regenerate the API contract file and commit it: `python scripts/export_openapi.py` (writes `docs/api/openapi.json`; `--check` only compares). A deployed API does not serve `/openapi.json`, so that file is the contract in machine form, and `tests/unit/test_api_contract_docs.py` fails when it is out of date or when a route is missing from `docs/api/`.
Full setup, check commands and troubleshooting: [`docs/runbooks/NF-P1-001-local-dev-setup.md`](../docs/runbooks/NF-P1-001-local-dev-setup.md).

## Docker
Production image: multi-stage `python:3.11.9-slim-bookworm`, gunicorn with uvicorn workers, non-root user, listens on `$PORT` (default 8080).

1. Build: `docker build -t nomadfinance-backend:local .` (or `./scripts/build_docker.sh`)
2. Run: `docker run --rm -p 8080:8080 --env-file .env.local nomadfinance-backend:local`
3. Check `http://127.0.0.1:8080/health`

Full build/run flow and troubleshooting: [`docs/runbooks/NF-P1-002-backend-docker.md`](../docs/runbooks/NF-P1-002-backend-docker.md).

## Firebase

Firebase Admin SDK (`app/core/security.py`, `app/repositories/base.py`) provides Firestore
access and Firebase Auth ID-token verification (`Depends(get_current_user)`
in `app/dependencies.py`). Prod uses Application Default Credentials via the
`nomadfinance-backend` Cloud Run service account; local dev points at the Firebase Emulator
Suite via `FIRESTORE_EMULATOR_HOST` / `FIREBASE_AUTH_EMULATOR_HOST`.

Full setup, verified commands and troubleshooting: [`docs/runbooks/NF-P1-005-firebase-admin-integration.md`](../docs/runbooks/NF-P1-005-firebase-admin-integration.md).

## Deploy
Cloud Run service `nomadfinance-api` in `nomadfinance-prod`, region `asia-south1`, image in Artifact Registry repo `nomadfinance`.

Merging to `main` deploys by itself (the **Backend deploy** workflow runs `scripts/deploy_manual.sh`). To deploy by hand: log in with `gcloud auth login`, then from `backend/` run `bash scripts/deploy_manual.sh`. It builds a `linux/amd64` image (Cloud Run rejects the arm64 image Apple Silicon builds by default), pushes it and deploys with `APP_ENV=prod` and the `gemini-api-key` secret mounted as `GEMINI_API_KEY`. Check the printed URL with `curl -s <url>/health`.

Full first-deploy steps, redeploy, rollback and troubleshooting: [`docs/runbooks/NF-P1-003-cloud-run-first-deploy.md`](../docs/runbooks/NF-P1-003-cloud-run-first-deploy.md).
