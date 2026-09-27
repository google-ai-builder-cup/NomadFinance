# NF-P2-001 — Contract Shield: Text Extraction Step

## Summary

Step 1 of Contract Shield now returns the contract's **structure**, not just a flat transcription. `POST /api/v1/contracts/extract` (and `extract_contract()` for the pipeline) returns the document as ordered **blocks**:
- headings
- numbered clauses with their number as printed
- list items like (a) and (b)
- whole tables, one row per line with ` | ` between cells
- signatures

Each block has its page number and the exact words in the original language. The response also gives the title, the page count and a legibility grade (`good` / `partial` / `poor`, so the UI can ask for a clearer photo). The plain `text` is **built in code** from the blocks rather than asked from Gemini a second time, which keeps output tokens and time down. It's the same `text` the next steps (detection, comparison) take as input.

The prompt is `contract/extract.v2`. v1 was removed: no stored result ever used it.

Live runs show about **2.6 s per PDF page** when Gemini is healthy: a 15-page contract finished in 39 s with all 75 clauses in order. The old 30 s timeout would have failed any contract over about 10 pages after three timed-out attempts. The Gemini client therefore gained a per-call timeout: **PDFs get 90 s** (3 attempts still fit in Cloud Run's 300 s), and photos keep 30 s. Gemini's extraction model also hangs or slows down at times (the same 2-page PDF took 3.4 s, then 76 s); timeouts and retries recover most of it (D-54).

## Files

| File | Change |
|---|---|
| `backend/app/prompts/contract/extract.v2.yaml` | New prompt: ordered blocks with page, kind, number, text; title; legibility; tables as ` | ` rows |
| `backend/app/prompts/contract/extract.v1.yaml` | Removed (no stored result uses it) |
| `backend/app/schemas/contract.py` | `ContractBlock`, `ExtractedContract` (Gemini response schema, replaces `ExtractedText`), `ContractExtractResponse` gains `title`, `legibility`, `blocks` |
| `backend/app/services/contract/extractor.py` | `extract_contract()` returns `(ExtractedContract, text)`; `contract_text()` builds the text; `EXTRACT_PROMPT` for `prompt_versions`; 90 s timeout for PDFs |
| `backend/app/api/v1/contracts.py` | Returns the new fields; summary and docstring |
| `backend/app/integrations/gemini/client.py` | `generate_structured(..., timeout_seconds=None)`: per-call timeout, default `GEMINI_TIMEOUT_SECONDS` |
| `backend/app/config.py` | `gemini_extraction_timeout_seconds` (default 90) |
| `backend/tests/unit/services/test_contract_extractor.py` | Prompt v2 and tier, text building (order, numbers, tables, empty blocks), poor legibility returned, rejections, PDF vs photo timeout |
| `backend/tests/integration/api/test_contracts_extract.py` | New response shape |
| `backend/tests/integration/api/test_contracts_extract_live.py` | Real Gemini: English PDF, Indonesian photo, generated 6-page contract with a fee table, selfie; prints each duration |
| `backend/tests/unit/integrations/test_gemini_client.py` | Per-call timeout overrides the default |
| `backend/tests/unit/test_prompt_loader.py` | Expects `contract/extract.v2` |
| `docs/api/endpoints.md` | Extract section: fields, blocks, timing, real example |
| `docs/pipelines/contract-shield.md` | Was empty: step table with owners, flow, step 1 in detail |
| `docs/data-model/collections/contracts.md`, `docs/runbooks/NF-P1-006-document-extract.md` | Pointers to the new names |
| `docs/deferred-items.md` | D-48 owner corrected (Pranjal); new D-53 (pipeline owner), D-54 (Gemini hangs) |
| `backend/app/prompts/README.md`, `backend/.env.example` | Prompt table lists `extract.v2`; optional `GEMINI_EXTRACTION_TIMEOUT_SECONDS` |

## Decisions

1. **Blocks, with the text built in code.** Asking for both would double output tokens and time (6 pages: 3,691 output tokens for the blocks alone).
2. **v2 prompt, v1 deleted.** Nothing stored used v1, so it isn't kept (`backend/app/prompts/README.md`, "Changing a prompt").
3. **`legibility` is information, not an error.** The endpoint returns 200; the pipeline or UI decides to ask for a clearer photo. Only "no document at all" is 422.
4. **Tables as ` | ` rows** in one block: readable by the comparison step, and the header row keeps the column meaning.
5. **Timeout by file type:** 90 s for PDFs (output grows with pages), the default 30 s for photos (one page; a hung attempt is retried sooner). The page count can't be read reliably from PDF bytes without a new dependency.
6. **Step 1 only.** The pipeline as a whole (storage, contract document, `pipeline.py`, full-analysis endpoint) has no owner yet (D-53). Proposed: NF-P2-007.

## Flow

```
POST /api/v1/contracts/extract (multipart "file")
  size check (413), type from bytes (415), auth (401), rate limits (429)
  extract_contract(bytes, mime_type)                     [services/contract/extractor.py]
    └─ GeminiClient.generate_structured(
         operation="contract.extract", tier=EXTRACTION,
         system=extract.v2 system, contents=[file, "Transcribe the attached document."],
         response_model=ExtractedContract,
         timeout_seconds=90 for PDFs / default 30 for photos)       3 attempts on timeout/503/429
    └─ contract_text(): "<number> <text>" per block, blank line between blocks
    └─ no document or no text → NotADocumentError → 422
  200 {filename, mime_type, size_bytes, page_count, title, legibility, text, blocks[]}
```

## All commands, in order

From `backend/` with the virtual environment active (`.venv\Scripts\Activate.ps1` in PowerShell, `source .venv/Scripts/activate` in Git Bash).

### 1. Checks

```bash
python -m pytest -q
ruff check .
black --check .
mypy app tests
```

As CI runs them, without Google credentials (Git Bash):

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent CLOUDSDK_CONFIG=/tmp/empty APPDATA=/tmp/empty python -m pytest -q
```

### 2. Live tests against real Gemini (uses free-tier quota, about 4 calls)

```bash
RUN_LIVE_GEMINI=1 python -m pytest tests/integration/api/test_contracts_extract_live.py -v -s
```

PowerShell:

```powershell
$env:RUN_LIVE_GEMINI = "1"; python -m pytest tests/integration/api/test_contracts_extract_live.py -v -s; Remove-Item Env:RUN_LIVE_GEMINI
```

`-s` prints each call's duration. A `gemini_retry ... did not respond` warning is Gemini hanging (D-54), not a failure, as long as the test passes.

### 3. Try the endpoint by hand

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The endpoint needs a real Firebase ID token. The simplest way is the Swagger page at http://127.0.0.1:8080/docs with a token from the signed-in app. In the browser console on the running app (`pnpm dev`):

```js
await (await import("/src/lib/firebase.ts")).auth.currentUser.getIdToken()
```

Then:

```bash
curl -s -H "Authorization: Bearer $TOKEN" -F "file=@tests/fixtures/contracts/sample_contract_sg.pdf" http://127.0.0.1:8080/api/v1/contracts/extract
```

## Verified results (2026-09-27)

| Check | Result |
|---|---|
| `pytest -q` | 217 passed, 6 skipped (the live tests) |
| The same without Google credentials (as CI) | 217 passed |
| `ruff check .`, `black --check .`, `mypy app tests` | Pass |

Live runs (`gemini-3.5-flash-lite`):

| Input | Result | Time |
|---|---|---|
| `sample_contract_sg.pdf` (2 pages, English) | Title, 12 blocks (heading, 2 paragraphs, 8 clauses, signature), pages 1 and 2, `good` | 3.4 to 3.8 s; 76 s during a slow hour |
| `sample_contract_my_id_photo.jpg` (Indonesian phone photo) | "PERJANJIAN KERJA", 9 blocks (clauses 1 to 6, parties as paragraphs), stays in Indonesian ("Gaji bulanan: RM 1.500"), `good` | 2.7 to 3.2 s; 42 s when the first attempt hung |
| Generated 6-page contract | 76 blocks: 24 clauses **in order**, 48 list items (a)/(b), the fee table on page 4 as `Item \| Amount \| Paid by` rows, signature on page 6; 3,676 in / 3,691 out tokens | 10.8 to 17.6 s; 77 s during a slow hour |
| Generated 15-page contract | 75 clauses in order, 8,356 in / 7,356 out tokens | 39.1 s (would fail with the old 30 s timeout) |
| `not_a_document.jpg` (selfie) | 422 | 2.0 s |

Gemini hangs seen on 2026-09-27 (D-54):
- a photo's first attempt hung several times, then the retry answered in about 2 s
- one run of the 6-page PDF hung on all 3 attempts (504 after 271 s)
- the same PDF then finished in 10.8 s, a normal 3,691 tokens with `finish_reason=STOP`, so it is not a runaway generation

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 504 "The AI service took too long" | Every attempt timed out: Gemini hanging (D-54), or a very long PDF. Try again; if it repeats for PDFs over about 25 pages, raise `GEMINI_EXTRACTION_TIMEOUT_SECONDS` (keep 3 × it + 16 s under Cloud Run's 300 s) |
| `gemini_retry ... did not respond within 30s` in logs | A hung attempt; the retry usually succeeds |
| 502 "unusable answer" | Gemini's JSON didn't match `ExtractedContract`; retry. If it repeats for one file, keep the file for NF-P2-008 |
| `legibility: poor` | Blurry, dark or cut-off photo: ask for a new photo in good light, whole page in frame |
| Clause numbers missing | The document has none; `kind` still says clause or paragraph. The comparison splits clauses itself |
| Live test fails on an assertion about wording | Gemini output varies a little; check the printed response before changing the prompt |

## Definition of Done (Gemini Pipeline Step)

- [x] Correct model tier: extraction (`gemini-3.5-flash-lite`, ADR-002)
- [x] Structured output via Pydantic `response_schema` (`ExtractedContract`), no free-text parsing
- [x] Retry logic via tenacity (unchanged; 3 attempts on timeout, 503, 429)
- [x] Timeout set: 30 s default, 90 s for PDFs (`GEMINI_EXTRACTION_TIMEOUT_SECONDS`)
- [x] Token usage logged (`gemini_call operation=contract.extract ... prompt_tokens output_tokens`)
- [x] Prompt in a versioned file (`contract/extract.v2.yaml`)
- [x] Tested with 3+ diverse inputs: long doc (6 and 15 pages), non-English photo, table, malformed (selfie)

## Commit and PR for this task

Branch: `feature/contract-extract` (already checked out).

**Note:** while building this, `git rm --cached` was run on `backend/app/prompts/contract/extract.v1.yaml` by mistake. That staged the file's deletion (git status shows `D ` for it). The deletion is intended and the file is gone from disk, so committing it is correct. To stage everything yourself instead, undo it first with `git restore --staged backend/app/prompts/contract/extract.v1.yaml`.

```bash
git add backend docs
git status
```

```bash
git commit -m "feat(contracts): extract contract structure as ordered blocks" -m "Refs: NF-P2-001"
```

PR title: `feat(contracts): structured contract extraction with blocks, legibility, PDF timeout (NF-P2-001)`

## For teammates

- **Everyone:**
  - No new packages and no new required settings: after pulling, nothing to install.
  - `.env.local` needs no change. `GEMINI_EXTRACTION_TIMEOUT_SECONDS` is optional (default 90).
- **Pranjal (NF-P2-002, detection):**
  - Take the contract as `text` from `extract_contract()` (the second value it returns). That's the `${contract_text}` of `contract/detect.v1`.
  - D-48 (daily wages) is yours.
  - Add your step to `docs/pipelines/contract-shield.md`.
- **Aditya (NF-P2-009, upload UI):**
  - Call `POST /api/v1/contracts/extract` with a `multipart/form-data` field `file`.
  - Show a "please retake the photo" message when `legibility` is `poor`, and a note when it's `partial`.
  - The call can take 3 s to over a minute, so show progress and don't time out on the client before 5 minutes. A 504 means "try again".
  - Check the file size (10 MB) in the browser before uploading: the server refuses larger files with 413, but only after Cloud Run has received the whole upload.
  - Mirror `ContractExtractResponse` and `ContractBlock` in `frontend/src/types/contract.ts` (see `docs/api/endpoints.md`).
- **Aditya (NF-P2-003, law retrieval):** no change.
- **Team:** decide who builds the pipeline as a whole (D-53).

## Not covered here

- Steps 2 to 6: NF-P2-002 to NF-P2-006 (`docs/pipelines/contract-shield.md`)
- Pipeline orchestration, storage, full-analysis endpoint: D-53
- Upload UI and "retake photo" message: NF-P2-009; progress display: NF-P2-010
- Local PDF text extraction without Gemini: D-54 (option)
