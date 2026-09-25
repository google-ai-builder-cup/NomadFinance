# NomadFinance

**AI-powered financial protection for the world's 280 million migrant workers.**

Built for the Google Cloud AI Builder Cup 2026 — BFSI Track (JAPAC).

## What It Does

Four interconnected pillars protect migrant workers across the financial vulnerability lifecycle:

1. **Remittance X-Ray** — Real-time comparison of transfer providers using World Bank RPW data + live FX rates from a 4-provider failover chain (Frankfurter → ExchangeRate-API → CurrencyFreaks → Wise).
2. **Contract Shield** — 6-step Gemini-powered agentic pipeline: extracts contract text in any language, compares against curated ILO NATLEX labor laws for the host country, generates a risk-scored report and complaint template.
3. **Exploitation Radar** — Crowdsourced database of bad actors with Gemini-driven validation, embedding-based clustering, and community heatmap.
4. **Financial Identity Builder** — Portable financial profile with bill OCR, transaction categorization, and Gemini-synthesized narrative report for MFI/bank access at home.

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

## License

MIT — see [LICENSE](./LICENSE)
