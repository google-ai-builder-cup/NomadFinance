## Task
Refs: NF-XXX-XXX

Owner: @ &nbsp;·&nbsp; Reviewer (the tracker names one per task): @

## What Changed
-

## Why
-

## Testing Steps
1.
2.

## Screenshots (UI changes)


## Rollout and rollback
- [ ] Behind a feature flag? Flag and state: `none` / `coach` / `scam` (off by default)
- [ ] Rollback: how to undo it (flag off first, or revert this pull request):

## Checks
The first four are enforced by CI and by branch protection; tick the rest yourself.
- [ ] Backend: ruff, black, mypy and pytest pass (Backend checks)
- [ ] Backend: every changed `backend/app/<package>` is at 70% coverage or more and `app/` at 93% (Backend checks, Coverage gate)
- [ ] Frontend: lint, prettier, tsc, build and vitest pass, coverage floors held (Frontend checks)
- [ ] Commit messages follow `<type>(<scope>): <summary>` with `Refs: NF-XXX-XXX` as the only trailer (Commit policy)
- [ ] Tests added or updated for what changed
- [ ] Docs updated where behaviour changed; task runbook at `docs/runbooks/<TASK-ID>-<slug>.md`
- [ ] A shared file changed (`package.json`, lock file, `pyproject.toml`, requirements, Dockerfile, `firebase.json`, rules, `tsconfig*.json`, `.gitignore`, `.github/workflows/*`)? The diff was shown and approved first
- [ ] No secrets committed, no AI attribution in code, docs or commits
- [ ] User-facing text goes through i18n keys (all six languages)

## Definition of Done for this kind of task
Tick the list that matches and delete the others.

<details><summary>Backend endpoint</summary>

- [ ] Pydantic request and response models; Firebase token check (public endpoints marked)
- [ ] Structured logging with request id, hashed user id, timing
- [ ] Specific status codes; v2 routes answer in the error envelope (`docs/api/v2-conventions.md`)
- [ ] Rate limit applied if user-facing
- [ ] Checked in Swagger (`/docs`, local only); `docs/api/endpoints.md` or the v2 doc updated
</details>

<details><summary>Frontend feature</summary>

- [ ] Tailwind and shadcn/ui; mobile responsive (checked at 375 px); slow-network checked
- [ ] Loading, error and empty states
- [ ] Keyboard navigable, semantic HTML, labels for screen readers
- [ ] Screenshots above
</details>

<details><summary>Gemini pipeline step or LLM feature</summary>

- [ ] Tier chosen through `ModelTier`, never a model id; structured output through a Pydantic schema
- [ ] Retries, timeout, token usage logged with the feature tag
- [ ] Prompt in `backend/app/prompts/<pillar>/<step>.v<N>.yaml`, version bumped if changed
- [ ] User, OCR or contract text passed as delimited data, never inside instructions
- [ ] Every number or legal claim shown to a user is derivable from slots, Firestore data or live FX
- [ ] Eval re-run and report in `docs/evals` (scam golden set, coach personas, injection suite) where the task says so
</details>

<details><summary>Streaming (SSE) endpoint</summary>

- [ ] Events `token`, `slot_update`, `done`, `error` as in `docs/api/v2-conventions.md`; heartbeat every 15 s
- [ ] First token under 2 s p95 on staging; a client disconnect cancels the Gemini call
- [ ] The frontend retries a dropped stream and never shows a half message as final
</details>

<details><summary>Firestore schema change</summary>

- [ ] `docs/data-model/` updated (fields, sample, TTL, owner); version fields bumped if cached data depends on it
- [ ] Security rules and the emulator rule tests updated; new queries have their index in `firestore.indexes.json`
- [ ] Migration script, or "not needed" stated
</details>

<details><summary>Feature-flagged module (Coach, Scam Analyzer)</summary>

- [ ] Route and nav entry hidden when the flag is off; the flag-off API answers 404 in the error envelope
- [ ] Production bundle and v1.0 behaviour unchanged with the flag off; the module is its own lazy chunk
- [ ] Rollback path stated above (flag off first)
</details>

<details><summary>Data script or curated dataset</summary>

- [ ] Idempotent, validates before writing, logs counts, documented in `data-scripts/README.md`
- [ ] Every figure carries source URL and retrieval date, curator initials recorded
- [ ] A second teammate spot-checked a sample; synthetic or fully anonymised data only
</details>

<details><summary>Bug fix</summary>

- [ ] Root cause identified, not only the symptom
- [ ] Committed as `fix(...)`; a regression test added if the fix is not trivial
</details>

<details><summary>Documentation only</summary>

- [ ] Consistent headings, lists and code blocks; no chat-style openers; reviewed by a teammate
</details>

<details><summary>Test or QA task</summary>

- [ ] The test fails when the behaviour is broken (shown once) and passes in CI
- [ ] Bugs found are filed with severity (P0, P1, P2) and repro steps
</details>
