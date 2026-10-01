# contracts

Shape sources: the contract path is **[D]**. The pipeline steps that decide the fields are in the design doc (Contract Shield pipeline) and NF-P2-001 to NF-P2-007 **[T]**. The split into a light contract document and one report per language, and the cache rule, are **[P]** and follow NF-P2-007 and NF-P2-012.

## Why two levels

The contract list page only needs a title, a score and a status. A full report (transcription, clauses, translation, complaint letter) can be tens of kilobytes. Reading it for every row of a list would waste reads and slow the page. So:

```
users/{uid}/contracts/{contractId}                     light: metadata, status, score, cache keys
users/{uid}/contracts/{contractId}/extraction/current  step 1's blocks and text (backend only)
users/{uid}/contracts/{contractId}/reports/{lang}      heavy: the full report in one language
```

The uploaded file itself is **not kept** (NF-P2-007): step 1 reads it during the upload request and only its blocks and text are stored.

## `users/{uid}/contracts/{contractId}`

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | yes | `uploaded` (step 1 done), `processing` (steps 2 to 6 running), `completed`, `failed` |
| `step` | string | while processing | The step running now: `detect`, `law`, `compare`, `complaint`, `translate`. The app watches it to show progress (NF-P2-010). Removed when the run ends |
| `title` | string or null | yes | Document title from step 1 |
| `legibility` | string | yes | `good`, `partial`, `poor` (step 1). `poor` stops the analysis with `poor_legibility` |
| `filename` | string | no | Name sent by the client |
| `mime_type` | string | yes | Detected from the file bytes (`application/pdf`, `image/jpeg`, ...) |
| `size_bytes` | number | yes | |
| `page_count` | number | no | From the extraction step (`ExtractedContract.page_count`, NF-P2-001) |
| `storage_path` | string | no | Not written: the file is not kept (NF-P2-007). Reserved in case a later task keeps it |
| `content_hash` | string | yes | SHA-256 (hex) of the file bytes. Part of the cache key. |
| `detected` | map | after step 2 | `language` (ISO 639-1), `host_country` (`SG`, `KR`, `MY`, `JP`, `HK`, `AU`), `document_kind` (`employment_contract`, `recruitment_agreement`, `loan_agreement`, `other`), `job_type` (as `users.job_type`). Any key may be null: `host_country` is null for a contract from another country or one that shows none (NF-P2-002) |
| `extracted` | map | after step 2 | `employer_name`, `agency_name`, `salary_amount`, `salary_currency`, `salary_period` (`month`, `week`, `day`, `hour`). Any key may be absent (NF-P2-002). Feeds Radar (NF-P2-021) and Financial Identity (NF-P3-024). |
| `host_country`, `job_type` | string | after step 2 | What the analysis used after the fallbacks: the worker's choice, else `detected`, else the profile (NF-P2-007, D-55) |
| `health_score` | number | when completed | 0 to 100, where 100 is safest (`risk_scorer.py`, NF-P2-004) |
| `risk_level` | string | when completed | `safe`, `caution`, `danger` (the design doc's Safe / Caution / Danger) |
| `clause_counts` | map | when completed | `{ "safe": 9, "caution": 3, "danger": 1 }` |
| `report_languages` | array of string | when completed | Languages that already have a `reports/{lang}` document, alphabetically sorted (not source-language-first; found by NF-P2-008 while testing a worker whose language sorts before "en") |
| `law_version` | number | when completed | `labor_laws/{country}/_meta/current.version` used for the analysis |
| `prompt_versions` | map | yes | Prompt file versions used. After upload only `contract.extract`; after analysis all five, for example `{ "contract.extract": 2, "contract.detect": 2, "contract.compare": 1, "contract.translate": 1, "contract.complaint": 2 }` |
| `models` | map | when completed | Model per tier, for example `{ "reasoning": "gemini-3.5-flash" }` (ADR-002) |
| `complaint_pending` | boolean | no | `true` when the complaint letter failed for a passing reason (Gemini overloaded, timeout, bad answer, or the host country's template not loaded in that Firestore); the next analyze writes only the letter. Absent otherwise. A stored analysis with a `danger` clause, no letter and no flag (analysed before 2026-10-01) is treated the same |
| `error` | map | when failed | `{ "step": "compare", "code": "gemini_unavailable" }`. Codes: `poor_legibility`, `country_unknown`, `not_employment_contract`, `no_law_data`, `no_terms`, `gemini_busy`, `gemini_unavailable`, `gemini_timeout`, `gemini_bad_answer`, `internal`. No stack traces. |
| `created_at`, `updated_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Example** — `users/uid_priya_demo/contracts/c_01`

```json
{
  "status": "completed",
  "filename": "sg_domestic_worker.pdf",
  "mime_type": "application/pdf",
  "size_bytes": 218450,
  "page_count": 4,
  "title": "EMPLOYMENT CONTRACT",
  "legibility": "good",
  "content_hash": "9f2c1b7e4d0a8c53e6b1f9a2d4c7e8b0a1f3d5c6b7e9a0c2d4f6e8a1b3c5d7e9",
  "detected": { "language": "en", "host_country": "SG", "document_kind": "employment_contract", "job_type": "domestic_worker" },
  "extracted": { "employer_name": "Example Household", "salary_amount": 650, "salary_currency": "SGD", "salary_period": "month" },
  "host_country": "SG",
  "job_type": "domestic_worker",
  "health_score": 58,
  "risk_level": "caution",
  "clause_counts": { "safe": 9, "caution": 3, "danger": 1 },
  "report_languages": ["en", "hi"],
  "law_version": 1,
  "prompt_versions": { "contract.extract": 2, "contract.detect": 2, "contract.compare": 1, "contract.translate": 1, "contract.complaint": 2 },
  "models": { "extraction": "gemini-3.5-flash-lite", "reasoning": "gemini-3.5-flash", "classification": "gemini-3.1-flash-lite" },
  "created_at": "2026-09-26T10:00:00Z",
  "updated_at": "2026-09-26T10:01:12Z",
  "schema_version": 1
}
```

**Access:** owner reads; only the backend writes.

## `users/{uid}/contracts/{contractId}/extraction/current`

What step 1 read from the file, kept so the analysis can run without the file (NF-P2-007).

| Field | Type | Required | Description |
|---|---|---|---|
| `blocks` | array of map | yes | Step 1's blocks: `page`, `kind`, `number`, `text` (NF-P2-001) |
| `text` | string | yes | The whole contract text built from the blocks |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Access:** backend only. The security rules deny every subcollection they do not name, so even the owner cannot read it (a rules test checks this); the owner sees the same text as `full_text` in each report.

## `users/{uid}/contracts/{contractId}/reports/{language}`

The document id is the language code. `reports/en` is the report the analysis writes (`is_source: true`): the comparison works in English. Every other language is a translation of it, made once, when the worker's language is not English or they switch language (NF-P2-012).

| Field | Type | Required | Description |
|---|---|---|---|
| `language` | string | yes | Same as the document id |
| `is_source` | boolean | yes | `true` for `reports/en`, the report the analysis wrote; `false` for a translation |
| `full_text` | string | yes | The whole contract text: the transcription in the contract's own language for `en`, its translation otherwise |
| `summary` | string | yes | Short plain-language summary for the report header |
| `clauses` | array of map | yes | One entry per clause, see below |
| `complaint` | map or null | yes | `null` when no violation was found. Otherwise `{ "template_type": "general", "authority_name": "...", "letter_text": "...", "letter_language": "en", "worker_copy": "..." or null, "authority_url": "..." or null, "channels": [...] }`. `letter_text` is in the authority's language; `worker_copy` is the same letter in `worker_language`, the language of the analysis that wrote it (null when that is the letter language). A report translated later carries the letter unchanged (NF-P2-006, NF-P2-007) |
| `content_hash` | string | yes | Copy of the contract's hash when this report was made |
| `law_version` | number | yes | Labor-law version used |
| `prompt_versions` | map | yes | As on the contract |
| `models` | map | yes | Model used per tier, for example `{ "reasoning": "gemini-3.5-flash" }` (ADR-002) |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

A clause map has: `index` (number, reading order), `number` and `page` (of the clause's first block), `block_ids` (its blocks in `extraction/current`, 1-based), `text` (the clause in this language), `category` (a labor-law category id from [labor_laws](labor_laws.md), or `other`), `risk` (`safe`, `caution`, `danger`, shown as the green, yellow and red flags), `law_reference` (string or null), `explanation` (why, in plain words) and `recommendation` (string or null).

A report stays well below the 1 MiB document limit for a normal contract (30 clauses at about 1 KB each plus the text).

**Example** — `users/uid_priya_demo/contracts/c_01/reports/en` (one clause shown)

```json
{
  "language": "en",
  "is_source": true,
  "full_text": "EMPLOYMENT CONTRACT ...",
  "summary": "Most terms are fine. One clause allows deductions that the law does not.",
  "clauses": [
    {
      "index": 7,
      "text": "The employer may deduct the cost of recruitment from wages.",
      "category": "salary_deductions",
      "risk": "danger",
      "law_reference": null,
      "explanation": "Deductions for recruitment costs are restricted.",
      "recommendation": "Ask for this clause to be removed."
    }
  ],
  "complaint": null,
  "content_hash": "9f2c1b7e4d0a8c53e6b1f9a2d4c7e8b0a1f3d5c6b7e9a0c2d4f6e8a1b3c5d7e9",
  "law_version": 1,
  "prompt_versions": { "contract.extract": 1, "contract.compare": 1 },
  "models": { "reasoning": "gemini-3.5-flash" },
  "created_at": "2026-09-26T10:01:10Z",
  "schema_version": 1
}
```

**Example values are illustrative.** The wording of the clause and the law reference are placeholders, not curated law.

**Access:** owner reads; only the backend writes.

### The response cache (NF-P2-007, NF-P2-012)

There is no separate cache collection: the contract and report documents are the cache entries (implemented in `services/contract/upload.py` and `report_store.py`). The backend serves a stored report without calling Gemini when **all** of these match:

1. the requested `language` is the document id,
2. the report's `content_hash` equals the contract's `content_hash`,
3. the report's `law_version` equals the current `labor_laws/{country}/_meta/current.version`,
4. the report's `prompt_versions` equal the prompt versions the code uses now.

Otherwise it makes a new report and overwrites the document. Switching the report language (NF-P2-012) reads or creates `reports/{lang}` and adds the language to `report_languages`.

As built (NF-P2-007):

- **Upload:** the same file (same `content_hash`) from the same user returns the stored contract without calling Gemini, unless it was read with an older `contract.extract` prompt; then it is read again into the same contract.
- **Analyze:** a contract whose `law_version` and `prompt_versions` still match, and whose `reports/en` is current, is served as it is (`cached: true`); a missing language is translated and stored. A different country or job chosen by the worker runs the analysis again.
- **A pending letter** (`complaint_pending`) is written on the next analyze, without re-running the rest, and added to every stored report.

The cache is per user on purpose. Serving one worker's contract analysis to another worker with the same file would leak the fact that they hold that contract.

## `complaint_templates/{country}/types/{type}`

Reference data: who to complain to, and the fixed frame of the letter. The pipeline (NF-P2-006) fills it in with the details from the analysis.

`complaint_templates/{country}` is a small header document: `{ "country": "SG", "updated_at": ... }`. The `type` id is a labor-law category id (for example `salary_deductions`, `recruitment_fees`, `passport_retention`).

| Field | Type | Required | Description |
|---|---|---|---|
| `country` | string | yes | ISO-2 host country |
| `type` | string | yes | Category id, same as the document id |
| `authority_name` | string | yes | The labor authority the letter is addressed to |
| `authority_url` | string | no | Official page for filing |
| `channels` | array of map | no | Ways to file: `{ "kind": "web" or "email" or "phone" or "post", "value": "..." }` |
| `letter_language` | string | yes | Language the authority works in |
| `template_text` | string | yes | Letter frame with `{{placeholder}}` markers |
| `placeholders` | array of string | yes | The markers used, for example `["employer_name", "worker_name", "violation_summary"]` |
| `reviewed_on` | string (date) | yes | When someone last checked the authority details |
| `schema_version` | number | yes | `1` |

The authority names and addresses must come from official sources when NF-P2-006 loads them. None are recorded in this document.

**Example** — `complaint_templates/SG/types/salary_deductions`. **The names and text are placeholders, not a real authority.**

```json
{
  "country": "SG",
  "type": "salary_deductions",
  "authority_name": "Example Labour Authority",
  "authority_url": "https://example.org/file-a-complaint",
  "channels": [{ "kind": "web", "value": "https://example.org/file-a-complaint" }],
  "letter_language": "en",
  "template_text": "To {{authority_name}}: I, {{worker_name}}, wish to report {{violation_summary}} by {{employer_name}}.",
  "placeholders": ["authority_name", "worker_name", "violation_summary", "employer_name"],
  "reviewed_on": "2026-09-27",
  "schema_version": 1
}
```

**Access:** read by signed-in users; only the data scripts and the backend write.

**Tasks that use it:** NF-P2-001 to NF-P2-007 (pipeline and cache), NF-P2-011 to NF-P2-013 (report UI), NF-P2-021 (radar signal), NF-P3-023 (radar warning on the report), NF-P3-024 (income from contract).
