# Changelog

Every release of NomadFinance. Versions follow [Semantic Versioning](https://semver.org).
Each section is built from Conventional Commits by `infra/release/generate_changelog.py`:
run it again when new commits land, and never edit between the markers by hand.

<!-- changelog:2.0.0:start -->
## [2.0.0] - 2026-10-11

Two new modules join the four pillars. Both ship behind feature flags and stay hidden until `config/feature_flags` turns them on, one at a time (Scam Analyzer first, then the Coach). With a flag off, its routes answer `404` and the app looks as it did in v1.0.

- **Scam Analyzer** (`scam`): a worker pastes a message, uploads a screenshot or shares it into the app, and gets a verdict, the tricks used, plain next steps with read-aloud, a history of checks, and a one-tap, anonymous report to Exploitation Radar.
- **Financial Coach** (`coach`): a short interview in the worker's own language, a preparedness score from 0 to 100, a 13-week plan with a PDF in six languages, and check-ins at day 30, 60 and 90.
- **Around them:** the `/api/v2` surface (standard error envelope, streaming replies, idempotency keys), PII redaction, log-based metrics, a dashboard and Gemini daily-limit alerts, a per-feature Gemini daily budget that degrades to "try again later", shared Coach and Scam signals for Financial Identity, a first-run tour on the home screen, and a security, performance and accessibility pass over the new screens.

Rollback is flag off first, then the previous Cloud Run revision and Hosting release: `docs/runbooks/NF-HR-011-release-v2.0.md`.

82 commits in 71 pull requests (#108 to #178) since `6117b4f`, up to `abcf536`.

### Features

- **coach:** add interview slots and question bank ([#145](https://github.com/google-ai-builder-cup/NomadFinance/pull/145), NF-FC-001)
- **coach:** add SG and AU cost baselines and loader ([#147](https://github.com/google-ai-builder-cup/NomadFinance/pull/147), NF-FC-003)
- **coach:** add KR and MY cost baselines ([#148](https://github.com/google-ai-builder-cup/NomadFinance/pull/148), NF-FC-004)
- **coach:** add JP and HK cost baselines ([#149](https://github.com/google-ai-builder-cup/NomadFinance/pull/149), NF-FC-005)
- **coach:** add session state machine and session routes ([#152](https://github.com/google-ai-builder-cup/NomadFinance/pull/152), NF-FC-008)
- **coach:** add turn endpoint with streamed replies ([#153](https://github.com/google-ai-builder-cup/NomadFinance/pull/153), NF-FC-009)
- **coach:** add slot extraction with checked answers and follow-ups ([#154](https://github.com/google-ai-builder-cup/NomadFinance/pull/154), NF-FC-010)
- **coach:** add preparedness scoring engine with fee cap and live rates ([#155](https://github.com/google-ai-builder-cup/NomadFinance/pull/155), NF-FC-011)
- **coach:** add 90-day plan generator with checked figures ([#156](https://github.com/google-ai-builder-cup/NomadFinance/pull/156), NF-FC-012)
- **coach:** add plan translation and PDF export ([#157](https://github.com/google-ai-builder-cup/NomadFinance/pull/157), NF-FC-014)
- **coach:** add guardrails for scope, injection, advice and distress ([#158](https://github.com/google-ai-builder-cup/NomadFinance/pull/158), NF-FC-013)
- **coach:** add day 30, 60 and 90 check-in reminders ([#159](https://github.com/google-ai-builder-cup/NomadFinance/pull/159), NF-FC-016)
- **coach:** add chat screen with streamed replies and answer helpers ([#160](https://github.com/google-ai-builder-cup/NomadFinance/pull/160), NF-FC-017)
- **coach:** add contract prefill and Financial Identity goals ([#161](https://github.com/google-ai-builder-cup/NomadFinance/pull/161), NF-FC-015)
- **coach:** add voice input, language switch and welcome-band shortcuts ([#162](https://github.com/google-ai-builder-cup/NomadFinance/pull/162), NF-FC-018)
- **coach:** add resume banner, drafts and offline answer queue ([#163](https://github.com/google-ai-builder-cup/NomadFinance/pull/163), NF-FC-019)
- **coach:** add preparedness score screen and the review-to-plan step ([#164](https://github.com/google-ai-builder-cup/NomadFinance/pull/164), NF-FC-020)
- **coach:** add 90-day plan view with PDF download and share ([#165](https://github.com/google-ai-builder-cup/NomadFinance/pull/165), NF-FC-021)
- **coach:** add check-in answers route for day 30, 60 and 90 ([#166](https://github.com/google-ai-builder-cup/NomadFinance/pull/166), NF-FC-022)
- **coach:** add review table, known answers card and accessibility pass ([#167](https://github.com/google-ai-builder-cup/NomadFinance/pull/167), NF-FC-023)
- **coach:** deffered updated (`27ecde0`)
- **dashboard:** add scam card status, first-run tour and phone layout ([#172](https://github.com/google-ai-builder-cup/NomadFinance/pull/172), NF-HR-002)
- **data:** add security rules and indexes for coach and scam collections ([#111](https://github.com/google-ai-builder-cup/NomadFinance/pull/111), NF-F0-004)
- **data:** seed demo coach plans and scam checks for the finale ([#173](https://github.com/google-ai-builder-cup/NomadFinance/pull/173), NF-HR-003)
- **fib:** add shared coach and scam signals and an activity feed ([#171](https://github.com/google-ai-builder-cup/NomadFinance/pull/171), NF-HR-001)
- **flags:** add feature flag service and require_flag dependency ([#112](https://github.com/google-ai-builder-cup/NomadFinance/pull/112), NF-F0-005)
- **frontend:** add feature flag hook, gate and lazy routes for coach and scam, docs(data-model): correct the collection-group index command ([#113](https://github.com/google-ai-builder-cup/NomadFinance/pull/113), NF-F0-006)
- **gemini:** add chat, streaming and usage logging to the Gemini client ([#114](https://github.com/google-ai-builder-cup/NomadFinance/pull/114), NF-F0-007)
- **gemini:** add per-feature daily quota budget and graceful degrade ([#178](https://github.com/google-ai-builder-cup/NomadFinance/pull/178), NF-HR-010)
- **i18n:** add coach and scam namespaces and a missing-key check ([#117](https://github.com/google-ai-builder-cup/NomadFinance/pull/117), NF-F0-013)
- **landing:** add Scam Check and Coach to the ecosystem diagram (`d27c8d0`)
- **observability:** add log fields, metrics, dashboard and quota alerts ([#121](https://github.com/google-ai-builder-cup/NomadFinance/pull/121), NF-F0-016)
- **redact:** add PII redaction for phones, emails, IDs, accounts and URLs ([#115](https://github.com/google-ai-builder-cup/NomadFinance/pull/115), NF-F0-008)
- **scam:** add scam taxonomy data, validator and loader ([#122](https://github.com/google-ai-builder-cup/NomadFinance/pull/122), NF-SA-001)
- **scam:** add english and hindi golden eval set and validator ([#124](https://github.com/google-ai-builder-cup/NomadFinance/pull/124), NF-SA-003)
- **scam:** add tagalog and indonesian golden eval set ([#125](https://github.com/google-ai-builder-cup/NomadFinance/pull/125), NF-SA-004)
- **scam:** add nepali and bengali golden eval set ([#126](https://github.com/google-ai-builder-cup/NomadFinance/pull/126), NF-SA-005)
- **scam:** add scam pattern library with gemini embeddings ([#127](https://github.com/google-ai-builder-cup/NomadFinance/pull/127), NF-SA-006)
- **scam:** add text analyze endpoint with structured verdict ([#128](https://github.com/google-ai-builder-cup/NomadFinance/pull/128), NF-SA-007)
- **scam:** add screenshot path with vision ocr to analyze endpoint ([#129](https://github.com/google-ai-builder-cup/NomadFinance/pull/129), NF-SA-008)
- **scam:** add psychology explainer and safe next steps to analyze ([#130](https://github.com/google-ai-builder-cup/NomadFinance/pull/130), NF-SA-009)
- **scam:** add similar-scam retrieval to analyze ([#131](https://github.com/google-ai-builder-cup/NomadFinance/pull/131), NF-SA-010)
- **scam:** add indicator extraction to analyze ([#132](https://github.com/google-ai-builder-cup/NomadFinance/pull/132), NF-SA-011)
- **scam:** store checks, add hash cache, history and hourly limit ([#133](https://github.com/google-ai-builder-cup/NomadFinance/pull/133), NF-SA-012)
- **scam:** add one-tap report of a scam check to radar ([#134](https://github.com/google-ai-builder-cup/NomadFinance/pull/134), NF-SA-013)
- **scam:** add check screen with upload, camera and share target ([#136](https://github.com/google-ai-builder-cup/NomadFinance/pull/136), NF-SA-015)
- **scam:** add verdict card with risk meter, tactics and highlights ([#137](https://github.com/google-ai-builder-cup/NomadFinance/pull/137), NF-SA-016)
- **scam:** add explainer section, numbered steps and read-aloud ([#138](https://github.com/google-ai-builder-cup/NomadFinance/pull/138), NF-SA-017)
- **scam:** add check history and report-to-Radar flow ([#139](https://github.com/google-ai-builder-cup/NomadFinance/pull/139), NF-SA-018)
- **scam:** add analytics events and weekly corridor counts ([#143](https://github.com/google-ai-builder-cup/NomadFinance/pull/143), NF-SA-022)
- **ui:** add shared chat, risk, step and timeline components ([#119](https://github.com/google-ai-builder-cup/NomadFinance/pull/119), NF-F0-012)

### Bug fixes

- **accessibility:** fix contrast, names and headings found by axe ([#177](https://github.com/google-ai-builder-cup/NomadFinance/pull/177), NF-HR-009)
- **auth:** use anonymous credentials when running against the emulators ([#118](https://github.com/google-ai-builder-cup/NomadFinance/pull/118), NF-F0-010)
- **frontend:** run the Firestore rules test files one at a time ([#174](https://github.com/google-ai-builder-cup/NomadFinance/pull/174), NF-F0-010)
- **scam:** allow 90 s for the analyze request (`71e8620`, NF-SA-015)
- **scam:** fix contrast, focus and tap targets found by an axe audit ([#140](https://github.com/google-ai-builder-cup/NomadFinance/pull/140), NF-SA-019)
- **scam:** stub navigator in report error test for Node 20 ([#140](https://github.com/google-ai-builder-cup/NomadFinance/pull/140), NF-SA-019)

### Documentation

- **api:** add API v2 conventions and error envelope mocks feat(api): answer /api/v2 errors in the standard envelope ([#109](https://github.com/google-ai-builder-cup/NomadFinance/pull/109), NF-F0-002)
- **api:** add scam analyzer contract, schemas and mocks ([#123](https://github.com/google-ai-builder-cup/NomadFinance/pull/123), NF-SA-002)
- **api:** add coach contract, schemas and mocks ([#146](https://github.com/google-ai-builder-cup/NomadFinance/pull/146), NF-FC-002)
- **coach:** add preparedness scoring rubric ([#150](https://github.com/google-ai-builder-cup/NomadFinance/pull/150), NF-FC-006)
- **coach:** add Financial Coach feature doc and prompt notes ([#170](https://github.com/google-ai-builder-cup/NomadFinance/pull/170), NF-FC-026)
- **data-model:** add schema for coach, scam and baseline collections ([#110](https://github.com/google-ai-builder-cup/NomadFinance/pull/110), NF-F0-003)
- **future-scope:** add coach and scam analyzer design addendum ([#108](https://github.com/google-ai-builder-cup/NomadFinance/pull/108), NF-F0-001)
- **runbooks:** add NF-F0-001 and NF-FC-006 runbooks (`2a45703`, NF-F0-001, NF-FC-006)
- **scam:** add feature page, prompt notes and eval baseline ([#142](https://github.com/google-ai-builder-cup/NomadFinance/pull/142), NF-SA-021)

### Tests

- **coach:** add twelve regression personas ([#151](https://github.com/google-ai-builder-cup/NomadFinance/pull/151), NF-FC-007)
- **coach:** add multi-turn persona regression runner ([#168](https://github.com/google-ai-builder-cup/NomadFinance/pull/168), NF-FC-024)
- **coach:** add Playwright end-to-end tests for the coach ([#169](https://github.com/google-ai-builder-cup/NomadFinance/pull/169), NF-FC-025)
- **fib:** stub the coach plan repository in the recompute endpoint test ([#161](https://github.com/google-ai-builder-cup/NomadFinance/pull/161), NF-FC-015)
- **harness:** add emulator fixtures, fake Gemini, MSW and Playwright ([#120](https://github.com/google-ai-builder-cup/NomadFinance/pull/120), NF-F0-014)
- **perf:** add load harness and v2 performance profiling runbook ([#174](https://github.com/google-ai-builder-cup/NomadFinance/pull/174), NF-HR-007)
- **regression:** add regression suite A and fix its five bugs ([#175](https://github.com/google-ai-builder-cup/NomadFinance/pull/175), NF-HR-004)
- **scam:** add offline eval runner with f1 quality bar ([#135](https://github.com/google-ai-builder-cup/NomadFinance/pull/135), NF-SA-014)
- **scam:** add browser tests and prompt-injection suite ([#141](https://github.com/google-ai-builder-cup/NomadFinance/pull/141), NF-SA-020)
- **scam:** add stress set and confidence report, keep classify v2 ([#144](https://github.com/google-ai-builder-cup/NomadFinance/pull/144), NF-SA-023)
- **security:** review v2 routes and fix JSON cap, headers, reply links ([#176](https://github.com/google-ai-builder-cup/NomadFinance/pull/176), NF-HR-008)

### Chores

- **ci:** add commit policy hooks and commitlint check ([#116](https://github.com/google-ai-builder-cup/NomadFinance/pull/116), NF-F0-009)
- **ci:** add coverage gates, emulator tests and a commit-policy check ([#118](https://github.com/google-ai-builder-cup/NomadFinance/pull/118), NF-F0-010)
- **coach:** add missing files ([#160](https://github.com/google-ai-builder-cup/NomadFinance/pull/160), NF-FC-017)
- **frontend:** remove a generated test report from version control ([#119](https://github.com/google-ai-builder-cup/NomadFinance/pull/119), NF-F0-012)
<!-- changelog:2.0.0:end -->
