# contracts

Shape sources: the contract path is **[D]**. The pipeline steps that decide the fields are in the design doc (Contract Shield pipeline) and NF-P2-001 to NF-P2-007 **[T]**. The split into a light contract document and one report per language, and the cache rule, are **[P]** and follow NF-P2-007 and NF-P2-012.

## Why two levels

The contract list page only needs a title, a score and a status. A full report (transcription, clauses, translation, complaint letter) can be tens of kilobytes. Reading it for every row of a list would waste reads and slow the page. So:

```
users/{uid}/contracts/{contractId}                  light: metadata, status, score, cache keys
users/{uid}/contracts/{contractId}/reports/{lang}   heavy: the full report in one language
```

## `users/{uid}/contracts/{contractId}`

| Field | Type | Required | Description |
|---|---|---|---|
| `status` | string | yes | `uploaded`, `processing`, `completed`, `failed` |
| `filename` | string | no | Name sent by the client |
| `mime_type` | string | yes | Detected from the file bytes (`application/pdf`, `image/jpeg`, ...) |
| `size_bytes` | number | yes | |
| `page_count` | number | no | From the extraction step (`ExtractedText.page_count`) |
| `storage_path` | string | no | Cloud Storage path of the uploaded file. Absent when the file was not kept. |
| `content_hash` | string | yes | SHA-256 (hex) of the file bytes. Part of the cache key. |
| `detected` | map | after step 2 | `language`, `host_country`, `contract_type` (NF-P2-002) |
| `extracted` | map | after analysis | `employer_name`, `agency_name`, `salary_amount`, `salary_currency`, `salary_period` (`month`, `week`, `hour`). Any key may be absent. Feeds Radar (NF-P2-021) and Financial Identity (NF-P3-024). |
| `health_score` | number | when completed | 0 to 100, where 100 is safest. How it is computed belongs to NF-P2-004. |
| `risk_level` | string | when completed | `safe`, `caution`, `danger` (the design doc's Safe / Caution / Danger) |
| `clause_counts` | map | when completed | `{ "safe": 9, "caution": 3, "danger": 1 }` |
| `report_languages` | array of string | when completed | Languages that already have a `reports/{lang}` document |
| `law_version` | number | when completed | `labor_laws/{country}/_meta/current.version` used for the analysis |
| `prompt_versions` | map | when completed | Prompt file versions used, for example `{ "contract.extract": 1, "contract.compare": 1 }` |
| `error` | map | when failed | `{ "step": "compare", "code": "gemini_unavailable" }`. No stack traces. |
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
  "storage_path": "contracts/uid_priya_demo/c_01/sg_domestic_worker.pdf",
  "content_hash": "9f2c1b7e4d0a8c53e6b1f9a2d4c7e8b0a1f3d5c6b7e9a0c2d4f6e8a1b3c5d7e9",
  "detected": { "language": "en", "host_country": "SG", "contract_type": "domestic_worker" },
  "extracted": { "employer_name": "Example Household", "salary_amount": 650, "salary_currency": "SGD", "salary_period": "month" },
  "health_score": 58,
  "risk_level": "caution",
  "clause_counts": { "safe": 9, "caution": 3, "danger": 1 },
  "report_languages": ["en", "hi"],
  "law_version": 1,
  "prompt_versions": { "contract.extract": 1, "contract.compare": 1 },
  "created_at": "2026-09-26T10:00:00Z",
  "updated_at": "2026-09-26T10:01:12Z",
  "schema_version": 1
}
```

**Access:** owner reads; only the backend writes.

## `users/{uid}/contracts/{contractId}/reports/{language}`

The document id is the language code. One document per language the user asked for. The document in the contract's own language (`is_source: true`) also holds the transcription.

| Field | Type | Required | Description |
|---|---|---|---|
| `language` | string | yes | Same as the document id |
| `is_source` | boolean | yes | `true` for the contract's original language |
| `full_text` | string | yes | The whole contract text in this language (the transcription for the source report, the translation otherwise) |
| `summary` | string | yes | Short plain-language summary for the report header |
| `clauses` | array of map | yes | One entry per clause, see below |
| `complaint` | map or null | yes | `null` when no violation was found. Otherwise `{ "template_type": "salary_deductions", "authority_name": "...", "letter_text": "..." }` |
| `content_hash` | string | yes | Copy of the contract's hash when this report was made |
| `law_version` | number | yes | Labor-law version used |
| `prompt_versions` | map | yes | As on the contract |
| `models` | map | yes | Model used per tier, for example `{ "reasoning": "gemini-3.5-flash" }` (ADR-002) |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

A clause map has: `index` (number, reading order), `text` (the clause in this language), `category` (a labor-law category id from [labor_laws](labor_laws.md), or `other`), `risk` (`safe`, `caution`, `danger`, shown as the green, yellow and red flags), `law_reference` (string or null), `explanation` (why, in plain words) and `recommendation` (string or null).

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

There is no separate cache collection. A report document is the cache entry. The backend serves a stored report without calling Gemini when **all** of these match:

1. the requested `language` is the document id,
2. the report's `content_hash` equals the contract's `content_hash`,
3. the report's `law_version` equals the current `labor_laws/{country}/_meta/current.version`,
4. the report's `prompt_versions` equal the prompt versions the code uses now.

Otherwise it makes a new report and overwrites the document. Switching the report language (NF-P2-012) reads or creates `reports/{lang}` and adds the language to `report_languages`.

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
