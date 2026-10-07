# NF-SA-021 — Scam Analyzer feature docs and prompt notes

## Summary

The Scam Analyzer (NF-SA-001 to NF-SA-020) now has its own documentation: one page for the feature and one for how its prompts behave and what to run after changing one. Documentation only: no code, prompt, test or workflow changed.

| File | What it holds |
|---|---|
| [`docs/features/scam-analyzer.md`](../features/scam-analyzer.md) (new) | What a worker sees; the analyze flow as built (a sequence diagram); the steps with their tiers, models and time boxes; every limit; what is stored and what never is; the safety properties; the report to Radar; the errors the screen handles; the evaluation results; known limits; how to turn it on; how to run the tests; where each part lives |
| [`docs/gemini-prompts.md`](../gemini-prompts.md) (new) | The rules every prompt follows; for the four scam prompts: purpose, tier and model, temperature, variables, response model, what the model must never do, and what the code does with the answer; how prompt versions drive the cache; the steps to repeat after changing a prompt, the taxonomy or the model. A heading for the Coach is left for NF-FC-026 |
| `README.md`, `docs/README.md` | A "Future Scope features" table with a Scam Analyzer row, and the index lines |

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | The tracker names `docs/features/` and `docs/gemini-prompts.md`, and the repo has an empty `docs/prompts/prompt-library-guide.md` | Followed the tracker. `docs/features/` is also where NF-FC-026 (the Coach) puts its page, and `backend/app/prompts/README.md` is the real prompt-file table, which the new page links to instead of copying |
| 2 | The tracker says "linked from README feature table", and the README had no table | Added a small table under "What It Does" |
| 3 | The flow differs from `docs/future-scope/design.md` 5.2 in three places | The page says so: the explainer starts after the verdict (it needs it); the indicators are found in the raw text before masking; a screenshot always spends a check |
| 4 | "Eval results" needed numbers, and the golden-set baseline had never been run (D-150) | Ran it on 2026-10-07 with the key from Secret Manager (`--rpm 10`, 120 calls) and added the report: `docs/evals/scam-eval-2026-10-07.md` |

## How the pages were checked

Each figure was read from the code or the settings, not from another document: the models (`backend/app/config.py`), the time boxes and thinking budget (`explainer.py`), the 8 s search time box (`retrieval.py`), the 400-character limit and the answer checks (`explainer.py`), the clean-up of the verdict (`classifier.py`), the 90-day and 1-year retention (`check_store.py`, `scam.md`), the 20-an-hour budget and the 60-a-minute limit (`config.py`), the page sizes (`history.py`), the report limits, the prompt variables and response models. Every markdown link and every file path in the two pages was resolved by a script; the only links that did not resolve until the run finished were the eval report and routes written as paths (`/scam-check/history`).

## Noticed, not fixed

- `docs/mermaid/scam-analyzer-pipeline.mmd` still names the original model tiers (1.5 Flash Vision, 2.5 Flash) and shows the explainer and the search as the design had them. The page says so and links it. Updating the diagram is a separate change.
- The `description` of `scam/read_screenshot.v1.yaml` says it feeds `scam/classify.v1`; the current one is `v2`. A comment only. It should be corrected the next time that prompt file is edited, because a prompt file changes only as a new version.
- `README.md` still lists "2.5 Flash + 1.5 Flash + Flash-Lite + text-embedding-004" under Google Cloud Services; the models in use are in `backend/app/config.py` and the embedding model is `gemini-embedding-001`. Outside this task.
- D-135 (load `scam_patterns` into production) is still open: the load stopped on the free-tier embedding quota. The feature page says what is missing without it.

## Results

| Check | Result |
|---|---|
| **Golden-set baseline** (`python -m evals.run_scam_eval --rpm 10`, live Gemini, 120 calls, about 25 minutes because the model answered 503 at times) | **120 of 120 called correctly.** F1 of scam against benign is 1.000 overall and in each of the six languages (bar 0.85 and 0.75); 84 scams caught, 36 benign passed, no false alarm, no missed scam, and every scam type right. Report: `docs/evals/scam-eval-2026-10-07.md` |
| Reading the number | A baseline, not a proof: 6 to 12 messages per type, written by the team, native-speaker reads still open (D-127, D-130, D-132), and the runner scores only the classifier (D-152). The feature page says so |
| The other results the page quotes | The live injection run (15 of 15, NF-SA-020) and the browser tests (30 runs) were not repeated; the page links to their reports |
| Links and paths in both pages | Resolved by a script; the run is the only place the figures come from |
| D-150 | Marked done in `docs/deferred-items.md` |

**Not verified:** how the two pages render on GitHub (the Mermaid diagram and the tables); that the figures still hold after the next prompt change.

## Definition of Done (Docs)

- [x] Feature page: flow, models, limits, evaluation results
- [x] Prompt page: the four scam prompts and the change checklist
- [x] Linked from the README and `docs/README.md`
- [x] Every number and path checked against the code
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `docs/NF-SA-021-scam-feature-docs` (the tracker's name; the branch checked out is the one to use).

```bash
git commit -m "docs(scam): add feature page, prompt notes and eval baseline" -m "Refs: NF-SA-021"
```

PR title: `docs(scam): Scam Analyzer feature docs, prompt notes and golden-set baseline (NF-SA-021)`
