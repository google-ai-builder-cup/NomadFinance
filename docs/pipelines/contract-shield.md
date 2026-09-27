# Contract Shield pipeline

Turns an uploaded employment contract into a Contract Health Report in the worker's language, and a complaint letter when the law is broken. Design doc section 5.3; data model in `docs/data-model/collections/contracts.md`; prompts in `backend/app/prompts/contract/`.

Each step's owner adds its section below when the step is built.

## Steps

| # | Step | Task (owner) | Tier (ADR-002) | Prompt | Code | Status |
|---|---|---|---|---|---|---|
| 1 | Extract text and structure | NF-P2-001 (Devam) | extraction | `contract/extract.v2` | `services/contract/extractor.py` | Built |
| 2 | Detect language, host country, contract type, employer/salary | NF-P2-002 (Pranjal) | extraction | `contract/detect.v1` | `services/contract/detector.py` | Not started |
| 3 | Fetch the host country's labor-law rules | NF-P2-003 (Aditya) | none (Firestore) | none | `services/contract/rag.py` | Not started |
| 4 | Clause-by-clause comparison, risk per clause | NF-P2-004 (Devam) | reasoning | `contract/compare.v1` | `services/contract/comparator.py`, `risk_scorer.py` | Not started |
| 5 | Translate the report into the worker's language | NF-P2-005 (Aditya) | classification | `contract/translate.v1` | `services/contract/translator.py` | Not started |
| 6 | Complaint letter when violations are found | NF-P2-006 (Pranjal) | reasoning | `contract/complaint.v1` | `services/contract/complaint.py` | Not started |
| - | Cache reports by hash, language, law and prompt versions | NF-P2-007 (Devam) | none | none | `services/contract/pipeline.py` (proposed) | Not started |

Not owned yet (D-53): storing the upload in Cloud Storage, the `users/{uid}/contracts/{id}` document and its `status`, `pipeline.py` running the steps in order, and the endpoint the upload UI calls for a full analysis. Proposed: NF-P2-007, since the cache needs the contract document and `content_hash` anyway.

## Flow

```
upload (PDF or photo, ≤ 10 MB)
  1 extract_contract(bytes, mime_type)      → ExtractedContract (blocks, title, legibility) + text
       legibility "poor" → stop and ask for a clearer photo (the pipeline's choice)
  2 detect(text)                            → language, host_country, job_type, employer, salary
  3 rules(host_country)                     → labor_laws/{country}/rules + law_version
  4 compare(text or blocks, rules, job)     → clauses[] with risk, law_reference, explanation
       health score computed in code from the clause risks
  5 translate(report, user language)        → reports/{lang}
  6 complaint(danger clauses, template)     → complaint letter (only if violations)
store: contract document + reports/{lang}, with prompt_versions and law_version (cache key)
```

Every step records its prompt as `{prompt.key: prompt.version}` in `prompt_versions` (see `docs/data-model/versioning.md`).

## Step 1: extract text and structure (NF-P2-001)

`extract_contract(data, mime_type, gemini)` in `backend/app/services/contract/extractor.py`.

- **In:** the file bytes (size- and type-checked by the endpoint: PDF, PNG, JPEG, WebP, HEIC).
- **Gemini call:** extraction tier, prompt `contract/extract.v2` (key `contract.extract`, version 2), response schema `ExtractedContract`.
- **Out:** `(ExtractedContract, text)`:
  - `blocks`: the document in reading order. Each has `page`, `kind` (heading, clause, paragraph, list_item, table, signature, other), `number` as printed, and the exact `text` in the original language. A table is one row per line with ` | ` between cells.
  - `title`, `page_count`, `legibility` (`good`, `partial`, `poor`), `is_document`.
  - `text`: built in code by `contract_text()`: each block's number then its text, blocks separated by a blank line. Not asked from Gemini a second time, which would double the output tokens and the time.
- **Errors:**
  - `NotADocumentError` when Gemini finds no document or no text (the endpoint answers 422).
  - Gemini failures raise `GeminiError` subclasses (503/504/502/500).
  - `legibility: "poor"` is returned, not raised.
- **Time:** about 2.6 s per PDF page when Gemini is healthy (2 pages: 3.4 s; 6 pages: 12.7 to 17.6 s; 15 pages: 39 s). The same 2-page PDF also took 76 s during a slow hour. Per attempt, photos time out after 30 s (`GEMINI_TIMEOUT_SECONDS`) and PDFs after 90 s (`GEMINI_EXTRACTION_TIMEOUT_SECONDS`), with up to 3 attempts, which stays under Cloud Run's 300 s.
- **For step 2 and step 4:** use `text` for prompts that take the whole contract. The clause numbers and `kind` in `blocks` can map the comparison's clauses back to the document; this is NF-P2-004's choice.
- **Standalone endpoint:** `POST /api/v1/contracts/extract` (`docs/api/endpoints.md`).
