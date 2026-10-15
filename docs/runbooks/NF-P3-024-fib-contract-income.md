# NF-P3-024 — Cross-Pillar: Contract Employment → FIB Income Source

Originally assigned to Devam; picked up on your direction.

## Summary

When Contract Shield's comparison (NF-P2-004) confirms a contract is a genuine employment contract and step 2 (`detector.py`) read a usable stated salary, that salary is now logged as one verified income entry in the Financial Identity Builder: `users/{uid}/income/{entry_id}`, `verified: true`, `source: "contract"`, `contract_ref` pointing back at the contract. This is the original design's flow #5 ("Verified employment adds" to P4) — the direct sibling of NF-P2-021's flow #2 (P2 → P3, `contract_to_radar.py`), and this task mirrors that one's shape closely.

No Gemini call: `salary_amount`/`salary_currency` are already-checked facts from step 2 (`detector.py::_clean` only ever sets `salary_currency` when it's a valid 3-letter code *and* `salary_amount` is finite and positive), never a fresh model guess here.

## Files

| File | Change |
|---|---|
| `backend/app/services/cross_pillar/contract_to_fib.py` (new) | `build_income_entry()`, `log_contract_income()` |
| `backend/app/services/contract/pipeline.py` | `PipelineDeps` gains a `fib` field; one call site right after `compare_contract` succeeds, wrapped so a failure here can never break the worker's own report |
| `backend/app/api/v1/contract_analysis.py` | `get_pipeline_deps` wires in `get_fib_repository()` |
| `backend/tests/fixtures/pipeline_fakes.py` | `FakeFib` |
| `backend/tests/unit/services/test_contract_to_fib.py` (new) | 9 tests |
| `backend/tests/unit/services/test_contract_pipeline.py` | 5 new tests; the existing `PipelineDeps(...)` fixture updated for the new field |
| `backend/tests/integration/api/test_contract_analysis.py` | Same `PipelineDeps(...)` update |

**`docs/api/endpoints.md` is unchanged, on purpose** — checked first: this project's own convention (set by NF-P2-021, the radar-signal sibling) is not to annotate the *triggering* endpoint (`/contracts/{id}/analyze`) with a cross-pillar side effect at all; it's already documented from the *data* side instead. Both `docs/data-model/collections/contracts.md` (`extracted`'s row) and `docs/data-model/collections/fib.md` (income's `verified`/`contract_ref` rows) already named NF-P3-024 correctly before this task existed, and `docs/api/endpoints.md`'s own `POST /fib/income` section already says `verified` is "always false... true is set only by the contract cross-pillar flow, NF-P3-024." Nothing to update — it was written forward-looking.

## Decisions

1. **Gated on `document_kind == "employment_contract"`**, not just "comparison succeeded." `compare_contract` only rules out `loan_agreement` as incomparable; a `recruitment_agreement` (an agency's fee schedule, not the worker's own wage) and `other` both still reach this code otherwise. Tested directly (`test_a_recruitment_agreement_with_a_salary_figure_logs_no_income`).
2. **The entry id is derived from the contract id** (`f"contract_{contract_id}"`), not `fib.new_id()`. Every other FIB writer logs a one-off event and wants a fresh id every time; this one is tied 1:1 to a contract, and re-analyzing it (a different host country chosen, the content changed) must *overwrite* the same entry, not log a second one that would double-count toward `income_stability`'s monthly totals. Tested directly (`test_re_analysing_the_same_contract_updates_not_duplicates_the_income_entry`).
3. **`amount` is the stated figure exactly as the contract reads it, whatever `salary_period` is — never normalized to a monthly equivalent.** Checked `report_html.py` first: the PDF export prints `salary_amount` verbatim as "the salary," with no period shown at all. Converting a stated "$50/day" to a monthly figure here would make the PDF state a number the contract itself does not say — worse than the alternative. The alternative is a known, accepted imprecision in `income_stability`'s monthly bucketing; that module already disclaims none of its formulas are calibrated against real lending outcomes.
4. **`category_source: "user"`, not `"model"`.** "Salary" here is a deterministic fact from a checked extraction step, not an AI guess — checked `categorizer.py`'s `_is_pending` first to confirm `category_source == "user"` is exactly what keeps an entry out of NF-P3-012's batch categorizer forever, which is the correct behavior: this category is never wrong in a way categorization would fix.
5. **The Firestore write can never break the worker's own contract report.** Same `except Exception:` swallow-and-log style `pipeline.py` already uses once for the radar signal — the one place this codebase deliberately widens the "specific exceptions only" rule, for the same reason: a FIB-write hiccup costing a worker their finished Contract Health Report is worse than logging and moving on.
6. **No backfill.** Contracts analyzed before this change has no retroactive income entry; the task only wires the flow going forward, matching the task's own wording ("when Contract Shield analyzes").

## Flow

```
services/contract/pipeline.py, right after `compare_contract` succeeds (before the
`if comparison.clause_counts.danger:` block — independent of contract risk)
  try:
    log_contract_income(uid, contract_id, detected.document_kind, facts, deps.fib, now)
      build_income_entry(facts, document_kind)
        document_kind != "employment_contract"        → None, nothing to log
        no salary_amount or no salary_currency          → None, nothing to log
        else                                             → the entry dict (employer_name
                                                             included only if present)
      fib.save_entry(uid, "income", f"contract_{contract_id}", entry)  → one Firestore write,
                                                             overwriting any earlier entry for
                                                             this same contract
  except Exception:
    log and continue — the pipeline's own result is unaffected either way
```

## All commands, in order

From `backend/` with the virtual environment active.

```bash
ruff check .
black --check .
mypy --strict app/services/
mypy app
python -m pytest -q
```

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (44 source files) |
| `mypy app` | Clean (132 source files) |
| `pytest -q` (full suite) | 931 passed, 60 skipped (opt-in live-Gemini tests) |
| New: `test_contract_to_fib.py` (9) | `build_income_entry`'s gates (document kind, missing amount, missing currency, missing employer), the deterministic id, overwrite-not-duplicate, the nothing-to-log no-op |
| New, in `test_contract_pipeline.py` (5) | End-to-end through `analyze_contract`: logs on a clean employment contract; no salary detected logs nothing; a recruitment agreement with salary facts logs nothing; re-analysis overwrites; a FIB write failure never breaks the worker's own report |

**Not run:** `mypy app tests` (not a CLAUDE.md-required check, only `mypy --strict app/services/` is) — ran it anyway out of curiosity; 19 pre-existing errors surfaced, all in test files this task never touched (`test_radar_evidence.py`, `test_fib_exporter.py`, `test_radar_aggregation.py`, and others), none in `test_contract_to_fib.py`, `test_contract_pipeline.py`, `test_contract_analysis.py` or `pipeline_fakes.py`. Pre-existing drift from other tasks, not this one.

**Not verified:** a manual Swagger test through the full `/contracts/{id}/analyze` → check `users/{uid}/income/contract_{id}` loop (needs a running backend + Firestore emulator + a real or faked Gemini detect/compare response) — the automated pipeline-level tests already exercise this exact path end-to-end with fakes, so this is schedule-of-confidence duplication, not a real gap; flagging it as the Definition of Done item left for you.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No income entry after analyzing an employment contract | Check `extracted.salary_amount`/`salary_currency` actually got set (`detector.py::_clean` drops an unreadable amount or a currency that isn't a valid 3-letter code) — with neither, there is nothing to log, on purpose |
| `pipeline_fib_income_failed` in the logs | The Firestore write failed; the worker's own contract report still completed normally (decision 5). Check Firestore access/quota; nothing to fix in the contract analysis itself |
| Re-analyzing a contract seems to have "lost" the old salary figure | Expected — the entry is overwritten, not appended (decision 2); the financial profile's `verified_employment` always reflects the contract's *current* analysis, not its history |
| A recruitment agreement's contract shows no verified income | Expected — gated to `employment_contract` only (decision 1) |

## Definition of Done

Cross-pillar / backend step:

- [x] No new API endpoint; this is an internal pipeline step
- [x] Specific errors kept specific everywhere except the one deliberate, documented boundary (decision 5)
- [x] Tested with diverse inputs: a clean employment contract, no salary detected, a recruitment agreement with salary facts anyway, re-analysis of the same contract, a Firestore failure
- [x] Data model docs already correct (confirmed, not re-written)
- [ ] Manual check against a real contract through the full pipeline: yours

Data ingestion into Firestore:

- [x] Validates before writing (gated in `build_income_entry`, nothing malformed reaches `save_entry`)
- [x] Safe to run again (deterministic id overwrites, decision 2)
- [x] Documented (this file)

## Commit and PR

Branch: `feature/fib-contract-income` (already checked out, matches tasks.md).

```
feat(fib): log verified employment income from analyzed contracts
Refs: NF-P3-024
```

PR title: `feat: contract employment flows into Financial Identity income (NF-P3-024)`

## Not covered here

Any frontend change — `verified_employment` display already exists end to end (NF-P3-014's PDF, NF-P3-017's dashboard reads `FinancialProfile.verified_employment` by type, NF-P3-018's preview modal), built before this task, against the shape this task now actually starts populating. No UI work was needed.
