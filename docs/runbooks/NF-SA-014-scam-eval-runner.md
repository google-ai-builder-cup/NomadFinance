# NF-SA-014 — Scam eval runner and quality bar

## Summary

`python -m evals.run_scam_eval` (from `data-scripts/`) sends the 120 golden messages through the Scam Analyzer's classifier, scores the answers against the labels and writes a report to `docs/evals/scam-eval-<date>.md`. The bar is the one on `docs/evals/scam-golden-set.md`: **F1 of scam against benign of at least 0.85 overall and at least 0.75 in every one of the six languages**. A manual GitHub workflow (**Scam eval**, Actions tab) runs the same command and fails below the bar.

- **Exit code 0**: the bar is met. **1**: it is not (the report is still written: the first run is the baseline whether or not it passes, and NF-SA-023 tunes from it). **2**: not scored, because a message got no answer or the setup is incomplete.
- The report has the verdict on top, then the run (model, prompt version, taxonomy hash, golden-set fingerprint), the bar group by group, scam against benign per language, precision / recall / F1 per scam type, the confusion matrix, and every wrong answer (false alarms first) with the label's own one-line reason, so the false alarms can be read by hand (D-129).
- **The bar is set on scam against benign only.** A scam type has 6 to 12 messages in the whole set, so one message moves its figures by 8 points or more; the per-type numbers are reported (as "k of n" and in the matrix) and not gated (D-129).

Not in this task: the 15-message injection suite and the Playwright E2E (NF-SA-020), the prompt tuning that follows the baseline (NF-SA-023), the explainer, the neighbour search, the cache and the hourly limit (none of them can change the verdict).

**The baseline report is not committed yet.** It needs live Gemini calls with a key, and was not run for this change: see D-150. Everything else was checked with a fake classifier and, for the wiring, with the real backend steps and only the network call replaced.

## What is scored

```
golden row ─► ScamAnalyzeTextRequest ─► redact_text ─► extract_signals ─► classify_message ─► verdict
              (trims the text)          (masks PII)     (links, phones,    (Gemini, the            is_scam, scam_type
                                                         amounts)           classification tier)
```

Each step is the backend's own function, the same ones `analyze_text` calls, so a change to the prompt, the taxonomy wording, the masking or the indicator rules moves the score. The taxonomy comes from `data-scripts/data/source/scam-taxonomy/*.json` in the order the backend reads it from Firestore (`order`), so no Firestore access is needed. The runner reads the answer's `is_scam` and `scam_type`; a scam with no type counts as `other_scam`, as the classifier files it.

## Run it

You need the backend's packages next to the data scripts' ones, and a key.

PowerShell, from `data-scripts/`:

```powershell
# Either use the backend's virtual environment, which already has everything:
..\backend\.venv\Scripts\python.exe -m evals.run_scam_eval --limit 6
# or add the backend's packages to the data scripts' one (the pins match, no conflict):
pip install -r ..\backend\requirements.txt
```

bash, from `data-scripts/`:

```bash
../backend/.venv/bin/python -m evals.run_scam_eval --limit 6   # Git Bash on Windows: .venv/Scripts/python.exe
pip install -r ../backend/requirements.txt                       # or install into the data scripts' environment
```

The key is read the way the backend reads it: `GEMINI_API_KEY` in this shell (`$env:GEMINI_API_KEY = "..."` in PowerShell, `export GEMINI_API_KEY=...` in bash; never in a file that is committed) or in `backend/.env.local`. A missing or empty key stops the run before any call (exit 2). The backend's settings also insist on `APP_ENV` and the Radar reporter key, which the eval never uses; when they are not set the runner fills them with `local` and a placeholder.

1. **Try the setup first**: `python -m evals.run_scam_eval --limit 6`. It runs 6 messages spread over the six languages and prints each answer. Nothing is scored and no report is written.
2. **Run it all**: `python -m evals.run_scam_eval`. 120 calls, one line per message as it finishes, then the F1 against each bar and the report path. On a free-tier key add `--rpm 10`: without it the per-minute quota runs out part way and messages end without an answer (exit 2). At 10 a minute the 120 calls take 12 minutes; without a limit it is faster.
3. **Read the report**, start with the false alarms (benign messages called a scam) and the missed scams, and commit it. The first report is the baseline.

| Option | Meaning |
|---|---|
| `--report PATH` | Write the report here (default `docs/evals/scam-eval-<today>.md`) |
| `--limit N` | Run N messages spread over the languages; no report, no bar |
| `--concurrency N` | Calls in flight at once (default 4) |
| `--rpm N` | Start at most N calls a minute (default no limit) |

If a message gets no answer (Gemini failed after the client's three tries) the run lists it and exits 2 **without writing a report**: a partial score would be read as a baseline. Run again, with a lower `--concurrency` or an `--rpm` if the quota ran out. Any other error (a bug in the eval or the backend) stops the run with its traceback.

## The manual workflow

`.github/workflows/scam-eval.yml` (name **Scam eval**, Actions tab, "Run workflow"): installs `backend/requirements.txt` and `data-scripts/requirements.txt`, runs `python -m evals.run_scam_eval --report /tmp/scam-eval.md` and attaches the report (also when the run failed). It needs a repository secret `GEMINI_API_KEY` (D-151) and, like any dispatch-only workflow, is listed in the Actions tab once it is on `main`. It has no `--rpm`: on a free-tier key it can exit 2 for lack of quota (D-151).

## Files

| File | Change |
|---|---|
| `data-scripts/evals/run_scam_eval.py` (new), `evals/__init__.py` (new, empty) | The command: options, the run, the exit code, the report file |
| `data-scripts/src/scam_eval/metrics.py` (new) | Counts, precision / recall / F1 (from the counts, so 34 of 40 is exactly 0.85), the confusion matrix, per class, per language, the bar (`gate`), the golden-set fingerprint |
| `data-scripts/src/scam_eval/runner.py` (new) | The loop: concurrency, `--rpm` pacing, a failed message recorded and the rest still run |
| `data-scripts/src/scam_eval/backend.py` (new) | The wiring to the backend's classifier and settings; a `SetupError` for what is missing |
| `data-scripts/src/scam_eval/report.py` (new) | The markdown report |
| `data-scripts/src/config.py` | `EVAL_REPORT_DIR` (`docs/evals/`) |
| `data-scripts/tests/test_scam_eval_{metrics,runner,report,cli,backend}.py` (new) | 55 tests |
| `.github/workflows/scam-eval.yml` (new, **shared path, approved before it was written**) | The manual job |
| `data-scripts/README.md`, `docs/evals/scam-golden-set.md` | A README section, how to score the set, D-150 to D-152 and the status of D-129 |

No change to `requirements*.txt`, `pyproject.toml`, `data-ci.yml` or any other shared file, and no change to the backend.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Only `classify_message` is run, not `analyze_text` | `analyze_text` also needs Firestore, the explainer (the reasoning tier, which is short of quota), the neighbour search, the cache and the hourly limit, none of which can change `is_scam` or the type |
| 2 | The taxonomy is read from the local files, not Firestore | The files are what the loader writes; the eval then runs without credentials and scores the wording in the working tree |
| 3 | The report is written whether or not the bar is met | The baseline is probably below it (that is what NF-SA-023 is for), and the report is how the weak classes and languages are found |
| 4 | A message with no answer means no report and exit 2 | One missing message changes a language's F1; a partial run must not be committed as the baseline |
| 5 | Only a Gemini failure is recorded per message; any other exception stops the run | A bug in the eval or the backend must be loud, not turned into a missing answer |
| 6 | The per-type figures are not gated | D-129: one message is 8 to 17 points of a type's recall |
| 7 | `--rpm` and `--concurrency` instead of a resume cache | Simple, and enough for a run of 120. A failed run is run again from the start; a resume file could hide a change to the classifier code (D-152) |
| 8 | The backend is imported by name when a run starts, untyped | data-scripts does not depend on it (the same reason `scam_patterns_check.py` loads the redactor by path); the data CI needs none of the backend's packages |
| 9 | The report carries a golden-set fingerprint and the taxonomy's content hash | Two reports with different fingerprints measured different benchmarks, which `docs/evals/scam-golden-set.md` asks a pull request to say |
| 10 | The report holds message ids, never a message | The messages are in `data-scripts/evals/`; a wrong answer is found by its id |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` (data-scripts) | clean |
| `pytest` (data-scripts venv) | **463 passed, 1 skipped, 3 failed.** The skip is `test_scam_eval_backend.py` (needs the backend's packages). The 3 failures are in `test_embedding_resilience.py`, which was not touched: this venv has no `google-genai` (see "Noticed, not fixed") |
| The 55 eval tests in the backend's virtual environment (the 7 wiring tests run) | **55 passed**. In the data scripts' environment: 48 passed and the wiring module skipped |
| `mypy src tests` | no error in the new files. 2 errors in `src/embedding.py` and `tests/test_embedding_resilience.py` (the SDK is not installed in this venv); with the SDK installed the new files and `evals/run_scam_eval.py` are clean and `src/embedding.py` has 1 unrelated typing error |
| **Mutation checks** (a copy of the files, one deliberate break at a time; each break failed a test, the files were restored) | The F1 bar lowered to 0: 6 tests failed. The per-language bar removed from the gate: 5. A run below the bar exiting 0: 2. A message with no answer ignored: 1. A Gemini failure crashing instead of failing the message: 1. The message sent to the classifier unmasked: 1. False alarms counted as caught scams: 1 |
| **Rehearsal of the whole command** | `python -m evals.run_scam_eval` with the real backend steps (request model, masking, indicators, `classify_message`, the real prompt and taxonomy) and only the network call replaced by a keyword guesser: 120 messages through, exit code 1, a complete report with every section (the guesser's F1 was 0.46, which is what it is for) |
| `pip install --dry-run -r backend/requirements.txt -r data-scripts/requirements.txt` | resolves with no conflict (what the workflow runs) |
| Not run | **A live Gemini run, so there is no baseline number.** The workflow was not dispatched (it is not on `main` and needs the secret). The yaml parses |

## Noticed, not fixed

- The data scripts' virtual environment on this machine has no `google-genai` although `requirements.txt` lists it (NF-SA-006): `pip install -r requirements-dev.txt` fixes the 3 failing tests and the 2 mypy errors.
- `src/embedding.py:128` has a typing error against the installed SDK (`embed_content(contents=list[str])`), visible once the SDK is installed. Not touched.
- The golden sets have not had a native-speaker read (D-127, D-130, D-132). A wrongly labelled row lowers a language's F1 for a reason that is not the classifier's: read the wrong answers before tuning to them.

## Definition of Done (Test-only / QA task)

- [x] **The test fails when the behaviour is broken**: shown once for each part of the bar and the exit code (the mutation checks above).
- [ ] **Passes in CI**: the data CI runs the new tests (the wiring tests are skipped there on purpose); the workflow has not been dispatched.
- [x] Bugs found are filed with severity: none in the code under test; the venv and typing notes above are P2 and not caused by this task.
- [ ] **Report committed under `docs/evals`** as the baseline: not done, needs the live run (D-150).
- [ ] Tracker acceptance "job fails when scam-vs-benign F1 < 0.85 or any language < 0.75": the logic is tested; the job itself needs the secret and a dispatch (D-151).
