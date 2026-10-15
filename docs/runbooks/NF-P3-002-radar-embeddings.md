# NF-P3-002 — Radar: Embedding + Clustering

## Summary

Steps 5 and 6 of the Exploitation Radar pipeline (`docs/mermaid/exploitation-radar-pipeline.mmd`), added to `POST /api/v1/radar/report` (NF-P3-001). After a report passes screening and classification, its description is embedded (`gemini-embedding-001`, 768 numbers, normalized). Firestore vector search then looks for a near-duplicate report on the same corridor. A match joins that report's `cluster_id`; otherwise the report starts its own cluster. The vector is written to `report_embeddings/{id}` after the report is saved.

Not in this task: `radar_entities` aggregation and rating (NF-P3-003), the alert cron (NF-P3-004), seed data (NF-P3-005), creating the vector index (D-33; the command is below), contract-signal reports (no free text, they keep their own cluster and get no embedding).

## Files

| File | Change |
|---|---|
| `backend/app/integrations/gemini/embeddings.py` (was an empty stub) | `embed_text`: one embedding call with tenacity retries, 30 s timeout, error mapping to the existing `Gemini*Error` classes, normalization, and a `gemini_call` log line |
| `backend/app/integrations/gemini/client.py` | Added `GeminiClient.embed_text`, which delegates to the module above |
| `backend/app/config.py`, `backend/.env.example` | Added `gemini_model_embedding` (default `gemini-embedding-001`, optional override) |
| `backend/app/repositories/radar_repo.py` | Added `find_similar`, `create_embedding`, `get_cluster_id`, and the `SimilarReport` result type |
| `backend/app/services/radar/clustering.py` (was an empty stub) | `embed_report` (step 5) and `find_cluster` (step 6), plus the match constants |
| `backend/app/services/radar/intake.py` | Calls steps 5 and 6 before the save, stores the embedding after it |
| `backend/app/api/v1/radar.py` | Docstring only |
| `backend/tests/unit/integrations/test_gemini_embeddings.py` (new) | 8 tests on the embedding call |
| `backend/tests/unit/services/test_radar_intake.py` | 9 new clustering tests; the fake Gemini and fake repository gained the new methods |
| `backend/tests/integration/api/test_radar_report.py` | The fake Gemini and fake repository gained the new methods |
| `docs/api/endpoints.md` | Steps 5 and 6 documented |

No shared files (`requirements.txt`, `firestore.rules`, `firebase.json`, ...) were touched, and no new dependency was added.

## Decisions

1. **Model `gemini-embedding-001` at 768 numbers, not `text-embedding-004`.** The tracker and original design still name the old model, which Google shut down on 2026-01-14. ADR-002, `radar.md` and D-04 already settled this. 768 because Firestore caps vectors at 2048 numbers and the model returns 3072 by default.
2. **Vectors are normalized before storing.** Shortened embeddings are not unit length, and `radar.md` requires normalizing.
3. **Match rule: cosine similarity of at least 0.85 and the same `entity_slug`.** Firestore returns the 5 nearest on the corridor; the first one that is the same business and close enough wins. The 0.85 is a first guess, not calibrated. Re-tune `MAX_MATCH_DISTANCE` in `clustering.py` (a cosine *distance*, so 0.15) once NF-P3-005 gives real near-duplicates and unrelated reports to compare.
4. **An embedding or search failure never loses the report.** If Gemini fails after its retries, or Firestore rejects the search (for example the index is missing), a warning or error is logged and the report is stored as its own cluster. On a Gemini failure no embedding is written, so that report can never be matched later.
5. **A report with no `corridor_id` is not searched.** The documented vector index is `corridor_id` plus `embedding`, so a search needs a corridor. Employer reports that only carry a `host_country` start their own cluster. Supporting them needs a second index, which is a schema change outside this task.
6. **The embedding is written after the report.** If that write fails it is logged and swallowed: the report is what the worker submitted, the vector only helps cluster later reports.
7. **`embed_text` is a method on `GeminiClient`.** The endpoint and tests already inject one Gemini object, so this avoids a new dependency and a signature change on `submit_report`.
8. **Embeddings are not a model tier.** They have their own setting (`gemini_model_embedding`) instead of a `ModelTier`, because embeddings are a different endpoint, not a generation call.

## Manual steps you need to do

Nothing here is required for the tests, which use fakes. Everything below is needed for the feature to work against real Firestore and Gemini.

### 1. Environment file

No change is needed. `GEMINI_API_KEY` already covers embeddings. `GEMINI_MODEL_EMBEDDING` is optional and only needed to override the default; it is listed (commented out) in `backend/.env.example`. Nothing changes in Secret Manager or on Cloud Run.

### 2. Create the Firestore vector index (once per project)

Without this index every search fails, is logged as `radar_similarity_search_failed`, and every report gets its own cluster. The reports are still stored, so nothing breaks visibly, which is why it is easy to miss.

Prerequisites: `gcloud` installed, signed in as an account that can create Firestore indexes, and the project selected.

```bash
gcloud auth login
gcloud config set project nomadfinance-prod
```

Create the index (bash; in PowerShell replace each trailing `\` with a backtick, or put the command on one line):

```bash
gcloud firestore indexes composite create --project nomadfinance-prod \
  --collection-group=report_embeddings --query-scope=COLLECTION \
  --field-config=field-path=corridor_id,order=ascending \
  --field-config=field-path=embedding,vector-config='{"dimension":768,"flat":{}}'
```

If `gcloud` rejects the syntax, check `gcloud firestore indexes composite create --help`; the flags for vector fields have changed between versions.

Check that it is built (the state must be `READY`; a small or empty collection takes a few minutes):

```bash
gcloud firestore indexes composite list --project nomadfinance-prod
```

Two things to know:
- Do this in the project you will test against. A dev project needs its own index; the one in `nomadfinance-prod` does not carry over.
- If your account lacks permission, the deploy account needs `roles/datastore.indexAdmin`. That and the decision on where `firestore.indexes.json` lives are part of D-33.

### 3. Test with the real backend

The Firestore emulator does not run vector queries as far as I know (I have not tested this here), so the live check needs a real Firestore project that has the index from step 2, plus your real `GEMINI_API_KEY` and `RADAR_REPORTER_HASH_SECRET` in `backend/.env.local`. Use a throwaway or dev project, not production: this writes real report documents. Point the Admin SDK at it with application-default credentials:

```bash
gcloud auth application-default login
```

Make sure `FIRESTORE_EMULATOR_HOST` is **not** set in that shell, otherwise the app talks to the emulator and the search fails.

Start the backend:

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8080
```

PowerShell:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
```

Get a Firebase ID token for a test user, then send three reports (each spends Gemini quota: 3 generation calls and 1 embedding call).

**A. First report.** Expect `201`. Keep the `report_id`.

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type":"money_transfer_operator","entity_name":"Example Remit","corridor_id":"SG-IN",
       "description":"They showed one rate on the screen and gave me a worse rate at the counter.",
       "language":"en"}' \
  http://127.0.0.1:8080/api/v1/radar/report
```

PowerShell:

```powershell
$body = @{
  entity_type = "money_transfer_operator"; entity_name = "Example Remit"; corridor_id = "SG-IN"
  description = "They showed one rate on the screen and gave me a worse rate at the counter."
  language = "en"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/v1/radar/report" `
  -Headers @{Authorization = "Bearer $env:TOKEN"} -ContentType "application/json" -Body $body
```

**B. Same incident, different words**, same business and corridor, for example "The counter staff quoted me a lower exchange rate than the app showed, so I received less money." Then in the Firebase console (Firestore data) open `radar_reports/{id of B}`: its `cluster_id` must equal the id from A.

**C. Different story, same business**, for example "They asked me for a 200 dollar fee before releasing my transfer." Its `cluster_id` must equal its **own** id.

**D. Same wording as B but a different business name** (for example "Other Remit"). Its `cluster_id` must equal its own id (a different business never joins).

Then check:
- Each report has a `report_embeddings/{id}` document with `dimension: 768`, `embedding_model: gemini-embedding-001`, and an `embedding` field of type vector.
- The backend log shows `gemini_call operation=radar.embed ...` once per report, and no `radar_similarity_search_failed` line. If that line appears with `FailedPrecondition`, the index from step 2 is missing or not yet `READY`.

### 4. Tune the threshold (optional, after NF-P3-005)

If near-duplicates in B do not cluster, or C is wrongly grouped with A, adjust `MAX_MATCH_DISTANCE` in `backend/app/services/radar/clustering.py` (0.15 = similarity 0.85; a larger number matches more).

## Automated checks

Run from `backend/` with the project venv:

```bash
.venv/Scripts/python.exe -m ruff check app tests
.venv/Scripts/python.exe -m black --line-length 100 --check app tests
.venv/Scripts/python.exe -m mypy --strict app/services app/integrations/gemini app/repositories/radar_repo.py
.venv/Scripts/python.exe -m pytest
```

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check app tests` | Clean |
| `black --check` | Clean |
| `mypy --strict app/services` | Clean (36 files) |
| `mypy --strict` on `app/services`, `app/integrations/gemini`, `radar_repo.py` | Clean (42 files) |
| `pytest` (full suite) | 670 passed, 51 skipped (live-Gemini tests, gated by `RUN_LIVE_GEMINI`) |
| New embedding tests | 8 passed: unit length and 768 size, retry on a 503, rate-limit and rejected-request errors, unusable vectors |
| New clustering tests | 9 passed: join a near-duplicate, too far, different business, deleted match, later neighbour, embedding outage, search failure, no corridor, embedding stored |

**Not verified:** no live Gemini call and no real Firestore vector search was run. The vector query and the `Vector` write are checked only against fakes; the manual steps above are the first real run.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Log `radar_similarity_search_failed` with `FailedPrecondition` / "index required" | The vector index does not exist or is not `READY` yet (step 2) |
| Every report has `cluster_id` equal to its own id, no errors | Report has no `corridor_id`; or the descriptions are not similar enough (threshold, step 4); or the business names slug differently |
| Log `radar_embed_skipped` | Gemini failed after retries (quota, outage). The report was stored without an embedding |
| No `report_embeddings` document appears | The embedding write failed (log `radar_embedding_store_failed`) or step 5 was skipped (above) |
| Search fails only locally | `FIRESTORE_EMULATOR_HOST` is set, so the app is using the emulator |
| 429 from the endpoint | The AI rate limit (10 a minute per user), not this task |

## Definition of Done

**Backend feature / Gemini pipeline step**
- [x] Structured logging (`gemini_call operation=radar.embed`; `radar_embed_skipped`, `radar_similarity_search_failed`, `radar_embedding_store_failed`)
- [x] Retry logic via tenacity, 30 s timeout
- [x] Token usage logged: partly. Embedding responses carry no token counts, so input size and latency are logged instead
- [x] Structured output via Pydantic schema, prompt stored in code: not applicable (embedding call, no prompt)
- [x] Docs updated (`docs/api/endpoints.md`, this runbook)
- [ ] Tested with 3+ diverse inputs against the real model: not done, needs the index and a live run (steps 2 and 3)
- [ ] Firestore Emulator tests: not done, the emulator does not run vector search; unit tests use fakes
- [x] Security rules: no change needed, `report_embeddings` is already backend-only
- [ ] Vector index created: not done, manual step 2 (D-33)

## Commit and PR

Branch: `feature/radar-embeddings` (already checked out).

```
feat(radar): add report embeddings and similarity clustering
Refs: NF-P3-002
```

PR title: `feat: radar embeddings and similarity clustering (NF-P3-002)`

## Noticed, not fixed

- The tracker row for NF-P3-002 still says `text-embedding-004` (already D-04), and the original design and `exploitation-radar-pipeline.mmd` name it too.
- A host-country-only report is never clustered (decision 5). If employer reports are common in the demo, a second vector index without the corridor filter would fix it.
- The cluster is only as good as the first match: a report joins the nearest single neighbour's cluster, so two clusters that later turn out to be the same incident are never merged.
- D-33 (indexes) is now the one blocker for real clustering; it still needs an owner.
