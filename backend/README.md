# NomadFinance — Backend

FastAPI service on Cloud Run.

## Stack
- Python 3.11, FastAPI, Uvicorn + Gunicorn
- Firebase Admin SDK, google-genai, httpx, Pydantic v2
- Firestore, Cloud Storage, Cloud Run

## Structure
- `app/api/v1/` — REST endpoints per pillar (thin — delegate to services)
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
2. Copy `.env.example` to `.env.local` (`APP_ENV` is required; the app refuses to start without it)
3. Run Firebase Emulator (see [`docs/runbooks/NF-P1-001-local-dev-setup.md`](../docs/runbooks/NF-P1-001-local-dev-setup.md))
4. Start the API: `./scripts/run_local.sh` (bash) or `uvicorn app.main:app --reload --port 8080`
5. Check `http://127.0.0.1:8080/health` and Swagger at `http://127.0.0.1:8080/docs`

Checks before every push: `pytest`, `ruff check .`, `black --check .`, `mypy app tests`.
Full setup, check commands and troubleshooting: [`docs/runbooks/NF-P1-001-local-dev-setup.md`](../docs/runbooks/NF-P1-001-local-dev-setup.md).

## Docker
Production image: multi-stage `python:3.11.9-slim-bookworm`, gunicorn with uvicorn workers, non-root user, listens on `$PORT` (default 8080).

1. Build: `docker build -t nomadfinance-backend:local .` (or `./scripts/build_docker.sh`)
2. Run: `docker run --rm -p 8080:8080 -e APP_ENV=local nomadfinance-backend:local`
3. Check `http://127.0.0.1:8080/health`

Full build/run flow and troubleshooting: [`docs/runbooks/NF-P1-002-backend-docker.md`](../docs/runbooks/NF-P1-002-backend-docker.md).

## Deploy
Cloud Run service `nomadfinance-api` in `nomadfinance-prod`, region `asia-south1`, image in Artifact Registry repo `nomadfinance`.

Manual deploy (until GitHub Actions lands in NF-P1-020): log in with `gcloud auth login`, then from `backend/` run `bash scripts/deploy_manual.sh`. It builds a `linux/amd64` image (Cloud Run rejects the arm64 image Apple Silicon builds by default), pushes it and deploys with `APP_ENV=prod`. Check the printed URL with `curl -s <url>/health`.

Full first-deploy steps, redeploy, rollback and troubleshooting: [`docs/runbooks/NF-P1-003-cloud-run-first-deploy.md`](../docs/runbooks/NF-P1-003-cloud-run-first-deploy.md).
