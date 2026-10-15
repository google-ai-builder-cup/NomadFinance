# NF-P2-021 — Cross-Pillar: Contract Flags → Radar Signal

## Summary

When a contract's comparison (NF-P2-004) finds one or more `danger` clauses — the same threshold that already triggers the complaint letter (NF-P2-006) — the flagged employer or agency is now also reported to Exploitation Radar automatically: an anonymized `radar_reports` document, `source: "contract_signal"` (`docs/data-model/collections/radar.md`).

No Gemini call. This task's only dependency is NF-P2-004, not NF-P1-004: the violation category is already a checked fact from step 4's clause comparison, not a fresh model guess, and there is no free text from a worker to spam-check. The radar pillar's own submission pipeline (NF-P3-001 to NF-P3-005) is Week 3 and still entirely unbuilt; this task fills in exactly the one write path the data model doc already names for it, nothing more.

New dependencies: `python-slugify==9.1.2` and its own required dependency `text-unidecode==1.3`, pinned exact. The data model doc requires this specific library for the entity slug, since the slug is the join key later cross-pillar badges (NF-P3-022, NF-P3-023) will match on — a hand-rolled slugifier could silently produce a different slug for the same name and split one entity into two.

## Files

| File | Change |
|---|---|
| `backend/requirements.txt` | `python-slugify==9.1.2`, `text-unidecode==1.3` |
| `backend/app/schemas/radar.py` (was a stub) | `RadarReport`, `RadarValidation`, `RadarEntityType`, `RadarViolationType`, `RadarReportSource` — the `radar_reports` write-side shape only; nothing for `radar_entities`/`radar_alerts` (not this task's job) |
| `backend/app/repositories/radar_repo.py` (was a stub) | `RadarRepository.new_report_id()`, `.create_report()` — write-only, nothing NF-P3-001/003 will need is added speculatively |
| `backend/app/utils/slugs.py` (new) | `slugify()`: the one place in the backend that turns a name into a slug, so every writer produces the same one |
| `backend/app/services/cross_pillar/contract_to_radar.py` (was a stub) | `choose_entity()`, `build_reports()`, `create_radar_signals()`, the `VIOLATION_TYPE` mapping |
| `backend/app/services/contract/pipeline.py` | `PipelineDeps` gains a `radar` field; one call site inside the existing `if comparison.clause_counts.danger:` block, wrapped so a failure here can never break the worker's own report |
| `backend/app/api/v1/contract_analysis.py` | `get_pipeline_deps` wires in `get_radar_repository()` |
| `backend/tests/fixtures/pipeline_fakes.py` | `FakeRadar` |
| `backend/tests/unit/services/test_contract_to_radar.py` (new) | 23 tests |
| `backend/tests/unit/services/test_contract_pipeline.py` | 3 new tests; both existing `PipelineDeps(...)` call sites updated for the new field |
| `backend/tests/integration/api/test_contract_analysis.py` | Same `PipelineDeps(...)` update |
| `backend/tests/integration/repositories/test_radar_repo.py` (new) | 4 tests, against the Firestore emulator |
| `docs/data-model/collections/radar.md` | Two small corrections: `validation` and the "written only after validation" line both now say what a `contract_signal` report actually does |

No API endpoint added: this is an internal step of the existing `analyze` pipeline, not a new route. `docs/api/endpoints.md` is unchanged.

## Decisions

1. **Same gate as the complaint letter: `clause_counts.danger`.** "Flags an employer/agency" in the task description is the same bar Contract Shield already uses to decide a violation is worth writing a formal letter about. Including `caution` clauses would flag far more employers on much weaker grounds, undermining the credibility of the "community flagged" badge the whole point of this signal feeds.
2. **One report per distinct mapped `violation_type`, not per clause, not one per contract.** Five `other`-mapped danger clauses collapse into a single `other` report; a passport clause and a recruitment-fee clause on the same contract become two separate reports, each carrying its own real violation type. Tested directly (`test_distinct_violation_types_become_separate_reports`, `test_several_clauses_of_the_same_mapped_type_collapse_into_one_report`).
3. **The description is built only from each clause's English `explanation`, never its raw `text`.** A contract clause can, in principle, contain the worker's own name (some templates have an "Employee: ___" line); the model's plain-language explanation never does. Tested directly, including a check that the literal marker string never appears in the description.
4. **`validation` is a documented placeholder, not invented Gemini output.** `spam_score: 0.0` (not user-submitted text, no spam risk), `category_confidence: 1.0` (a deterministic lookup, not a model's guess), `model: "contract_shield"` (names the real source). The data model doc's own `validation` row and its opening sentence are corrected to say this is normal for `source: "contract_signal"`, not a gap.
5. **A report's id is generated before the report is built, not patched in after.** `cluster_id` must equal the report's own id when it starts a new cluster (radar.md). Firestore's `collection.document()` with no argument assigns an id purely client-side (checked directly against the SDK source, no network round trip), so `RadarRepository.new_report_id()` is called synchronously, once per report that will actually be written, and only after both the danger-clause check and the named-entity check have already passed — so it is never called when nothing will be written (checked with a fake id function that raises if called unexpectedly).
6. **The Firestore write can never break the worker's own contract report.** The call is wrapped in `pipeline.py`'s own `except Exception:` (the same broad-catch style already used once in that file, for its own top-level failure handler), logged and swallowed. This is the one place in the codebase that deliberately widens the usual "specific exceptions only" rule, because the alternative — a radar-write hiccup costing a worker their finished Contract Health Report — is worse than logging and moving on. Mutation-tested: removing the try/except makes the pipeline's own test suite fail exactly where expected.
7. **`corridor_id` is never set, `host_country` always is.** Contract Shield knows the contract's host country; it never knows a remittance corridor.
8. **No entity aggregation, no embedding, no clustering.** `radar_entities/{slug}` is untouched (NF-P3-003's job, once it exists); `report_embeddings/{id}` is not written (NF-P3-002's job); `cluster_id` equals the report's own id for now. Every contract-signal report is an ordinary `radar_reports` document, so those pipelines pick it up like any other once they are built — nothing here needs to change when they land.
9. **`app/utils/slugs.py` is a two-line wrapper, not a new abstraction for its own sake.** Its only job is to be the one place that calls `python-slugify`, so a later writer (NF-P3-001) reaches for the same function instead of calling the library directly with possibly different options.

## Flow

```
services/contract/pipeline.py, inside `if comparison.clause_counts.danger:`
  write_letter(...)                                          [unchanged, NF-P2-006]
  try:
    create_radar_signals(host, document_kind, comparison.clauses, facts, deps.radar)
      choose_entity(document_kind, facts)              → (type, name) or None (nothing to report)
      group danger clauses by VIOLATION_TYPE[category]  → one group per distinct violation_type
      for each group:
        radar.new_report_id()                           → id, client-side, no I/O
        build a RadarReport (cluster_id = that id, source="contract_signal", validation=fixed)
        radar.create_report(id, report)                  → one Firestore write
  except Exception:
    log and continue — the pipeline's own result is unaffected either way
```

## All commands, in order

From `backend/` with the virtual environment active.

### 1. The checks CI runs (`.github/workflows/backend-ci.yml`, `security-scan.yml`)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it, without Google credentials, then the dependency audit:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
pip install pip-audit==2.10.1
pip-audit -r requirements.txt --no-deps --disable-pip
```

```bash
docker build --platform linux/amd64 -t nomadfinance-backend:ci .
```

### 2. The Firestore repository test (needs the emulator)

From `frontend/`:

```bash
firebase emulators:start --only firestore --project demo-nomadfinance
```

From `backend/`, in another shell:

```bash
FIREBASE_PROJECT_ID=demo-nomadfinance FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 \
  python -m pytest tests/integration/repositories -q
```

### 3. Try it by hand

Analyze a contract whose clauses include at least one `danger` risk and a named employer (for example the existing `sample_contract_sg.pdf` fixture through the whole pipeline), then read the newly created `radar_reports/{id}` document in the emulator UI or via the same Firestore REST calls used in the NF-P2-014 runbook. Expect `source: "contract_signal"`, `entity_name` matching the contract's employer, no `reporter_hash`.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass |
| `pytest -q`, with and without Google credentials | 625 passed, 51 skipped (opt-in live and emulator tests) |
| New tests | 23 unit (`test_contract_to_radar.py`), 3 pipeline-level, 4 Firestore-emulator |
| `pip-audit -r requirements.txt --no-deps` | No known vulnerabilities (covers the two new pins) |
| Firestore emulator repository test | 4 passed against a real running emulator; the whole repository suite (19 tests) still passes alongside it |
| Mutation checks | Three on `contract_to_radar.py` (raw-text leak into the description, no dedup by violation type, skipping the no-entity check) and one on `pipeline.py`'s own try/except: each deliberately broken, each caught by the tests, both files restored byte-for-byte afterward |
| `docker build --platform linux/amd64 -t nomadfinance-backend:ci .` | **Not run**: the Docker daemon was not running on this machine this time. `Dockerfile` is unchanged; `requirements.txt` gained two small, already-`pip-audit`-clean pins; NF-P2-014's runbook has the last successful build of this same `Dockerfile` |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| No `radar_reports` document after analyzing a contract with danger clauses | Check the contract actually named an employer or agency (`extracted.employer_name` / `agency_name`); with neither, there is nothing to anonymize and no report is written, on purpose |
| `pipeline_radar_signal_failed` in the logs | The Firestore write failed; the worker's own report still completed normally (decision 6). Check Firestore access/quota; nothing to fix in the contract analysis itself |
| Two contracts about the same business produce two different `entity_slug` values | Almost certainly two different spellings of the name reaching Contract Shield's detection step; `radar_entities.aliases` (NF-P3-003, not built yet) is the documented place to merge them |
| Adding a new clause category later | Add it to `VIOLATION_TYPE` in `contract_to_radar.py`; the mypy `dict[ClauseCategory, RadarViolationType]` type will fail to compile until every category has an entry, so a missed one cannot ship silently |

## Definition of Done

Cross-pillar / backend step:

- [x] No new API endpoint; this is an internal pipeline step, documented as such
- [x] Specific errors kept specific everywhere except the one deliberate, documented boundary (decision 6)
- [x] Anonymized: no `reporter_hash`, no worker fact, never a clause's raw text
- [x] Tested with diverse inputs: multiple violation types on one contract, a contract naming only an agency, a contract naming no one, a contract with only `caution` clauses, a long description that needs truncating, a name with punctuation
- [x] `docs/data-model/collections/radar.md` updated
- [ ] Manual check against a real contract through the full pipeline (step 3 above): yours

Data ingestion into Firestore:

- [x] Validates before writing (Pydantic `RadarReport`, `RadarValidation`)
- [x] Safe to run again (each analyze that still finds danger clauses writes new reports; nothing is overwritten or duplicated by id, since each report gets its own fresh id)
- [x] Documented (this file)

## Commit and PR

Branch: `feature/contract-radar-signal` (already checked out; up to date with `main`).

```
feat(contracts): report flagged employers and agencies to exploitation radar
Refs: NF-P2-021
```

PR title: `feat(contracts): send contract violations to exploitation radar (NF-P2-021)`

## For teammates

- **NF-P3-001 (report submission, Pranjal):** reuse `app/utils/slugs.py`'s `slugify()` for a worker's own report, not a fresh call to `python-slugify` — same join key, same behavior.
- **NF-P3-002/003 (embeddings, entity aggregation):** contract-signal reports are ordinary `radar_reports` documents with `source: "contract_signal"`; no special-casing should be needed when reading the collection, only when deciding whether to ask a worker to confirm a report (contract signals have no reporter to ask).
- **NF-P3-022/023 (cross-pillar badges):** the slug this task writes is exactly the one those badges will look up.

## Not covered here

Everything else in Exploitation Radar: submission (NF-P3-001), embeddings and clustering (NF-P3-002), entity risk aggregation (NF-P3-003), the alert cron (NF-P3-004), demo seed data (NF-P3-005), any UI, App Check (NF-P3-025).
