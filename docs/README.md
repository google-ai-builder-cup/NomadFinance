# NomadFinance — Documentation

Start with the root `README.md` for what the project is and how to run it.

## Index
- `api/` — The REST contract. `endpoints.md` is `/api/v1` and the internal Cloud Scheduler routes; `v2-conventions.md`, `v2-flags.md`, `v2-scam.md` and `v2-coach.md` are `/api/v2`. `openapi.json` is the machine-readable form, exported from the code
- `data-model/` — Every Firestore collection (`firestore-schema.md` is the map, `collections/` has the fields), the indexes and TTL policies, the Storage paths, and the versioning rules
- `mocks/` — Sample answers of the `/api/v2` routes, replayed by the frontend's tests and checked against the backend's models
- `mermaid/` — Source `.mmd` files for all diagrams (the root `README.md` embeds one and links the rest)
- `gemini-prompts.md` — How each Future Scope prompt behaves and what to re-run after changing one. The prompt-file table is in `backend/app/prompts/README.md`
- `decisions/` — ADRs (Architecture Decision Records)
- `evals/` — Saved results of the scam golden set, injection suite and Coach regression runs
- `runbooks/` — One page per task (`<TASK-ID>-<slug>.md`) plus the deploy procedures (`deploy-backend.md`, `deploy-frontend.md`)
- `release-notes/` — What each release contains
- `security-review-v2.md` — The OWASP API and prompt-injection review of the v2 surface

## Key files
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Dev workflow and PR standards
- [`SECURITY.md`](SECURITY.md) — Security reporting
