# NomadFinance — Infrastructure

## Contents
•⁠  ⁠⁠ firebase/ ⁠ — an empty placeholder: the Firestore indexes are in `frontend/firestore.indexes.json` and were created by hand (D-33, D-114 in `docs/deferred-items.md`). Firestore and Storage rules live in frontend/ next to firebase.json, because the Firebase CLI only reads files inside that folder (NF-P1-014)
•⁠  ⁠⁠ cloud-run/ ⁠ — empty placeholders. The service's settings (CPU, memory, timeout, instances, secrets) are in `backend/scripts/deploy_manual.sh`
•⁠  ⁠⁠ cloud-scheduler/ ⁠ — 5 cron jobs, one YAML each (refresh-rates, radar-aggregation, fib-recompute, scam-stats, coach-checkins). `labor-law-check.yaml` is an empty placeholder that the deploy workflow skips
•⁠  ⁠⁠ iam/ ⁠ — Service account structure documentation and `setup-github-actions.sh` (one-time keyless deploy setup for GitHub Actions, NF-P1-020)
•⁠  ⁠⁠ monitoring/ ⁠ — Log-based metrics, the dashboard and the Gemini daily-limit alerts, with `setup-monitoring.sh` (NF-F0-016; run once by hand, no workflow). `quota-limits.json` also feeds the backend's per-feature budget: `rpd_env.py` turns it into the `GEMINI_RPD_*` settings that `backend/scripts/deploy_manual.sh` sets (NF-HR-010)
- `release/` — `generate_changelog.py` builds a version's section of the root `CHANGELOG.md` from Conventional Commits (read-only on git), and `highlights-2.0.0.md` is the text under that version's heading and in its GitHub Release (NF-HR-011). Procedure: `docs/runbooks/NF-HR-011-release-v2.0.md`

See ⁠ docs/runbooks/deploy-backend.md ⁠ for deployment procedures.
