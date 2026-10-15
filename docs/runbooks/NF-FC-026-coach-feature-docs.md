# NF-FC-026 — Coach feature docs and prompt notes

> The feature pages this task wrote have since been removed from the repository; they stay in git history.

## Summary

The Financial Coach now has the same two pages the Scam Analyzer has, and a row in the README table.

| Page | What it holds |
|---|---|
| [`docs/gemini-prompts.md`](../gemini-prompts.md), section "Financial Coach" (filled in) | The seven prompts: tier, model, temperature, response model, variables, what each must never do, what the code does with the answer, version history; how prompt versions meet stored sessions and plans; and the steps to run after changing a Coach prompt, the question bank, the rubric or the model |
| [`README.md`](../../README.md) | A **Financial Coach** row in the "Pillars 5 and 6: feature docs" table: the feature doc, the prompt notes and the API contract |
| [`backend/app/prompts/README.md`](../../backend/app/prompts/README.md) | The three Coach prompts the table did not list: `coach/reply.v2`, `coach/review.v1`, `coach/summarise.v1` (agreed in the plan) |

Not in this task: any code or behaviour change, the Scam Analyzer docs (NF-SA-021).

## What it was written from

Every statement was taken from the code or a runbook, not from the design intent. The sources were the API contract (`docs/api/v2-coach.md`), the design addendum (section 4), the runbooks NF-FC-007 to NF-FC-025, the seven prompt files, `session_machine.py`, `review_reader.py`, `guard.py`, `config.py` (tiers, thinking budgets, limits), `plan_generator.py` and `plan_translator.py` (temperature and timeouts), the data model page, the check-in job's scheduler file, and the question bank. Where the design and the build differ the page follows the build (for example the reply runs on the classification tier by default, not Gemini 2.5 Flash).

## Files

| File | Change |
|---|---|
| `docs/gemini-prompts.md` | The Coach section added; the two feature rows in its table link to their sections |
| `README.md` | One row |
| `backend/app/prompts/README.md` | Three rows |
| `docs/runbooks/NF-FC-026-coach-feature-docs.md` | New (this page) |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows, `tsconfig*`) and no code was touched.

## Decisions that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Link, not copy, the rubric and the plan rules | The two pages are long and carry the numbers; copying them would give two places to keep true. The feature doc keeps the shape (factors, weights, bands, caps) a reader needs to follow the flow |
| 2 | The page mirrors the Scam Analyzer page | Same order and tone, so a reader who knows one finds the other |
| 3 | Prompt behaviour in `gemini-prompts.md`, not in the feature doc | As that page says: the files cannot explain behaviour, and the feature doc is about the flow |
| 4 | Results are quoted with their date and run | The evaluation table says which numbers are from live runs and which have not been made (the first regression run, the guard's live check, the plan's re-run) |
| 5 | The pipeline diagram is not redrawn | `docs/mermaid/financial-coach-pipeline.mmd` is the design's; the feature doc says where it differs (D-263) |
| 6 | A prompt that has not been tried with the live model says so | `coach/reply.v2` (D-253) |
| 7 | The third and fourth prompts README rows | The prompts README is the full list the notes page points to; it had 4 of the 7 Coach prompts |

## Checks run (2026-10-10)

| Check | Result |
|---|---|
| The three Mermaid diagrams of the feature doc (a turn, the state machine, the plan) | **All three parse** (mermaid 10.9.1 in a browser; the page that ran it was a scratch file, not kept) |
| Relative links in the four pages | **0 broken** |
| Repository paths named in backticks in the feature doc | **0 missing** |
| Words the project does not allow in docs (the names of the tools and of authorship) | none found |
| `pytest tests/unit/test_prompt_loader.py` (it holds the list of prompts) | 87 passed |
| `pytest -k coach` | 1,563 passed, 47 skipped (the live and emulator ones) |
| Coach frontend tests (components, pages, helpers, hooks, services, mocks) | 49 files, 636 passed |
| Numbers in the pages against the code | Thresholds (guard 0.7 and 0.5, review 0.85 and 0.6), temperatures, tiers and thinking budgets, the history window (24 turns, 6,000 tokens), the plan's 90 s and the translation's 60 s, the stage moves and the status moves were read from the code |

**Not verified:** a second person's read of the pages (D-263); the Coach's behaviour on a running server with real Gemini (D-258); the guard's live check (D-227); the diagrams rendered on GitHub itself (they parse; GitHub's renderer is a different version); the pages' table of contents.

## Definition of Done (Documentation)

- [x] Written in Markdown
- [x] Uses consistent formatting (headings, lists, code blocks), the same layout as the Scam Analyzer page
- [ ] **Reviewed by at least one other teammate.** Aditya wrote it; the tracker names Aditya as the reviewer, so Devam or Pranjal should read it (D-263)
- [x] Committed to `/docs`, and the README row and the prompts README updated at their source
- [x] No authorship lines and no boilerplate openers
- [x] Tracker finish line, "linked from README feature table": done. "Docs merged": after the pull request

## Noticed, not fixed

Left for later (D-263): the design pipeline diagram still names Gemini 2.5 Flash for the reply; `docs/api/v2-coach.md` "Implementation status" ends with "The rest is specified only", which is no longer true; the evaluation table will go stale as the open live runs happen.

## Commit

Branch: `docs/NF-FC-026-coach-feature-docs` (already created).

Commit message:

```
docs(coach): add Financial Coach feature doc and prompt notes
Refs: NF-FC-026
```
