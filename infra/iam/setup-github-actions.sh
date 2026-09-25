#!/usr/bin/env bash
# One-time setup for the GitHub Actions workflows (NF-P1-020). Run by a project owner:
#
#   bash infra/iam/setup-github-actions.sh
#
# Creates a Workload Identity Federation pool for GitHub and three deployer service accounts.
# GitHub proves who it is with a short-lived OIDC token; Google trades it for a short-lived
# access token. No JSON key is created anywhere. Safe to run again: what already exists is kept.
#
# Google accepts only a run of THIS repository on the main branch (the provider condition), so
# other branches, forks and pull requests cannot deploy. Undo: see the runbook, "Remove it".
set -euo pipefail

PROJECT="${PROJECT:-nomadfinance-prod}"
REGION="${REGION:-asia-south1}"
REPO="${REPO:-google-ai-builder-cup/NomadFinance}"
POOL="github"
PROVIDER="github"

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)')"
PRINCIPAL="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"

BACKEND_DEPLOYER="nomadfinance-deploy-backend"
FRONTEND_DEPLOYER="nomadfinance-deploy-frontend"
INFRA_DEPLOYER="nomadfinance-deploy-infra"
sa_email() { echo "$1@${PROJECT}.iam.gserviceaccount.com"; }

exists() { "$@" >/dev/null 2>&1; }

echo "== 1. APIs"
gcloud services enable sts.googleapis.com iamcredentials.googleapis.com --project "${PROJECT}"

echo "== 2. Workload Identity pool and GitHub provider"
if ! exists gcloud iam workload-identity-pools describe "${POOL}" --project "${PROJECT}" --location global; then
  gcloud iam workload-identity-pools create "${POOL}" --project "${PROJECT}" --location global \
    --display-name "GitHub Actions"
fi
if ! exists gcloud iam workload-identity-pools providers describe "${PROVIDER}" \
  --project "${PROJECT}" --location global --workload-identity-pool "${POOL}"; then
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER}" \
    --project "${PROJECT}" --location global --workload-identity-pool "${POOL}" \
    --display-name "GitHub OIDC" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "assertion.repository=='${REPO}' && assertion.ref=='refs/heads/main'"
fi

echo "== 3. Deployer service accounts"
for id in "${BACKEND_DEPLOYER}" "${FRONTEND_DEPLOYER}" "${INFRA_DEPLOYER}"; do
  if ! exists gcloud iam service-accounts describe "$(sa_email "${id}")" --project "${PROJECT}"; then
    gcloud iam service-accounts create "${id}" --project "${PROJECT}" \
      --display-name "GitHub Actions deploy (${id#nomadfinance-deploy-})"
  fi
done

project_role() { # <service account id> <role>
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member "serviceAccount:$(sa_email "$1")" --role "$2" --condition=None >/dev/null
  echo "   $1 -> $2 (project)"
}

echo "== 4. Backend deployer: build, push, deploy the Cloud Run service"
gcloud run services add-iam-policy-binding nomadfinance-api --project "${PROJECT}" --region "${REGION}" \
  --member "serviceAccount:$(sa_email "${BACKEND_DEPLOYER}")" --role roles/run.admin >/dev/null
echo "   ${BACKEND_DEPLOYER} -> roles/run.admin (service nomadfinance-api only)"
gcloud artifacts repositories add-iam-policy-binding nomadfinance --project "${PROJECT}" --location "${REGION}" \
  --member "serviceAccount:$(sa_email "${BACKEND_DEPLOYER}")" --role roles/artifactregistry.writer >/dev/null
echo "   ${BACKEND_DEPLOYER} -> roles/artifactregistry.writer (repo nomadfinance only)"
gcloud iam service-accounts add-iam-policy-binding "$(sa_email nomadfinance-backend)" --project "${PROJECT}" \
  --member "serviceAccount:$(sa_email "${BACKEND_DEPLOYER}")" --role roles/iam.serviceAccountUser >/dev/null
echo "   ${BACKEND_DEPLOYER} -> roles/iam.serviceAccountUser (act as nomadfinance-backend only)"
# Metadata only: the script asks whether the optional secrets exist. It cannot read a value.
project_role "${BACKEND_DEPLOYER}" roles/secretmanager.viewer
project_role "${BACKEND_DEPLOYER}" roles/serviceusage.serviceUsageConsumer

echo "== 5. Frontend deployer: Firebase Hosting"
project_role "${FRONTEND_DEPLOYER}" roles/firebasehosting.admin
project_role "${FRONTEND_DEPLOYER}" roles/firebase.viewer
project_role "${FRONTEND_DEPLOYER}" roles/serviceusage.serviceUsageConsumer

echo "== 6. Infra deployer: Firestore and Storage rules, Cloud Scheduler jobs"
project_role "${INFRA_DEPLOYER}" roles/firebaserules.admin
project_role "${INFRA_DEPLOYER}" roles/firebase.viewer
project_role "${INFRA_DEPLOYER}" roles/cloudscheduler.admin
project_role "${INFRA_DEPLOYER}" roles/serviceusage.serviceUsageConsumer
gcloud iam service-accounts add-iam-policy-binding "$(sa_email nomadfinance-scheduler)" --project "${PROJECT}" \
  --member "serviceAccount:$(sa_email "${INFRA_DEPLOYER}")" --role roles/iam.serviceAccountUser >/dev/null
echo "   ${INFRA_DEPLOYER} -> roles/iam.serviceAccountUser (act as nomadfinance-scheduler only)"

echo "== 7. Let this repository's GitHub identity use each deployer"
for id in "${BACKEND_DEPLOYER}" "${FRONTEND_DEPLOYER}" "${INFRA_DEPLOYER}"; do
  gcloud iam service-accounts add-iam-policy-binding "$(sa_email "${id}")" --project "${PROJECT}" \
    --member "${PRINCIPAL}" --role roles/iam.workloadIdentityUser >/dev/null
  echo "   ${REPO} -> ${id} (workloadIdentityUser)"
done

echo
echo "Done. The workflows use this provider:"
echo "  projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
