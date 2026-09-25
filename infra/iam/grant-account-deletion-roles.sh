#!/usr/bin/env bash
# One-time grant for "Delete my account" (NF-P1-023). Run by a project owner:
#
#   bash infra/iam/grant-account-deletion-roles.sh
#
# The backend deletes an account with the Firebase Admin SDK, running as the Cloud Run service
# account. Deleting Firestore data already works (roles/datastore.user). Two more things need a
# role, or the endpoint answers 503 in production:
#   - deleting the sign-in account:      roles/firebaseauth.admin
#   - deleting the user's uploaded files: roles/storage.objectUser, on the Firebase Storage bucket only
# Safe to run again. Undo: see the runbook, "Remove the grants".
set -euo pipefail

PROJECT="${PROJECT:-nomadfinance-prod}"
BUCKET="${BUCKET:-${PROJECT}.firebasestorage.app}"
RUNTIME_SA="${RUNTIME_SA:-nomadfinance-backend@${PROJECT}.iam.gserviceaccount.com}"

echo "== Delete sign-in accounts (project)"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/firebaseauth.admin --condition=None >/dev/null
echo "   ${RUNTIME_SA} -> roles/firebaseauth.admin"

echo "== Delete uploaded files (this bucket only)"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${RUNTIME_SA}" --role roles/storage.objectUser >/dev/null
echo "   ${RUNTIME_SA} -> roles/storage.objectUser on gs://${BUCKET}"

echo
echo "Done. Check: gcloud projects get-iam-policy ${PROJECT} --flatten='bindings[].members' \\"
echo "  --filter='bindings.members:${RUNTIME_SA}' --format='value(bindings.role)'"
