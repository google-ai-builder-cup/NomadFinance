# NF-HR-012 — README and architecture diagrams for v2.0

## Summary

The root `README.md` is rewritten so a stranger can understand the project, run it on their own machine from a fresh clone, and find everything else. The two diagrams the tracker names, `system-architecture.mmd` and `cross-pillar-data-flow.mmd`, are redrawn to match the code and the live Google project as of 2026-10-11 (v2.0.0, after NF-HR-011).

| File | What changed |
|---|---|
| [`README.md`](../../README.md) | Rewritten. The problem in plain words; one worker's six moments (with a diagram); the six pillars; why it can be trusted; numbers that can be checked; how it works (model tiers, data stores, background jobs); scope; Google Cloud services; a verified Quick start; configuration reference; tests and checks; CI/CD and operations; repository and documentation maps; contributing |
| [`docs/mermaid/system-architecture.mmd`](../mermaid/system-architecture.mmd) | Redrawn. v2.0.0 is no longer "not yet deployed". All 5 Scheduler jobs (it showed 2), the Gemini tiers by role, the full set of Firestore stores, Cloud Storage, Secret Manager, FCM, the per-feature Gemini budget, observability and delivery. Left to right, 3,356 × 3,493 units (the old one was 6,937 × 1,756) |
| [`docs/mermaid/cross-pillar-data-flow.mmd`](../mermaid/cross-pillar-data-flow.mmd) | Redrawn. Solid lines are v1.0 flows, dotted lines involve a flag-gated module. Two flows added that the code has and the old diagram lacked: Financial Identity to Coach ("known answers", the worker confirms) and Exploitation Radar to Coach (flagged operators passed over in the plan). Consent is written on each edge |
| [`backend/README.md`](../../backend/README.md), [`frontend/README.md`](../../frontend/README.md), [`infra/README.md`](../../infra/README.md) | Small corrections to statements that are no longer true (listed below) |

No code, workflow, rule or other shared file was touched.

## Flow: where each fact comes from

```text
code (config.py, services, rules)  ─┐
live project (read-only commands)  ─┼─►  README.md  ─►  links to  ─►  docs/mermaid/*.mmd
accepted ADRs and eval reports     ─┘        │                         docs/api, docs/runbooks
                                             └─►  Quick start  ─►  verified in a fresh clone of main
```

Every number in the README comes from a file or a command named in this runbook. Things that could not be shown were left out on purpose: there is no Coach pass rate (no live Coach regression run exists, D-258) and no Lighthouse score (NF-HR-007 is partly done).

## What the old README and diagrams got wrong

| Said | Reality (source) |
|---|---|
| Gemini 2.5 Flash, 1.5 Flash, Flash-Lite, `text-embedding-004` | `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-embedding-001` (`app/config.py`, ADR-002). The README and diagrams now name the *tier*, with the defaults in one table |
| 4 cron jobs, one of them "labor law change detection" | 5 jobs; `labor-law-check.yaml` is empty and no such endpoint exists (live Scheduler lists 5) |
| Emulators need Java 11+ | firebase-tools 15.31.0 refuses anything below Java 21 |
| Two required environment variables | Three: `APP_ENV`, `GEMINI_API_KEY`, `RADAR_REPORTER_HASH_SECRET` |
| "See the folder READMEs" for local run | Emulator variables must be shell variables (nothing loads `.env.local` into them); no loader exists for `config/feature_flags` or the rates |
| e2e: `pnpm build` then `pnpm test:e2e` | CI builds with `--mode emulator` and runs inside `firebase emulators:exec` |
| Repository tree outside a code fence | Rendered as one run-on paragraph |
| Architecture diagram: "Not yet deployed" | v2.0.0 shipped (CHANGELOG) |
| Contract files uploaded to Cloud Storage (old pillar diagram, old wording) | `services/contract/upload.py`: the file's bytes are never stored, only its text. Bill photos, Radar evidence and PDFs are what Cloud Storage holds |

Corrections to the three folder READMEs: `backend/README.md` (three required variables, the `api/v2` folder, deploy is automatic now), `frontend/README.md` (the pillar pages are real, the install offer is a toast, deploy is automatic now; closes D-47), `infra/README.md` (5 jobs, and the empty placeholder folders say so).

## Commands

Re-read the live facts the README and the architecture diagram state (all read-only; run them with a Google login that can read `nomadfinance-prod`):

```bash
gcloud scheduler jobs list --project nomadfinance-prod --location asia-south1
gcloud run services describe nomadfinance-api --project nomadfinance-prod --region asia-south1
gcloud firestore databases list --project nomadfinance-prod
gcloud firestore indexes composite list --project nomadfinance-prod
gcloud firestore fields ttls list --project nomadfinance-prod
gcloud secrets list --project nomadfinance-prod
```

Check a README after editing it: every relative link must point at a real file and every in-page anchor at a real heading (GitHub's rules for turning a heading into an anchor), and the fenced blocks must balance. The diagrams are plain Mermaid; GitHub draws `.mmd` files, and they were rendered here with Mermaid 11.4.1 (`mermaid.parse` then `mermaid.render` over all eight files plus the README's own diagram).

Run the project the way the README says: the Quick start in [`README.md`](../../README.md#run-it-on-your-machine), in a clone made with `git clone -c core.autocrlf=false`.

## Decisions that were not in the task text

| # | Decision | Why |
|---|---|---|
| 1 | Models are named by tier (reasoning, extraction, classification, embedding), with the default model ids in one README table | The team's standing instructions and the original design say 2.5 / 1.5 Flash; the code and the accepted ADR-002 say 3.5 / 3.1. ADR-002 already tells readers to read the tier names as the roles. A model swap is an environment variable, so a diagram that hard-codes a version goes stale |
| 2 | The architecture diagram groups: one node for the five jobs, one per group of Firestore stores, the frontend pages in two nodes | The first version (one node per job, store and page) was 6,000 units wide and unreadable on GitHub; the grouped one is about half the width and square |
| 3 | The cross-pillar diagram has no sub-boxes, and solid versus dotted means "v1.0 versus flag-gated" | Sub-boxes made edges loop round them; the dashed outline already marks the two flagged modules |
| 4 | The README does not state whether the flags are on in production | `config/feature_flags` is an operator's switch and D-291 records that it was already on before the release rehearsal. The README explains the mechanism and leaves the state to the console |
| 5 | The Quick start uses emulators only, and says so loudly at the data-loading step | The loaders default to `nomadfinance-prod` (D-300). A callout and "set the emulator variables first" cost nothing |
| 6 | Flags and rates are set with a pasted snippet and a scratch script, not a new loader | A loader is code, and this task changes none. D-299 asks for the loaders |
| 7 | The README links the diagrams instead of embedding them, except one small journey diagram | One source of truth for the detailed diagrams. The journey diagram is conceptual and cannot drift |
| 8 | Two diagrams of six pillars (the six `*-pipeline.mmd` files) were left alone | The tracker names two diagrams. Their old model names are logged as D-303 |

## Checks run (2026-10-11)

Everything below was run in **a fresh clone of the committed `main`** (`a5fe509`) on Windows 11 with Git's default CRLF line endings, except the two last rows.

| Check | Result |
|---|---|
| README: relative links and anchors | 85 links and 38 headings, all resolve; same for the three folder READMEs |
| Mermaid 11.4.1: 8 `.mmd` files and the README's diagram | 9 of 9 render |
| Scan of the edited files for tool attribution and for the retired country name | clean |
| Backend: venv on Python 3.11.9, `pip install -r requirements-dev.txt` | ok |
| Backend: `pytest -q`, no `.env.local`, no emulator | 3,863 passed, 226 skipped, **2 failed** (the known Windows timing and network-guard tests, D-248, D-279, D-289; Linux CI is green) |
| Backend: `ruff check .`, `black --check .`, `mypy app` | pass (519 files; 244 source files) |
| Backend: the README's `firebase emulators:exec ... pytest tests/integration` | 771 passed, 119 skipped, **3 failed**: the two above and a Coach concurrency test that passed 4 of 4 alone (D-305). The command itself works as written |
| Frontend: `pnpm install --frozen-lockfile` | ok, 28 s |
| Frontend: `pnpm lint`, `node scripts/check-i18n.mjs`, `pnpm build` (no env file) | pass; 1,331 keys in 6 languages |
| Frontend: `pnpm format:check` | **fails on a CRLF clone (545 files), passes on a clone made with `core.autocrlf=false`**. The README tells Windows users how to clone (D-21) |
| Frontend: `pnpm test` with no env file | **18 of 142 files fail to load** ("Missing VITE_FIREBASE_API_KEY"); with the four placeholders CI uses, 142 files and 1,650 tests pass. The README documents the four values (D-297) |
| Frontend: `pnpm test:rules` | 3 files, 189 tests pass |
| Browser suite (Playwright, phone and desktop, inside the emulators, build with `--mode emulator`) | 195 of 196 passed; the one failure passed 3 of 3 alone (D-307) |
| Quick start, step by step: emulators, then the six loaders, flags snippet, rates script, API, web app | every step works as written; the loaders wrote only to the emulator |
| In the running app: phone sign-in with the code from the README's `curl`, onboarding, dashboard with all six pillars, SG to PH comparison for SGD 260 (InstaReM best, family receives 12,663.32 PHP), Radar map with the seeded reports, Scam Check and Coach screens, Coach pre-filled from the new profile | all as described |
| Read-only GCP checks (list above) | 5 Scheduler jobs, Cloud Run 0 to 2 instances, 900 s, Firestore native in `asia-south1`, TTL on three collections, 4 secrets, Hosting site `nomadfinance-prod`; 6 composite indexes (the repo file declares 3, D-301) |

**Not verified, and why:**

- **The PowerShell variants** of the command blocks were not run in PowerShell. The checks ran in Git Bash. The syntax used is standard (`$env:NAME = "value"`, `py -3.11 -m venv`, `Copy-Item`), and the `Invoke-RestMethod` line is the one in the NF-P1-009 runbook.
- **Editing `backend/.env.local`** was blocked by a deny rule in this environment, so the three required values were passed as shell variables instead. They are read the same way (shell variables beat the file); the file edit itself is a text edit.
- **Anything that calls Gemini** (contract analysis, scam verdicts, Coach replies and plans, bill scanning, "Get advice") ran with a placeholder key, so those screens were opened but not exercised. The savings insight needs the optional rate-history backfill, which was not run.
- **PDF output and the Docker image** were not run (WeasyPrint needs Linux libraries; no image was built).
- `pnpm` itself does not run in the agent's shell, so `npx pnpm@10` stood in, and the browser suite was started with the equivalent direct calls instead of `pnpm test:e2e` inside `emulators:exec`. The Playwright configuration and the tests are the repository's.

## Definition of Done (Documentation)

- [x] Written in Markdown
- [x] Consistent headings, lists and code blocks
- [ ] Reviewed by at least one other teammate (the tracker names Aditya)
- [x] Committed to `/docs` or updated at the file's own source (`README.md`, the folder READMEs and `docs/mermaid/`)
- [x] No attribution to a tool, and no chat-style opener

And the tracker's two lines for this task:

- [x] A fresh clone can run locally by following the README only. Done in a fresh clone; the gaps it found are fixed in the README (Java 21, the third required variable, shell-level emulator variables, flags and rates, the four test placeholders, the LF clone) or logged (D-297, D-299).
- [x] The diagrams match the deployed reality, as read on 2026-10-11. The six pillar diagrams do not yet (D-303).

## Noticed, not fixed

D-297 to D-307. The ones that matter most: **D-300** (the loaders write to production if the emulator variables are missing), **D-301** (live Firestore has 3 composite indexes the repo file lacks), **D-297** (frontend tests need an env file), **D-299** (flags and rates have no local loader).

## Commit

Branch: `docs/NF-HR-012-readme-architecture-v2` (the repository was on `main` when the work was done; create the branch before committing, the edits are unstaged).

```text
docs(readme): rewrite README and redraw v2 architecture diagrams
Refs: NF-HR-012
```
