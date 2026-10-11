#!/usr/bin/env bash
# Manual Cloud Run deploy: build (linux/amd64), push to Artifact Registry, deploy.
# Run by .github/workflows/backend-deploy.yml on every merge to main (NF-P1-020); also usable by
# hand as a fallback. Override any variable from the environment.
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${PROJECT:-nomadfinance-prod}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-nomadfinance-api}"
REPO="${REPO:-nomadfinance}"
RUNTIME_SA="${RUNTIME_SA:-nomadfinance-backend@${PROJECT}.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/backend:${TAG}"
SCHEDULER_SA="${SCHEDULER_SA:-nomadfinance-scheduler@${PROJECT}.iam.gserviceaccount.com}"

# Cloud Scheduler's OIDC tokens are checked against the service URL (NF-P1-019). The service
# already exists, so its URL is known before this deploy.
SERVICE_URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" \
  --format 'value(status.url)')"

# Daily request limits per Gemini model, from the file the quota alerts also read (NF-F0-016).
# A model with a null limit adds nothing: its budget guard (NF-HR-010) stays off. They travel
# with every deploy because --set-env-vars below replaces all variables on the service.
RPD_ENV="$(python3 ../infra/monitoring/rpd_env.py)"

# The FX keys are optional (ADR-006): mount each one only if its secret exists.
SECRETS="GEMINI_API_KEY=gemini-api-key:latest,RADAR_REPORTER_HASH_SECRET=radar-reporter-hash-secret:latest"
for mapping in "CURRENCYFREAKS_API_KEY=currencyfreaks-api-key" "WISE_API_TOKEN=wise-api-token"; do
  if gcloud secrets describe "${mapping#*=}" --project "${PROJECT}" >/dev/null 2>&1; then
    SECRETS="${SECRETS},${mapping}:latest"
  fi
done

# Cloud Run only runs linux/amd64; Apple Silicon builds arm64 by default.
docker build --platform linux/amd64 -t "${IMAGE}" .
docker push "${IMAGE}"

# --timeout 900: a contract analysis (steps 2 to 6, NF-P2-007) runs inside one request and can
# pass the default 300 s when Gemini is slow and retries.
gcloud run deploy "${SERVICE}" \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --service-account "${RUNTIME_SA}" \
  --set-env-vars "APP_ENV=prod,CRON_SERVICE_ACCOUNT=${SCHEDULER_SA},CRON_AUDIENCE=${SERVICE_URL}${RPD_ENV}" \
  --set-secrets "${SECRETS}" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --timeout 900 \
  --min-instances 0 \
  --max-instances 2

echo "Deployed ${IMAGE} (secrets: ${SECRETS})"
echo "Check: curl -s ${SERVICE_URL}/health"
