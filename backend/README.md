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
1. Copy `.env.example` to `.env.local`
2. Run Firebase Emulator (see `/docs/runbooks/local-dev-setup.md`)
3. `./scripts/run_local.sh`

## Deploy
Automatic on merge to main via GitHub Actions.
