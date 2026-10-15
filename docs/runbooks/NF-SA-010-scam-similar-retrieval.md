# NF-SA-010 — Similar-scam retrieval ("seen N times")

## Summary

`POST /api/v2/scam/analyze` now fills `similar` and `corridor_report_count` (docs/api/v2-scam.md). The redacted message is embedded once (`gemini-embedding-001`, 768 numbers, the same as the 480 templates of NF-SA-006), and that vector is searched in two places:

- **`scam_patterns`**: the 5 nearest of any type and language (no filter, the plain vector index).
- **Radar `report_embeddings`**: the 10 nearest on the worker's corridor (the existing `corridor_id` + `embedding` index). Skipped when the worker sent no corridor.

What the answer shows:

- **`similar`**: at most 3, closest first, only those at or above the cutoff, **one per source and scam type**. Each is `{source, scam_type, score}`, a score from 0 to 1. No id and no template or report text leaves the backend.
- **`corridor_report_count`**: how many of the 10 Radar reports on the corridor are above the cutoff, so 0 to 10; `null` with no corridor or a failed search.

**Nothing here can fail a check.** If the embedding call fails, the search takes over 8 s, a Firestore search fails (the index is not deployed, the collection is empty, a permission error), the answer carries `similar: []` and `corridor_report_count: null` (or just the part that did work), and the verdict and explainer are unchanged.

The dependencies NF-SA-006 (templates) and NF-SA-007 (the verdict) are merged. Not in this task: indicators (NF-SA-011), storing and caching a check and the rate limit (NF-SA-012), the one-tap report (NF-SA-013), the screens (NF-SA-016), loading the templates into production (D-135) and deploying the vector index from the file (D-114).

## How it works

```
analyze_text / analyze_screenshot
  redact ──┬─ SimilarScamFinder.find ── embed ──┬─ scam_patterns (5 nearest)
           │     (starts first, own 8 s box)    └─ report_embeddings on the corridor (10 nearest)
           └─ classify ── explain ───────────────→ answer = verdict + explainer + similar + count
```

The search is a task started before the classification and awaited after the explainer, so it costs no waiting. Its answer is **never given to the classifier or the explainer**: a poisoned template or report cannot steer the verdict (design 5.2). If the classification fails, the search is cancelled.

**Tie to the data:** a report's scam type is read from its Radar entity slug (`scam-illegal-recruitment-fee` gives `illegal_recruitment_fee`) when it is a scam report and one of the taxonomy's types; any other report (an agency's hidden fee) has `scam_type: null`, which the contract allows.

**Cost:** one extra Gemini embedding call per check that reaches Gemini, on the embedding model's own quota, plus two Firestore vector queries. Repeat messages will skip all of it when the cache exists (NF-SA-012).

## Files

| File | Change |
|---|---|
| `backend/app/repositories/scam_pattern_repo.py` (new) | `ScamPatternRepository.find_similar`; returns the id, the type and the distance of each template, never its text |
| `backend/app/services/scam/retrieval.py` (new) | `SimilarScamFinder`: embed, search, cutoff, one per type, count, and the failure rules |
| `backend/app/services/scam/analyzer.py` | Starts the search beside the classification; fills `similar` and `corridor_report_count` |
| `backend/app/dependencies.py`, `backend/app/api/v2/scam.py` | `get_similar_scam_finder`, and the endpoint takes it |
| `backend/tests/unit/services/test_scam_retrieval.py` (new) | 18 tests with a fake embedder and fake repositories |
| `backend/tests/fixtures/scam_similar.py` (new), `scam_app.py` | `FakeFinder`; the test app replaces the search so no endpoint test touches Firestore or Gemini embeddings |
| `backend/tests/integration/api/test_scam_analyze.py`, `test_scam_analyze_screenshot.py` | The answer equals the mocks' `similar` and `corridor_report_count`; the search gets the redacted text, the corridor and the taxonomy types; no ids in the answer; a failed classification does not wait for the search; the screenshot path searches too |
| `data-scripts/src/loaders/scam_patterns_calibrate.py` (new), `tests/test_scam_patterns_calibrate.py` (new) | The command that chooses the cutoff from the golden sets (7 tests) |
| `data-scripts/src/embedding.py`, `tests/test_embedding_resilience.py` (new), and the three loaders that embed | A daily or very long quota stops the run at once with a clear message instead of retrying for twelve minutes; `CachedEmbedder` keeps finished embeddings in a temp file (`nomadfinance-embedding-cache.json`, or `EMBEDDING_CACHE_FILE`) so a run that dies resumes (12 tests). Added after the first calibration run hit the free tier's limit |
| `docs/api/v2-scam.md`, `docs/data-model/collections/scam.md` | The state row and the two field definitions; D-137 updated, D-141 to D-143 |

No shared files, no new dependency, no workflow change. The contract's response models did not change.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The search runs beside the classification, with its own 8 s time box | The verdict budget is a few seconds and neighbours must never add to it; design 5.2 says the results are returned, not fed to the classifier |
| 2 | Templates: 5 fetched, no filter. Radar: 10 fetched, on the worker's corridor | The templates need only the plain index (scam.md); the Radar index is `corridor_id` + `embedding`, so a search needs a corridor |
| 3 | `corridor_report_count` counts the nearest 10 Radar reports that are above the cutoff | It means "reports like this one on your corridor", not "all reports on the corridor". Capped at 10. The data model says "found on the corridor when the check ran" |
| 4 | One entry per source and scam type | Three Hindi, Nepali and Bengali copies of one lottery template are one finding |
| 5 | The cutoff is a constant that starts at 0.85, to be set by `scam_patterns_calibrate` (D-141) | A guess would be wrong in a way nobody sees: a safe message told "seen before" |
| 6 | Only Firestore and Gemini errors are absorbed; any other exception still surfaces | A search that hides a bug is worse than one that fails loudly |
| 7 | The answer has `{source, scam_type, score}`; the internal match keeps the id | Contract: no ids and no text of other people's reports; NF-SA-012 stores the id (D-142) |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy --strict app/services` (backend) | clean |
| `pytest` (backend) | **1656 passed, 94 skipped** (the live tests) |
| `black`, `ruff`, `mypy`, `pytest` (data-scripts) | clean, **403 passed**; 7 are new |
| The calibration report | Printed once with an offline stand-in embedder to check its layout (the numbers are meaningless there). **Not run with Gemini: no key in this session** |
| Not run | A real search against `scam_patterns` and `report_embeddings`: the collection is not loaded in production (D-135) and the index deploy is untested (D-114). The repository is tested against a fake collection, and the real call mirrors the one `RadarRepository.find_similar` already makes |

## Do this: set the cutoff (D-141)

From `data-scripts/` with its own `.venv` active:

PowerShell:

```powershell
$env:GEMINI_API_KEY = "<your key>"
python -m src.loaders.scam_patterns_calibrate
```

It embeds the 480 templates and the 120 golden messages (about 600 texts, about 6 minutes on the free tier, waiting where Google asks) and prints:

- the spread of the closest-template similarity for the 84 scams and for the 36 benign look-alikes;
- a table for 0.70, 0.75, 0.80, 0.85 and 0.90: the share of scams and of safe messages each cutoff would show;
- the 8 safe messages closest to a known scam (they decide the cutoff) and the 5 scams furthest from any template;
- a suggested cutoff.

**If it stops with `Gemini will not embed more for now (...PerDay...)`**: the free tier's daily embedding quota is used up (earlier runs of the NF-SA-006 check and the calibration count against it). Nothing is lost: every batch already embedded is saved in `nomadfinance-embedding-cache.json` in your temp folder, and the next run, tomorrow or on a key with billing, embeds only the rest. Delete that file to start fresh.

Send the output and the constant gets set (`PATTERN_MIN_SCORE` in `backend/app/services/scam/retrieval.py`; the two sample mocks with scores of 0.83 and 0.74 get adjusted to agree).

## Try it for real

After D-135 (templates loaded) and D-114 (index deployed), with the backend running and a token (commands in `docs/api/v2-scam.md`, "Analyze"): send a message of a known shape (a recruitment fee, say) with a `corridor_id`. `similar` should show a `scam_pattern` of the right type with a score above the cutoff. Until then every answer has `similar: []`, and the log says `scam_similar_patterns_failed` (no index) or `scam_similar patterns=0` (collection empty). Neither is an error to the worker.

## Not done, and why

- **The cutoff is a first guess** (D-141): it needs your key and a few minutes.
- **The real Firestore searches are untested** until the templates are loaded and the index deployed (D-135, D-114).
- **The Radar cutoff is not calibrated** (D-143): there are no scam reports yet.
- **Not stored, not cached** (NF-SA-012; D-142 says what it must keep).

## Definition of Done (backend endpoint)

- [x] Returns at most 3 neighbours above a cutoff, one per source and type; no id and no text
- [x] Degrades to an empty list (`corridor_report_count` `null`) when any search fails; the verdict is unchanged
- [x] The search never reaches the classifier; the raw message never reaches it (only the redacted text)
- [x] Tests, lint, format, `mypy --strict app/services` pass; the answer equals the mocks
- [x] `docs/api/v2-scam.md` and the data-model doc updated
- [ ] Cutoff set from data (D-141)
- [ ] Searched against the real loaded collection and index (D-135, D-114)
- [ ] Rate limiting: not this task (the general 10-a-minute budget applies; the 20-an-hour limit is NF-SA-012)
