# NF-P2-008 — Contract Shield: E2E Testing

## Summary

Team task: test the full pipeline (NF-P2-001 to NF-P2-007) with 5 real sample contracts (SG, AU, KR, MY, JP), fix edge cases, profile latency.

**Real Gemini quota was exhausted before this task could run its first live call** (D-58, confirmed again — see "Live testing" below). Rather than burn further shared quota on retries with no signal, this task instead built a second E2E path that exercises the **real** pipeline code, the **real** Firestore-backed repositories and the **real** curated labor-law and complaint-template data for all 5 countries, with only the raw Gemini answers scripted — catching real per-country wiring bugs at zero quota cost. It found and fixed one (D-60). The live-Gemini path is fully set up and ready to run the moment quota is available (tomorrow ~07:00 UTC, or sooner with a different key).

## What this task added

| File | Purpose |
|---|---|
| `backend/tests/fixtures/contracts/sample_contract_{au,kr,jp}.pdf` | 3 new realistic sample contracts (hand-built minimal PDFs, same technique as the existing `sample_contract_sg.pdf`), each mixing compliant and violating clauses drawn from that country's real curated labor law |
| `backend/tests/fixtures/contracts/sample_contract_{au,kr,jp}.blocks.json` | The same contracts' blocks, for the scripted extraction answer |
| `backend/tests/fixtures/contract_e2e_scenarios.py` | `Scenario` per country (SG, AU, KR, MY, JP) and `ScriptedGemini`, a `GeminiClient` stand-in keyed by `response_model` so the real `extractor`/`detector`/`comparator`/`translator`/`complaint` code runs unmodified |
| `backend/tests/integration/api/test_contract_e2e_mocked.py` | Runs `/contracts` → `/contracts/{id}/analyze` for all 5 countries against the real emulator-backed repositories and real curated data; also a cache-reuse check and a loan-agreement edge case. **No Gemini quota used.** |
| `backend/tests/integration/api/test_contract_e2e_countries.py` | The real-Gemini counterpart for AU, KR, MY, JP (SG is already covered in depth by `test_contract_analysis_live.py`), with per-step timing printed for latency profiling. **Opt-in, not yet run** (see below) |
| `backend/app/schemas/contract_pipeline.py`, `docs/api/endpoints.md`, `docs/data-model/collections/contracts.md` | Fixed: `report_languages` is alphabetically sorted, not source-language-first (D-60, found by this task) |

No shared files, no application code changes beyond the D-60 doc fixes above (the sort itself, in `report_store.py`, was already correct — only undocumented).

## Live testing: blocked by D-58, confirmed again

Before touching the 4 new countries, I ran the existing `test_contract_analysis_live.py` (SG) as a baseline check. Extraction (extraction tier) succeeded in 3.8 s; the comparison call (reasoning tier, `gemini-3.5-flash`) failed with `429 RESOURCE_EXHAUSTED` — *"Quota exceeded ... limit: 20, model: gemini-3.5-flash"* — after one 503 retry. This is the same wall NF-P2-006 hit on the same day (its runbook: *"could not run ... quota was already used up today"*). The free-tier daily cap resets at 07:00 UTC; today's reset already happened roughly 4 hours before I ran this, so it had already been re-exhausted by other testing (NF-P2-007 verification, my own NF-P2-005/006 work) before NF-P2-008 got a turn.

Since **compare is required before complaint or translate**, this blocks a full live run for *every* country right now, not just the new ones. I stopped rather than keep retrying (each retry itself counts against the quota) and discussed the tradeoff with the team: proceed now with everything that doesn't need real Gemini, leave the live path ready, and run it once quota is available.

**To finish the live pass** (SG is already covered by NF-P2-007's own test):

```bash
firebase emulators:start --only firestore --project demo-nomadfinance      # frontend/
```

```bash
# data-scripts/
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
    python -m src.loaders.ilo_natlex --only AU KR MY JP
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
    python -m src.loaders.complaint_templates --only AU KR MY JP
```

```bash
# backend/
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance RUN_LIVE_GEMINI=1 \
    python -m pytest tests/integration/api/test_contract_e2e_countries.py -v -s
```

Each of the 4 tests prints `[COUNTRY upload]`, `[COUNTRY analyze]` and a `TOTAL` line — copy those into the latency table below once run.

## Mocked full-pipeline E2E: what it proved, and what it found

`test_contract_e2e_mocked.py` runs the **real** `/contracts` and `/contracts/{id}/analyze` endpoints, with **real** `ContractRepository`/`UserRepository`/`LaborLawRepository`/`ComplaintTemplateRepository` against the Firestore Emulator (loaded with the real curated labor law and complaint templates for all 5 countries), and only `get_gemini_client` overridden with `ScriptedGemini`. That stand-in answers by `response_model` identity — `ExtractedContract`, `DetectedContract`, `ComparisonAnswer`, `ComplaintAnswer`, `TranslationAnswer` — so every line of `extractor.py`, `detector.py`, `comparator.py` (including its law-reference matching against the real curated JSON), `translator.py`'s merge logic, and `complaint.py`'s real template lookup and placeholder check actually runs, for a real contract, against each country's real data.

**What it found:** `ContractAnalysis.report_languages` came back `["bn", "en"]` for the KR scenario (worker language Bengali) instead of the `["en", "bn"]` every earlier test implicitly expected. Every prior test (SG→hi, and NF-P2-007's own suite) happened to pick a worker language that sorts *after* "en" alphabetically, so `report_store.py`'s intentional `sorted(set(...) | {...})` always looked like "source language first" by coincidence. It isn't a functional bug — the sort is deliberate and deterministic — just undocumented in a way that could trip up NF-P2-012 (the language switcher) if it assumed index 0 is the source report. Fixed by documenting the real behavior in three places (`schemas/contract_pipeline.py`, `docs/api/endpoints.md`, `docs/data-model/collections/contracts.md`) rather than changing working, intentional code. Logged as **D-60, closed in this same change**.

**Also covered:** a loan-agreement upload correctly stops at `compare` with `not_employment_contract` and `status: failed`, without ever reaching the law or complaint steps — the one pipeline-level edge case not already covered by NF-P2-007's own extensive unit/integration suite (28 + 14 tests) that seemed worth a dedicated real-endpoint check here.

**Deliberately not re-tested here** (already covered thoroughly by NF-P2-007's own `test_contract_pipeline.py` and `test_contract_analysis.py`, no new value in duplicating): the claim transaction / 409, stale-claim takeover, `poor_legibility`, `country_unknown` and the other fallback orders, `complaint_pending` retry, and the response-cache rule itself.

## Latency profiling

Real numbers, collected across this and earlier tasks (`GEMINI_MODEL_REASONING=gemini-3.5-flash`, extraction/classification tiers on `-flash-lite`):

| Step | Tier | Measured | Source |
|---|---|---|---|
| 1. Extract | extraction | ~2.6 s/page; 2-page PDF 3.4 s (also seen: 76 s during a slow hour) | NF-P2-001 runbook; confirmed again today, SG upload 3.8 s |
| 2. Detect | extraction | 1.4–2.0 s | NF-P2-002 runbook |
| 3. Law (RAG) | none (Firestore) | not separately measured; the mocked E2E's whole `analyze` (Firestore only, no Gemini) was 30–120 ms end to end, so this step is a small fraction of that | this task |
| 4. Compare | reasoning | **20–38 s** for 6–25 terms (3.6k–4.8k thinking tokens) — the dominant cost | NF-P2-004 runbook |
| 5. Translate | classification | not yet measured live (blocked, see above) | NF-P2-005 runbook; still open |
| 6. Complaint | reasoning | not yet measured live (blocked twice now: NF-P2-006 and this task) | NF-P2-006 runbook; still open |
| **Full pipeline** (upload + analyze, one danger contract, letter included) | — | **upload 17.1 s, analyze 74.6 s** (with 2 retries along the way) — about **92 s total** | NF-P2-007 runbook, its one successful live run |
| Pipeline overhead alone (claim, Firestore writes, orchestration — no Gemini) | — | **upload 8–120 ms, analyze 30–120 ms** per country | this task, mocked E2E |

**Reading these together:** Gemini call time is ~2–3 orders of magnitude larger than everything else the pipeline does — the plumbing (claiming the analysis, storing the contract and reports, the cache check) is not a latency concern. **Compare (step 4) is the bottleneck**, both in absolute time and in variance (D-54: extraction has also hung for as long as 76 s on a bad run). A full analysis, even with retries, has stayed well inside Cloud Run's 900 s request timeout (NF-P2-007) — the measured worst case so far is under 100 s.

**Not yet measured live:** translate and complaint, both blocked by the same quota wall. The mocked E2E confirms their *code paths* run correctly end to end; only their real timing is outstanding. Fill in once the live run above completes.

## All commands, in order

From `backend/` with the virtual environment active.

### 1. Checks (the same ones CI runs, plus tests in mypy)

```bash
ruff check .
black --check .
mypy app
mypy app tests
python -m pytest -q
```

As CI runs it, without Google credentials:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
```

### 2. Mocked full-pipeline E2E (no quota used)

```bash
firebase emulators:start --only firestore --project demo-nomadfinance      # frontend/
```

```bash
# data-scripts/, once per country not already loaded
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
    python -m src.loaders.ilo_natlex --only SG AU KR MY JP
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
    python -m src.loaders.complaint_templates --only SG AU KR MY JP
```

```bash
# backend/
FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 FIREBASE_PROJECT_ID=demo-nomadfinance \
    python -m pytest tests/integration/api/test_contract_e2e_mocked.py -v -s
```

### 3. Live E2E (real Gemini, real quota) — once available

See "Live testing" above.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `pytest -q` (no emulator, no live) | 409 passed, 38 skipped (28 pre-existing opt-in + 6 new mocked-E2E-needs-emulator + 4 new live-needs-quota) |
| The same without Google credentials (as CI) | 409 passed |
| `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass (174 files) |
| Mocked full-pipeline E2E, all 5 countries + cache reuse + loan-agreement edge case | **6 passed** |
| Live SG baseline (`test_contract_analysis_live.py`) | Extraction succeeded (3.8 s); analyze failed at compare, `429` quota exceeded — see "Live testing" |
| Live AU/KR/MY/JP (`test_contract_e2e_countries.py`) | **Not run** — blocked by the same quota wall; ready to run once available |
| Docker image build | Not run locally (Docker available on this machine per `docker --version`, but not exercised — no `Dockerfile` change to verify) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `429 RESOURCE_EXHAUSTED ... limit: 20, model: gemini-3.5-flash` on any live contract test | D-58: the shared free-tier reasoning quota is used up for the day. Wait for the 07:00 UTC reset, or use a different key. Don't retry in a loop — each attempt (and each internal 503/429 retry) counts against the same budget |
| Mocked E2E test skipped | `FIRESTORE_EMULATOR_HOST` not set, or that country's labor law/complaint template isn't loaded in the emulator yet (see command 2 above) |
| `ScriptedGemini has no answer for <Model>` | A step called `generate_structured` with a `response_model` `ScriptedGemini` doesn't recognise — check `contract_e2e_scenarios.py`'s dispatch matches every model the pipeline currently uses |
| `report_languages` looks "out of order" | It's alphabetically sorted by design (`report_store.py`) — see D-60. Not a bug |

## For teammates

- **Everyone:** the emulator started for this task (`firebase emulators:start --only firestore --project demo-nomadfinance`) is left running with SG/AU/KR/MY/JP labor law and complaint templates loaded, in case you want to run the live pass or poke around in the Emulator UI (http://127.0.0.1:4000/firestore) before it's stopped.
- **Whoever runs the live pass once quota resets:** `test_contract_e2e_countries.py` is ready; fill in the latency table above with its printed timings, and note here whether AU/KR/MY/JP's real Gemini answers ever disagree with what the mocked scenarios assumed (e.g., a different category classification) — that would be a genuine finding this task couldn't reach.
- **Billing account owner (D-58):** this is the third task in one day (NF-P2-004 testing, NF-P2-006, now NF-P2-008) to lose live-Gemini progress to the shared free-tier cap. Worth prioritizing the paid key before more E2E or demo-prep work depends on it.
- **Pranjal (NF-P2-012, language switcher):** `report_languages` is alphabetically sorted, not source-first — don't assume index 0 is the worker's own report.

## Commit and PR for this task

Branch: `fix/contract-e2e` (already checked out).

```bash
git add backend docs
git status
```

```bash
git commit -m "test(contracts): E2E test all 5 host countries, fix report_languages docs" -m "Refs: NF-P2-008"
```

PR title: `test(contracts): Contract Shield E2E for SG/AU/KR/MY/JP, latency profiling (NF-P2-008)`

## Not covered here

- The live-Gemini run for AU, KR, MY, JP, and therefore their real translate/complaint timing — blocked by D-58, ready to run
- Anything already covered by NF-P2-007's own 28 + 14 tests (claim/stale-claim, poor legibility, country fallback order, complaint_pending retry) — not duplicated here
- A paid Gemini key (D-58, still open, now flagged a third time)
- Cross-browser or frontend testing (NF-P4-001/002) — this is backend-only, no frontend built yet for Contract Shield (NF-P2-009 to NF-P2-013)
