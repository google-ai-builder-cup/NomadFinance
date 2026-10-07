# NomadFinance

**AI-powered financial protection for the world's 280 million migrant workers.**

Built for the Google Cloud AI Builder Cup 2026 — BFSI Track (JAPAC).

## What It Does

Four interconnected pillars protect migrant workers across the financial vulnerability lifecycle:

1. **Remittance X-Ray** — Real-time comparison of transfer providers using World Bank RPW data + live FX rates from a 4-provider failover chain (Frankfurter → ExchangeRate-API → CurrencyFreaks → Wise).
2. **Contract Shield** — 6-step Gemini-powered agentic pipeline: extracts contract text in any language, compares against curated ILO NATLEX labor laws for the host country, generates a risk-scored report and complaint template.
3. **Exploitation Radar** — Crowdsourced database of bad actors with Gemini-driven validation, embedding-based clustering, and community heatmap.
4. **Financial Identity Builder** — Portable financial profile with bill OCR, transaction categorization, and Gemini-synthesized narrative report for MFI/bank access at home.

### Future Scope features

Added behind feature flags, so they are off for everyone until switched on (`docs/api/v2-flags.md`).

| Feature | What it does | Docs |
|---|---|---|
| **Scam Analyzer** | A worker pastes a message or uploads a screenshot and gets a verdict, the tricks used and safe next steps in their own language, and can warn other workers through Exploitation Radar. | [Feature doc](./docs/features/scam-analyzer.md) · [Prompt notes](./docs/gemini-prompts.md) · [API contract](./docs/api/v2-scam.md) |

## Google Cloud Services

- **Firebase Authentication** — Google + Phone OTP sign-in
- **Cloud Firestore** — Primary NoSQL DB (all app data)
- **Cloud Storage** — Contract PDFs + generated reports
- **Cloud Run** — FastAPI backend container
- **Firebase Hosting** — React PWA + CDN
- **Cloud Scheduler** — 4 cron jobs (FX refresh, radar aggregation, FIB recompute, labor law change detection)
- **Gemini** (2.5 Flash + 1.5 Flash + Flash-Lite + text-embedding-004) — Multi-modal AI layer
- **Firebase Cloud Messaging** — Push notifications
- **Firebase Analytics** — Usage tracking

## JAPAC Scope

- **Host Countries (6):** Singapore, South Korea, Malaysia, Japan, Hong Kong, Australia
- **Corridors (6):** SG→PH, SG→IN, AU→IN, MY→ID, JP→PH, AU→PH
- **Languages (6):** English, Hindi, Tagalog, Bahasa Indonesia, Nepali, Bengali

## Repo Structure

backend/ # FastAPI service (Python 3.11, Cloud Run)
frontend/ # React 18 PWA (TypeScript, Vite, Firebase Hosting)
data-scripts/ # Data loaders (World Bank, ILO NATLEX, seed data)
infra/ # Firebase config, Cloud Run YAMLs, Scheduler configs
docs/ # Architecture, API contracts, ADRs, diagrams, runbooks
.github/ # CI/CD workflows, PR templates, issue templates


## Team

Built by the [google-ai-builder-cup](https://github.com/google-ai-builder-cup) team.

## Local Development

See individual folder READMEs:
- [backend/README.md](./backend/README.md)
- [frontend/README.md](./frontend/README.md)
- [data-scripts/README.md](./data-scripts/README.md)

Full docs: [docs/README.md](./docs/README.md)

## How to Test

Five kinds of test, from fastest to slowest. Commands are the same on macOS, Linux and Windows (PowerShell). Details, fixtures and examples: [`docs/runbooks/NF-F0-014-test-harness.md`](./docs/runbooks/NF-F0-014-test-harness.md).

| Kind | Where | Command | Needs |
|---|---|---|---|
| Backend unit and API tests, Gemini replaced by recordings | `backend/tests/unit`, `backend/tests/integration/api` | `cd backend && pytest` | the backend virtual environment active |
| Backend tests against the Firestore emulator, with seeded data | `backend/tests/integration` | `cd backend && firebase emulators:exec --only firestore,auth --project demo-nomadfinance --config ../frontend/firebase.json "python -m pytest tests/integration -q"` | the backend virtual environment active, Java 11+ and the Firebase CLI |
| Frontend unit and component tests, with the API mocked from `docs/mocks/` | `frontend/src/**/*.test.ts(x)` | `cd frontend && pnpm test` | `pnpm install` |
| Security-rule tests | `frontend/tests/rules` | `cd frontend && pnpm test:rules` | Java 11+ and the Firebase CLI |
| End-to-end tests in a real browser | `frontend/e2e` | `cd frontend && pnpm build && pnpm exec playwright install chromium && pnpm test:e2e` | a built app; the browser is downloaded once |

Point the end-to-end tests at another running copy of the app with `PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 pnpm test:e2e`. By default no test calls the real Gemini API or a real Google project: Gemini is replaced by recorded answers (`backend/tests/fixtures/gemini/`), the tests that call the real API run only with `RUN_LIVE_GEMINI=1`, and the emulator fixtures refuse to run against anything that is not on your own machine.

## License

MIT — see [LICENSE](./LICENSE)
