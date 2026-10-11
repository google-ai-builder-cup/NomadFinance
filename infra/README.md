# NomadFinance — Infrastructure

## Contents
- `cloud-scheduler/` — 5 cron jobs, one YAML each (refresh-rates, radar-aggregation, fib-recompute, scam-stats, coach-checkins). `scheduler-deploy.yml` creates or updates a job when its file is merged to `main`. The live project has the same five jobs.
- `iam/` — Service account structure and the permissions matrix (`service-accounts.md`, `permissions-matrix.md`), `setup-github-actions.sh` (one-time keyless deploy setup for GitHub Actions, NF-P1-020) and `grant-account-deletion-roles.sh` (the two roles account deletion needs)
- `monitoring/` — Log-based metrics, the dashboard and the Gemini daily-limit alerts, with `setup-monitoring.sh` (NF-F0-016; run once by hand, no workflow). `quota-limits.json` also feeds the backend's per-feature budget: `rpd_env.py` turns it into the `GEMINI_RPD_*` settings that `backend/scripts/deploy_manual.sh` sets (NF-HR-010)
- `release/` — `generate_changelog.py` builds a version's section of the root `CHANGELOG.md` from Conventional Commits (read-only on git), and `highlights-2.0.0.md` is the text under that version's heading and in its GitHub Release (NF-HR-011). Procedure: `docs/runbooks/NF-HR-011-release-v2.0.md`

## Not here, on purpose
- **Firestore and Storage rules, and the Firestore indexes** are in `frontend/` (`firestore.rules`, `storage.rules`, `firestore.indexes.json`), because the Firebase CLI only reads files next to `firebase.json` (NF-P1-014). The rules deploy from `main` by workflow; the indexes were created by hand and no workflow deploys them. What production holds is in `docs/data-model/firestore-schema.md`, "Required indexes".
- **Cloud Run settings** (CPU, memory, timeout, instances, secrets) are in `backend/scripts/deploy_manual.sh`. There is no Cloud Run YAML.

See `docs/runbooks/deploy-backend.md` for deployment procedures.
