# NomadFinance — Infrastructure

## Contents
•⁠  ⁠⁠ firebase/ ⁠ — Firestore indexes. Firestore and Storage rules live in frontend/ next to firebase.json, because the Firebase CLI only reads files inside that folder (NF-P1-014)
•⁠  ⁠⁠ cloud-run/ ⁠ — Cloud Run service configuration
•⁠  ⁠⁠ cloud-scheduler/ ⁠ — 4 cron jobs (refresh-rates, radar-aggregation, fib-recompute, labor-law-check)
•⁠  ⁠⁠ iam/ ⁠ — Service account structure documentation

See ⁠ docs/runbooks/deploy-backend.md ⁠ for deployment procedures.
