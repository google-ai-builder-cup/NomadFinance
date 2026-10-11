# NomadFinance — Documentation

Start with [`design-doc/NomadFinance_Design_Document.md`](design-doc/NomadFinance_Design_Document.md), then the root `README.md` for how to run the project.

## Index
- `design-doc/` — The master design document
- `future-scope/` — The design addendum for the flag-gated Financial Coach and Scam Analyzer
- `features/` — One page per Future Scope feature: flow, models, limits, results (start with `features/scam-analyzer.md`)
- `api/` — The REST contract. `endpoints.md` is `/api/v1` and the internal Cloud Scheduler routes; `v2-conventions.md`, `v2-flags.md`, `v2-scam.md` and `v2-coach.md` are `/api/v2`. `openapi.json` is the machine-readable form, exported from the code
- `data-model/` — Every Firestore collection (`firestore-schema.md` is the map, `collections/` has the fields), the indexes and TTL policies, the Storage paths, and the versioning rules
- `mocks/` — Sample answers of the `/api/v2` routes, replayed by the frontend's tests and checked against the backend's models
- `pipelines/` — Deep dives for Contract Shield, Remittance X-Ray and Exploitation Radar. Financial Identity is described by its diagram, `collections/fib.md` and the NF-P3-010 to -014 runbooks
- `mermaid/` — Source `.mmd` files for all diagrams (the root `README.md` embeds one and links the rest)
- `prompts/` and `gemini-prompts.md` — The Gemini prompt library guide, and how each Future Scope prompt behaves and what to re-run after changing one
- `decisions/` — ADRs (Architecture Decision Records)
- `evals/` — Saved results of the scam golden set, injection suite and Coach regression runs
- `runbooks/` — One page per task (`<TASK-ID>-<slug>.md`) plus the operating procedures (deploy, data refresh, incident response)
- `design-system.md` and `ui-kit.md` — The visual language and the shared components
- `security-review-v2.md` — The OWASP API and prompt-injection review of the v2 surface
- `deferred-items.md` — Everything found and left for later, with an owner

## Key files
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Dev workflow and PR standards
- [`SECURITY.md`](SECURITY.md) — Security reporting
