# NomadFinance — Infrastructure

## Contents
•⁠  ⁠⁠ firebase/ ⁠ — Firestore indexes. Firestore and Storage rules live in frontend/ next to firebase.json, because the Firebase CLI only reads files inside that folder (NF-P1-014)
•⁠  ⁠⁠ cloud-run/ ⁠ — Cloud Run service configuration
•⁠  ⁠⁠ cloud-scheduler/ ⁠ — 6 cron jobs (refresh-rates, radar-aggregation, fib-recompute, labor-law-check, scam-stats, coach-checkins)
•⁠  ⁠⁠ iam/ ⁠ — Service account structure documentation and `setup-github-actions.sh` (one-time keyless deploy setup for GitHub Actions, NF-P1-020)
•⁠  ⁠⁠ monitoring/ ⁠ — Log-based metrics, the dashboard and the Gemini daily-limit alerts, with `setup-monitoring.sh` (NF-F0-016; run once by hand, no workflow). `quota-limits.json` also feeds the backend's per-feature budget: `rpd_env.py` turns it into the `GEMINI_RPD_*` settings that `backend/scripts/deploy_manual.sh` sets (NF-HR-010)

See ⁠ docs/runbooks/deploy-backend.md ⁠ for deployment procedures.
