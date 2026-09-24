#!/usr/bin/env bash
# Manual Cloud Run deploy: build (linux/amd64), push to Artifact Registry, deploy.
# Superseded by GitHub Actions in NF-P1-020. Override any variable from the environment.
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT="${PROJECT:-nomadfinance-prod}"
REGION="${REGION:-asia-south1}"
SERVICE="${SERVICE:-nomadfinance-api}"
REPO="${REPO:-nomadfinance}"
RUNTIME_SA="${RUNTIME_SA:-nomadfinance-backend@${PROJECT}.iam.gserviceaccount.com}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/backend:${TAG}"

# Cloud Run only runs linux/amd64; Apple Silicon builds arm64 by default.
docker build --platform linux/amd64 -t "${IMAGE}" .
docker push "${IMAGE}"

gcloud run deploy "${SERVICE}" \
  --project "${PROJECT}" \
  --region "${REGION}" \
  --image "${IMAGE}" \
  --service-account "${RUNTIME_SA}" \
  --set-env-vars "APP_ENV=prod" \
  --allow-unauthenticated \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 2

URL="$(gcloud run services describe "${SERVICE}" --project "${PROJECT}" --region "${REGION}" \
  --format 'value(status.url)')"
echo "Deployed ${IMAGE}"
echo "Check: curl -s ${URL}/health"
