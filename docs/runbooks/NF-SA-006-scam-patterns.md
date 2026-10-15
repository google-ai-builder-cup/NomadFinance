# NF-SA-006 — Known-scam pattern library and embeddings

## Summary

480 synthetic scam templates, embedded and stored in Firestore `scam_patterns/`, so the Scam Analyzer can ask "which known scams does this message look like" by vector search (NF-SA-010). **60 per scam type, 10 per language in every type** (English, Hindi, Tagalog, Indonesian, Nepali, Bengali), and **every one of the six corridors in at least 3 templates per type**. Placeholders (`[AGENCY]`, `[AMOUNT]`, ...) stand for names and sums; contact points are written the way the redactor writes them (`[PHONE]`, `[EMAIL]`, `[ID]`, `[ACCOUNT]`, `[URL]`), because the analyzer embeds the redacted message.

**The tracker says `text-embedding-004`; that is wrong.** The model is `gemini-embedding-001`, asked for 768 numbers and rescaled to unit length. This is the same model, size and task type the backend uses (`backend/app/integrations/gemini/embeddings.py`, ADR-002), and it is the size of the vector index in `frontend/firestore.indexes.json`. A vector from any other model or size cannot be compared with the stored ones.

Scope: the six corridors only: SG→PH, SG→IN, AU→IN, MY→ID, JP→PH, AU→PH. No Gulf country and no Korea appears anywhere (the tracker's AU-side wording is read as Australia). The validator rejects a template that names a place outside them.

Not in this task: the retrieval used when a message is analysed (NF-SA-010), the classifier prompts (NF-SA-007), the eval runner (NF-SA-014), and deploying the vector index from the file (D-114).

## What is in it

| | Count |
|---|---|
| Templates | 480 (8 scam types × 60) |
| Per type and language | 10 each, for all 6 languages |
| Typed in Latin letters | 32: two Hindi, one Nepali and one Bengali per type (workers often type these in Latin letters, as in the golden sets) |
| By corridor | MY-ID 72, SG-IN 40, AU-IN 40, SG-PH 32, JP-PH 32, AU-PH 32, no route 232 (the Nepali and Bengali templates, and some others, are for workers whose route is not one of the six) |
| Tactics used | urgency 224, scarcity 178, authority 144, reciprocity 90, social proof 81, fear 79 |

Each type has 10 scenarios, each written in all six languages in the way a local scammer would put it, not as a word-for-word translation. For example, fake job offer: hotel cleaner, warehouse, farm work, factory form, caregiver, the "favour" recruiter, work-from-home rating, driver, nurse aide, restaurant staff.

## Files

| File | Change |
|---|---|
| `data-scripts/data/source/scam-patterns/<scam_type>.jsonl` (8 new) | The templates: `id`, `scam_type`, `language`, `tactics`, `text`, `corridor_id`, `curator` |
| `data-scripts/src/validators/scam_patterns.py` (new) | `PatternRow` (the schema), `load_all`, `check_library` (size, language and corridor coverage, repeats), the spot-check picker and the command |
| `data-scripts/src/embedding.py` (new) | `GeminiEmbedder`: batches of 50, 30 s timeout, retries on 429/5xx, 768 numbers, unit length; the SDK is imported when it is first used |
| `data-scripts/src/loaders/scam_patterns.py` (new) | The idempotent embed-and-load |
| `data-scripts/src/loaders/scam_patterns_check.py` (new) | The nearest-neighbour check, in memory or through Firestore |
| `data-scripts/tests/test_scam_patterns.py`, `test_scam_patterns_loader.py` (new) | 57 tests, with a fake embedder and a fake Firestore client |
| `data-scripts/src/config.py`, `data-scripts/.env.example`, `data-scripts/README.md` | Path constant, `GEMINI_API_KEY=` placeholder, a README section |
| `docs/data-model/collections/scam.md` | `scam_patterns`: added `corridor_id` (optional) and `content_hash`; counts |
| **`data-scripts/requirements.txt` (shared file; NOT edited, see below)** | needs `google-genai==2.25.0` |

## Do this first: one line in a shared file

`data-scripts/requirements.txt` does not have the SDK that makes the embeddings. It was not edited here (a shared file, and the edit was blocked), so add this line yourself, then install:

```diff
 firebase-admin==7.7.0
+google-genai==2.25.0
```

Same pin as `backend/requirements.txt`. Until it is added, `mypy src tests` reports one error (`src/embedding.py:64`, the SDK is missing) and so will the data CI. Nothing else needs it: the validator, the tests and `--dry-run` run without it.

PowerShell, from `data-scripts/` with its own `.venv` active (see the README, "Setup"):

```powershell
pip install -r requirements-dev.txt
```

## Run it

From `data-scripts/`, virtual environment active:

```bash
python -m src.validators.scam_patterns
```

Expected: `OK   480 templates, 8 types, 6 languages`, then 60 per type, `0 reviewed`.

```bash
python -m src.loaders.scam_patterns --dry-run
```

Expected: `Validated 480 templates` and a `[dry-run]` line. No Gemini call, no Firestore.

### 1. The nearest-neighbour check, in memory (needs only the key)

PowerShell:

```powershell
$env:GEMINI_API_KEY = "<your key>"
python -m src.loaders.scam_patterns_check
```

bash:

```bash
export GEMINI_API_KEY="<your key>"
python -m src.loaders.scam_patterns_check
```

It embeds the 480 templates and the 84 golden scams (564 texts, about 12 requests of up to 50), and prints:

- `Held-out gate: N of 10 hit`, each of the 10 with its three nearest templates and their similarity. **The tracker's bar is 10 of 10.**
- `All golden scams: N of 84 hit in the top 3`, by type and by language, and every miss outside the gate.

The 10 held-out scams are a fixed pick, the same ones every run, covering all 8 types and all 6 languages: `gold-en-007`, `gold-hi-001`, `gold-tl-002`, `gold-id-009`, `gold-ne-005`, `gold-bn-013`, `gold-en-019`, `gold-hi-004`, `gold-tl-007`, `gold-id-003`. A hit means one of the three nearest templates has the same scam type. The exit code is 1 if any of the 10 misses.

### 2. Load it into Firestore and check through vector search

Needs credentials with write access to the project, and for the live check the vector index on `scam_patterns.embedding` (dimension 768, flat; defined in `frontend/firestore.indexes.json`, deploy: D-114).

```powershell
gcloud auth application-default login
$env:GEMINI_API_KEY = "<your key>"
python -m src.loaders.scam_patterns
python -m src.loaders.scam_patterns          # second run: 480 unchanged, 0 embedded
python -m src.loaders.scam_patterns_check --firestore
```

Expected first run: `Loaded 'scam_patterns': 480 new, 0 changed, 0 unchanged, 0 removed (480 embedded)`. Second run: `0 new, 0 changed, 480 unchanged, 0 removed (0 embedded)`. That second line is the "idempotent" check.

The Firestore emulator is not used for the vector query: I have not confirmed it supports `find_nearest`, so the live check is against the real project (D-135).

### 3. The second teammate's review (10 templates)

```bash
python -m src.validators.scam_patterns --spot-check 10
```

lists a fixed sample (the same ten every time): one scenario from every type and every language. The reviewer asks, for each: is this something a scammer really sends, does the type match the mechanism, are the tactics really in the text, is it free of anything that could be real, and does it read naturally in its language? Their initials go in `reviewed_by` on that row (`"reviewed_by": "PP"` at the end of the line). Before merging:

```bash
python -m src.validators.scam_patterns --require-reviewed 10
```

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | `gemini-embedding-001` at 768, normalised, task type `SEMANTIC_SIMILARITY` | Same as the backend and the index; the tracker's `text-embedding-004` was shut down and is not the model in use |
| 2 | 10 templates per language per type | A Nepali message must not be matched on a thinner shelf than an English one, and per-language results stay comparable. The model is multilingual, so cross-language neighbours still work |
| 3 | Templates were written independently of the golden sets, and a test refuses one that is 60% the same words as a golden message | The golden scams are the held-out queries; a template written from one would make the check measure memory. The check caught one of my own (`illegal_recruitment_fee-en-001`, 68%), and the other nine that scored about 50% or more were rewritten too |
| 4 | Vectors are not committed; the loader embeds | 480 × 768 numbers would be about 4 MB of noise in every diff, and they depend on the model |
| 5 | Idempotency by a stored `content_hash` (text, labels, model, size; not the curator) | A second run costs no embedding call and no write; changing the model re-embeds everything |
| 6 | All embeddings are made before the first write | A Gemini failure part-way writes nothing |
| 7 | The check redacts a query with the backend's own `redact_text` (loaded by path) | The analyzer embeds the redacted message, so a test on raw text would flatter or punish the search wrongly |
| 8 | A `corridor_id` field on the template (optional), not filtered on in a search | The user asked for every corridor to be covered; the field makes that checkable and available later. A search stays unfiltered (nearest 3 of any type and language), so no composite index is needed |
| 9 | Place check: a template naming Korea, the Gulf states and so on is rejected | The scope has six corridors and no others |
| 10 | Tests use a fake embedder and a fake Firestore client; CI never calls Gemini | No key in CI, no cost, deterministic |
| 11 | Retries are a short loop in `embedding.py`, not `tenacity` | `tenacity` is not in `data-scripts/requirements.txt` and adding it is a second shared-file edit; a one-off script needs 4 attempts and a back-off, not a policy library |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black --check .`, `ruff check .` (data-scripts) | clean |
| `mypy src tests` (data-scripts) | clean once `google-genai==2.25.0` is installed (before that: 1 error, the missing SDK) |
| `pytest` (data-scripts) | **395 passed**; 57 of them are new |
| The committed library | 480 templates, 60 per type, 10 per language per type, every corridor 3 or more per type, 32 in Latin letters, no near-copies, nothing outside the six corridors, no real link, address or number |
| Tampered rows | A bad id, type, tactic, placeholder, link, address, number, place, script, a self-review and a wrong corridor each fail with the reason; a missing language, corridor, type or id gap fails the library check |
| The real `GeminiEmbedder` | Smoke-tested with the real SDK types and a stubbed call (the backend's environment has the SDK): 60 texts go in batches of 50 and 10, a 503 is retried once, the request carries model `gemini-embedding-001`, task type `SEMANTIC_SIMILARITY` and 768 dimensions, and the vector is rescaled to length 1 |
| The nearest-neighbour check, in memory (run by Devam, free-tier key) | **Held-out gate: 10 of 10 hit. All 84 golden scams hit in the top 3** (every type, every language). Closest-template similarity 0.83 to 0.97; the weakest of the 10 was `gold-id-009` (investment or romance), 0.847. The free tier allows 100 embedding texts a minute, so the run took about 6 minutes, waiting where Google asked |

## Not done, and why

- **The 10-of-10 result is measured in memory only**, not through Firestore Vector Search (D-135). The scores say nothing yet about benign look-alikes: a safe message may also land close to a template, which is what D-137 asks NF-SA-010 to measure before choosing a cutoff.
- **Not loaded into Firestore** (D-135). Writing to the production project is your step.
- **No native speaker has read the templates** (D-134), and **no second teammate has spot-checked 10** (D-136). The tracker's acceptance is not met until the latter is.
- **A similarity cutoff for "seen before" is not chosen** (D-137, NF-SA-010).
- **`google-genai` is not in `data-scripts/requirements.txt`** (above).
- The data CI does not run `python -m src.loaders.scam_patterns --dry-run`; the tests already validate the committed files, and the workflow is a shared file.

## Definition of Done (curated dataset, plus the task's own)

- [x] ≥ 60 canonical templates for each of the 8 scam types (60 each), in the six languages and covering all six corridors
- [x] Validated against a schema; the validator and the loader are idempotent (a second run embeds nothing)
- [x] Source and curator recorded on every row; synthetic only, enforced by the validator; only the six corridors, no Korea
- [x] Embedded with the Gemini embedding model (`gemini-embedding-001`, 768), not `text-embedding-004`
- [x] Tests, lint, format, mypy: pass (396 tests)
- [x] **Nearest-neighbour sanity test: 10 held-out scams each retrieve a same-type template in the top 3**: 10 of 10, and 84 of 84 for all golden scams (in memory)
- [ ] Vectors stored in Firestore and verified through Vector Search (D-135)
- [ ] A second teammate spot-checked 10 templates (D-136)
- [ ] A native speaker read the templates (D-134)
