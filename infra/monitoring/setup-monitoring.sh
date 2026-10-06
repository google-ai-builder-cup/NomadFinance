#!/usr/bin/env bash
# One-time setup of the observability resources (NF-F0-016). Run by a project owner:
#
#   ALERT_EMAILS="a@example.com,b@example.com,c@example.com" bash infra/monitoring/setup-monitoring.sh
#
# Creates, in project nomadfinance-prod: the log-based metrics, the dashboard, an email
# notification channel per address, and one alert per Gemini model at 80% of its daily limit.
# Safe to run again: metrics are updated in place, and the dashboard and the alerts are replaced.
#
#   DRY_RUN=1   print what would run, change nothing
#   PROJECT     default nomadfinance-prod
#
# Needs: gcloud (logged in as someone with roles/logging.configWriter and roles/monitoring.editor,
# or an owner), curl and python3. The alerts need real daily limits in quota-limits.json: a model
# whose limit is still null is skipped, and the script ends with exit code 3 to say so.
# Nothing here is deployed by a workflow: run it by hand, then check the dashboard.
set -euo pipefail

PROJECT="${PROJECT:-nomadfinance-prod}"
DRY_RUN="${DRY_RUN:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

run() { if [ -n "${DRY_RUN}" ]; then echo "[dry run] $*"; else "$@"; fi; }
exists() { "$@" >/dev/null 2>&1; }

echo "== 1. Log-based metrics"
for file in "${HERE}"/metrics/*.json; do
  name="$(basename "${file}" .json)"
  if exists gcloud logging metrics describe "${name}" --project "${PROJECT}"; then
    run gcloud logging metrics update "${name}" --config-from-file="${file}" --project "${PROJECT}"
    echo "   updated ${name}"
  else
    run gcloud logging metrics create "${name}" --config-from-file="${file}" --project "${PROJECT}"
    echo "   created ${name}"
  fi
done

echo "== 2. Dashboard"
DASHBOARD_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["displayName"])' "${HERE}/dashboard.json")"
existing="$(gcloud monitoring dashboards list --project "${PROJECT}" \
  --filter="displayName=\"${DASHBOARD_NAME}\"" --format='value(name)' 2>/dev/null || true)"
for old in ${existing}; do
  run gcloud monitoring dashboards delete "${old}" --project "${PROJECT}" --quiet
  echo "   replaced ${old}"
done
run gcloud monitoring dashboards create --config-from-file="${HERE}/dashboard.json" --project "${PROJECT}"

echo "== 3. Notification channels (email)"
CHANNELS=()
if [ -z "${ALERT_EMAILS:-}" ]; then
  echo "   ALERT_EMAILS is not set: no channel, so no alerts will be created (step 4)."
else
  TOKEN="$(gcloud auth print-access-token)"
  API="https://monitoring.googleapis.com/v3/projects/${PROJECT}/notificationChannels"
  IFS=',' read -r -a ADDRESSES <<<"${ALERT_EMAILS}"
  for address in "${ADDRESSES[@]}"; do
    address="$(echo "${address}" | tr -d '[:space:]')"
    [ -z "${address}" ] && continue
    if [ -n "${DRY_RUN}" ]; then
      echo "[dry run] ensure an email notification channel for ${address}"
      CHANNELS+=("projects/${PROJECT}/notificationChannels/DRY-RUN")
      continue
    fi
    found="$(curl -fsS -H "Authorization: Bearer ${TOKEN}" -G "${API}" \
      --data-urlencode "filter=type=\"email\" AND labels.email_address=\"${address}\"" \
      | python3 -c 'import json,sys; c=json.load(sys.stdin).get("notificationChannels",[]); print(c[0]["name"] if c else "")')"
    if [ -z "${found}" ]; then
      found="$(curl -fsS -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" "${API}" \
        -d "{\"type\":\"email\",\"displayName\":\"NomadFinance alerts: ${address}\",\"labels\":{\"email_address\":\"${address}\"}}" \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"
      echo "   created channel for ${address}"
    else
      echo "   channel exists for ${address}"
    fi
    CHANNELS+=("${found}")
  done
fi

echo "== 4. Alert per Gemini model (80% of the daily limit)"
status=0
if [ "${#CHANNELS[@]}" -eq 0 ]; then
  echo "   skipped: no notification channel"
  status=3
else
  python3 "${HERE}/render_policies.py" "${WORK}/policies" "${CHANNELS[@]}" || status=$?
  if [ "${status}" -ne 0 ] && [ "${status}" -ne 3 ]; then exit "${status}"; fi
  for file in "${WORK}"/policies/*.json; do
    [ -e "${file}" ] || continue
    display="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["displayName"])' "${file}")"
    old="$(gcloud monitoring policies list --project "${PROJECT}" \
      --filter="displayName=\"${display}\"" --format='value(name)' 2>/dev/null || true)"
    for policy in ${old}; do
      run gcloud monitoring policies delete "${policy}" --project "${PROJECT}" --quiet
      echo "   replaced ${display}"
    done
    run gcloud monitoring policies create --policy-from-file="${file}" --project "${PROJECT}"
    echo "   created ${display}"
  done
fi

echo
echo "Done. Dashboard: https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT}"
if [ "${status}" -eq 3 ]; then
  echo "NOT everything was created: see the SKIPPED / skipped lines above (fill rpd in quota-limits.json, set ALERT_EMAILS)."
  exit 3
fi
