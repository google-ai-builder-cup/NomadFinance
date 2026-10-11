Two new modules join the four pillars. Both ship behind feature flags and stay hidden until `config/feature_flags` turns them on, one at a time (Scam Analyzer first, then the Coach). With a flag off, its routes answer `404` and the app looks as it did in v1.0.

- **Scam Analyzer** (`scam`): a worker pastes a message, uploads a screenshot or shares it into the app, and gets a verdict, the tricks used, plain next steps with read-aloud, a history of checks, and a one-tap, anonymous report to Exploitation Radar.
- **Financial Coach** (`coach`): a short interview in the worker's own language, a preparedness score from 0 to 100, a 13-week plan with a PDF in six languages, and check-ins at day 30, 60 and 90.
- **Around them:** the `/api/v2` surface (standard error envelope, streaming replies, idempotency keys), PII redaction, log-based metrics, a dashboard and Gemini daily-limit alerts, a per-feature Gemini daily budget that degrades to "try again later", shared Coach and Scam signals for Financial Identity, a first-run tour on the home screen, and a security, performance and accessibility pass over the new screens.

Rollback is flag off first, then the previous Cloud Run revision and Hosting release: `docs/runbooks/NF-HR-011-release-v2.0.md`.
