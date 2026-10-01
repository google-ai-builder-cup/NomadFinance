# Contract Shield pipeline

Turns an uploaded employment contract into a Contract Health Report in the worker's language, and a complaint letter when the law is broken. Design doc section 5.3; data model in `docs/data-model/collections/contracts.md`; prompts in `backend/app/prompts/contract/`.

Each step's owner adds its section below when the step is built.

## Steps

| # | Step | Task (owner) | Tier (ADR-002) | Prompt | Code | Status |
|---|---|---|---|---|---|---|
| 1 | Extract text and structure | NF-P2-001 (Devam) | extraction | `contract/extract.v2` | `services/contract/extractor.py` | Built |
| 2 | Detect language, host country, contract type, employer/salary | NF-P2-002 (Pranjal) | extraction | `contract/detect.v2` | `services/contract/detector.py` | Built |
| 3 | Fetch the host country's labor-law rules | NF-P2-003 (Aditya) | none (Firestore) | none | `services/contract/rag.py` | Built |
| 4 | Clause-by-clause comparison, risk per clause | NF-P2-004 (Devam) | reasoning | `contract/compare.v1` | `services/contract/comparator.py`, `risk_scorer.py` | Built |
| 5 | Translate the report into the worker's language | NF-P2-005 (Aditya) | classification | `contract/translate.v1` | `services/contract/translator.py` | Built |
| 6 | Complaint letter when violations are found | NF-P2-006 (Pranjal) | reasoning | `contract/complaint.v2` | `services/contract/complaint.py` | Built |
| - | Run the steps in order, store the contract and reports, cache by hash, law and prompt versions | NF-P2-007 (Devam) | none | none | `services/contract/upload.py`, `pipeline.py`, `report_store.py`, `letter.py` | Built |

The pipeline as a whole (D-53) was added to NF-P2-007 by team decision; see "The pipeline" at the end.

## Flow

```
upload (PDF or photo, ≤ 10 MB)
  1 extract_contract(bytes, mime_type)      → ExtractedContract (blocks, title, legibility) + text
       legibility "poor" → stop and ask for a clearer photo (the pipeline's choice)
  2 detect_contract(text)                   → language, host_country, document_kind, job_type, employer, salary
       host_country null → fall back to the worker's profile country, or ask (the pipeline's choice)
  3 rules(host_country)                     → labor_laws/{country}/rules + law_version
  4 compare(text or blocks, rules, job)     → clauses[] with risk, law_reference, explanation
       health score computed in code from the clause risks
  5 translate(report, user language)        → reports/{lang}
  6 complaint(danger clauses, template)     → letter for the authority + copy for the worker (only if violations)
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

## Step 2: detect language, country and kind (NF-P2-002)

`detect_contract(text, gemini)` in `backend/app/services/contract/detector.py`.

- **In:** the contract `text` from step 1, in its original language. It goes into the prompt inside `<contract_text>` tags; a closing tag inside the document is neutralised so the document cannot end that section early.
- **Gemini call:** extraction tier, prompt `contract/detect.v2` (key `contract.detect`, version 2), response schema `DetectedContract`, temperature 0 (a classification should give the same answer twice). Default 30 s timeout: the input is text and the output about 120 tokens.
- **Out:** `DetectedContract`:

| Field | Values | Note |
|---|---|---|
| `language` | ISO 639-1 code (`en`, `ms`, `ko`, ...) or null | Normalised: `EN`, `en-US`, `zh_CN` become `en`, `en`, `zh`; anything that is not two letters becomes null |
| `host_country` | `SG`, `KR`, `MY`, `JP`, `HK`, `AU` or null | Null for a contract from any other country or one that shows none. Never guessed |
| `host_country_evidence` | short text | What showed the country (a law, an address, a currency); empty when `host_country` is null |
| `document_kind` | `employment_contract`, `recruitment_agreement`, `loan_agreement`, `other` | Step 4 compares against labor law only for employment and recruitment documents |
| `job_type` | the seven onboarding job types | Judged by the duties, not the title; `other` when unclear |
| `employer_name`, `agency_name` | text (at most 200 characters) or null | As written |
| `salary_amount`, `salary_currency`, `salary_period` | number, ISO 4217 code, `month`/`week`/`day`/`hour`, or null | Basic pay only. An amount that is zero or negative drops all three; a malformed currency becomes null; the period is null when there is no amount |

- **Stored as:** `language`, `host_country`, `document_kind`, `job_type` go into the contract's `detected` map; the employer, agency and salary fields into `extracted` (`docs/data-model/collections/contracts.md`). Storing is the pipeline's job (D-53).
- **Errors:** Gemini failures raise `GeminiError` subclasses (503, 504, 502, 500). An unusable value never raises: it becomes null.
- **Time:** 1.4 to 2.0 s per call in live runs (about 580 to 730 prompt tokens, 75 to 135 output tokens).
- **Standalone endpoint:** `POST /api/v1/contracts/detect` (`docs/api/endpoints.md`).
- **For step 3 (Aditya):** read `host_country` (and `job_type` to choose the rules). When it is null there is nothing to look up: the pipeline decides between the profile country and asking the worker.

## Step 3: fetch the host country's labor law (NF-P2-003)

`get_labor_law_context(country, job_type, repo)` in `backend/app/services/contract/rag.py`, backed by `LaborLawRepository` (`backend/app/repositories/labor_law_repo.py`).

- **In:** `host_country` and `job_type` from step 2. `host_country` is a plain `HostCountryCode`, never `None`: this step does not decide what happens for a null country (D-55 is the pipeline owner's call), it just isn't called until one is chosen.
- **Firestore reads, no Gemini call:** `labor_laws/{country}/_meta/current.version` and the 15 documents under `labor_laws/{country}/rules`.
- **Out:** `LaborLawContext`: `country`, `job_type`, `law_version` (for the cache key, `docs/data-model/versioning.md`), and 15 `LaborLawRule`s. Each rule carries `applicable_variant` — the variant whose `applies_to` contains the given `job_type`, falling back to the `all` variant — plus the full `variants` list, `references`, `confidence` and `notes`. Step 4 should compare a contract against `applicable_variant.requirements`.
- **Errors:** `LaborLawNotFoundError` when the country has no curated data loaded yet (NF-P1-018 not run for it, or the version/rules are missing) — the endpoint answers 404.
- **Standalone endpoint:** `GET /api/v1/contracts/labor-law/{host_country}?job_type=...` (`docs/api/endpoints.md`).
- **For step 4 (Devam):** use `rules[i].applicable_variant` directly; no need to re-resolve `job_type` against `variants` yourself. Skip labor-law comparison entirely when `document_kind` is `loan_agreement` (that check stays in step 2's output, this step does not look at `document_kind`).

## Step 4: compare each term with the law (NF-P2-004)

`compare_contract(blocks, law, gemini, document_kind)` in `backend/app/services/contract/comparator.py`.

- **In:**
  - the `blocks` of step 1
  - the `LaborLawContext` of step 3
  - `document_kind` from step 2: only `employment_contract` and `recruitment_agreement` are checked, anything else raises `NotComparableError`
- **Gemini call:** reasoning tier, prompt `contract/compare.v1` (key `contract.compare`, version 1), response schema `ComparisonAnswer`, per-attempt timeout 90 s (`GEMINI_COMPARE_TIMEOUT_SECONDS`).
  - **Blocks** are sent as numbered lines, `[id] (kind number, page) text`. The model answers with block ids, so it never copies clause text.
  - **Rules** are sent as compact JSON: the job type's variant only, and no references.
- **Checked in code, whatever the model says:**
  - Block ids that don't exist, or were already used, are dropped.
  - A `danger` without a `regulated` or `partly_regulated` rule becomes `caution`.
  - `law_reference` is the curated reference whose law best matches the applied variant's requirements.
  - Term blocks (clause, list item, table) the model skipped are returned in `unassessed_block_ids` and logged by id.
- **Score (`risk_scorer.py`):** the worst risk sets the band. Danger 0–49, caution 50–79, safe 100; each further problem lowers the score inside the band.
- **Out:** `ContractComparison`:
  - `health_score`, `risk_level`, `clause_counts`, `summary`
  - `clauses[]`: `index`, `number`, `page`, exact `text`, `category`, `risk`, `law_reference`, `explanation`, `recommendation`, `block_ids`
  - `law_version`

  This is the clause map of `reports/{lang}` plus number, page and block ids.
- **Language:** explanations and the summary are English; step 5 translates. The clause `text` stays in the contract's language.
- **Time:** 20 to 38 s measured for 6 to 25 terms.
- **Errors:**
  - `NotComparableError` (422 at the endpoint)
  - `NoTermsError` when nothing could be assessed (422)
  - Gemini errors (503/504/502/500)
- **Standalone endpoint:** `POST /api/v1/contracts/compare` (`docs/api/endpoints.md`).
- **For step 5 (Aditya):** translate `summary` and each clause's `text`, `explanation` and `recommendation`, and keep `category`, `risk`, `law_reference` and numbers as they are.

## Step 5: translate the report (NF-P2-005)

`translate_report(full_text, summary, clauses, target_language, gemini)` in `backend/app/services/contract/translator.py`.

- **In:** `full_text` from step 1 (the source-language transcription), `summary` and `clauses` from step 4's `ContractComparison`, and `target_language` (one of the six UI languages: `en`, `hi`, `tl`, `id`, `ne`, `bn`).
- **Gemini call:** classification tier, prompt `contract/translate.v1` (key `contract.translate`, version 1), response schema `TranslationAnswer`. Only `index`, `category`, `risk`, `text`, `explanation` and `recommendation` of each clause go to the model, inside `<report>` tags; a closing tag inside a clause's text is neutralised the same way step 2 and step 4 neutralise theirs.
- **Never sent to the model, and never taken from its answer:** `law_reference`, `number`, `page` and `block_ids` are carried straight over from the source clauses. `category` and `risk` are round-tripped for the model's own bookkeeping but the merged result still takes them from the source, never the answer — they are the codes the UI keys its risk flags on, so a mistranslated word can never change one.
- **Out:** `ContractReportTranslation`: `language`, `full_text`, `summary`, `clauses` (each a `TranslatedClause`: `index`, `number`, `page`, `text`, `category`, `risk`, `law_reference`, `explanation`, `recommendation`, `block_ids`). This is the shape of `reports/{lang}` minus the storage-only fields (`content_hash`, `law_version`, `prompt_versions`, `models`, `created_at`, `schema_version`), which the pipeline (D-53) adds when it stores the report.
- **Errors:** `TranslationIncompleteError` when the answer leaves out a clause that was sent (the endpoint answers 502, same message as an unusable Gemini answer); Gemini failures raise `GeminiError` subclasses (503/504/502/500).
- **Time:** not yet measured live (classification tier, but the output is a whole report — comparable in size to extraction's output).
- **Standalone endpoint:** `POST /api/v1/contracts/translate` (`docs/api/endpoints.md`). Also meant for the report language switcher (NF-P2-012): call it again with a different `target_language` on the same `full_text`/`summary`/`clauses`.
- **For the pipeline owner (D-53):** this step is stateless like steps 1 to 4; storing `reports/{lang}` and filling in `content_hash`, `law_version`, `prompt_versions` and `models` is still unowned.

## Step 6: complaint letter (NF-P2-006)

`generate_complaint(host_country, clauses, facts, worker_language, repo, gemini)` in `backend/app/services/contract/complaint.py`.

- **In:** the host country (step 2), the `clauses` of step 4's `ContractComparison`, the employer, agency and salary read in step 2 (`ContractFacts`), and the worker's language. The English comparison is used as it is; step 5 is not needed first.
- **Violations:** the clauses with `risk == "danger"`, in index order. None: `NoViolationsError` (422 at the endpoint); the pipeline decides not to call this step and stores `complaint: null` (D-53).
- **Template:** `complaint_templates/{country}/types/general`, read through `ComplaintTemplateRepository`. Only `general` is curated (one template per country); it names the labor authority, the ways to reach it, the language it works in and the letter frame. No template loaded: `ComplaintTemplateNotFoundError` (404).
- **Gemini call:** reasoning tier, prompt `contract/complaint.v2` (key `contract.complaint`, version 2), response schema `ComplaintAnswer` (`letter_text`, `worker_copy`), per-attempt timeout 60 s (`GEMINI_COMPLAINT_TIMEOUT_SECONDS`). The template, the violations and the contract facts go in their own tags; a closing tag inside a clause or an employer name is neutralised.
- **Two languages:** `letter_text` is in the authority's language (`en`, `ko`, `ms` or `ja`) so it can be sent as it is; `worker_copy` is the same letter in the worker's language so they can read it. When the two are the same language `worker_copy` is `null`, whatever Gemini returned.
- **Blanks:** the worker's name, contact details and start date are `[bracketed blanks]` in both texts, in the same places, because none of them is known to the pipeline. The worker fills them in before sending.
- **Set by code, never taken from Gemini:** `authority_name`, `authority_url`, `channels`, `template_type`, `letter_language`, `violation_count`.
- **Checked in code:** an empty letter, a missing `worker_copy` (when the languages differ) or a `{{placeholder}}` of the template left in either text is `ComplaintIncompleteError` (502).
- **Out:** `ContractComplaint`. `template_type`, `authority_name` and `letter_text` are the `complaint` map of `reports/{lang}`; `worker_copy`, `channels` and `letter_language` extend it (`docs/data-model/collections/contracts.md`).
- **Errors:** `NoViolationsError` (422), `ComplaintTemplateNotFoundError` (404), `ComplaintIncompleteError` (502), Gemini errors (503/504/502/500).
- **Standalone endpoint:** `POST /api/v1/contracts/complaint` (`docs/api/endpoints.md`).
- **Data:** the six country files in `data-scripts/data/source/complaint-templates/`, checked by `python -m src.validators.complaint_template` and loaded by `python -m src.loaders.complaint_templates` (see the runbook).
- **For the report UI (Aditya, NF-P2-013):** show `worker_copy` (or `letter_text` when it is null) as the preview and `letter_text` for the PDF and the copy action; list `channels` under it as where to send it.
- **For the pipeline owner (D-53):** the letter is written in one call from the English comparison, so it is independent of the report language. Store the `complaint` map in the source-language report, and reuse it, with `worker_copy`, in the other languages of the same worker.

## The pipeline: upload, analyze, store (NF-P2-007)

Three endpoints run the steps above in order and store everything under `users/{uid}/contracts/{id}` (`docs/api/endpoints.md`, `docs/data-model/collections/contracts.md`).

```
POST /contracts (file)                              upload.py
  same user + same file hash + same extract prompt → return the stored contract, no Gemini
  else step 1 → store contract {status: uploaded, legibility, title, content_hash, ...}
            + extraction/current {blocks, text}      the file itself is not kept

POST /contracts/{id}/analyze (optional choices)      pipeline.py
  stored analysis still current (law_version, prompt_versions, reports/en)?  report_store.py
      → translate only a missing language, write only a pending letter → cached: true
  claim the contract (transaction; 409 if another request runs it, taken over after 16 min)
  step 2 detect      → country / job / language: choice > detected > profile (D-55)
  step 3 law         → labor_laws/{country}
  step 4 compare     → clauses, score
  step 6 complaint   → letter.py: only when a term is danger; a passing failure (Gemini, or the
                      template not loaded) = complaint_pending; the report page offers "Write the letter"
  store reports/en, then the analysis fields on the contract
  step 5 translate   → reports/{worker language} when it isn't English
  status completed; on any failure: status failed, error {step, code}, then the HTTP error

POST /contracts/{id}/reports/{language}              report_store.ensure_report
  stored and current → return it; else translate reports/en, store, return
```

- **Progress:** the contract's `step` changes as each step starts. The app shows it by listening to the document in Firestore (NF-P2-010), see below.
- **Cloud Run:** everything runs inside the request, because Cloud Run gives CPU only to open requests. The request timeout is 900 s (`scripts/deploy_manual.sh`); a normal analysis takes 30 s to 2 minutes.
- **Cache key:** `content_hash` + `law_version` + `prompt_versions`, and per report its language (`docs/data-model/versioning.md`). Per user on purpose: one worker's analysis is never served to another.
- **Account deletion** (NF-P1-023) already removes `users/{uid}` with all contracts, extractions and reports.

## How the app shows progress (NF-P2-010)

The upload page (`pages/contract/ContractUpload.tsx`) follows `users/{uid}/contracts/{id}` with `onSnapshot` from the moment the upload returns, and shows five steps with a report skeleton under them (`components/contract/PipelineProgress.tsx`, `ReportSkeleton.tsx`; the logic is in `utils/pipelineProgress.ts`).

| Screen step | While |
|---|---|
| 1 Reading your contract | the upload request runs (step 1, `extract`) |
| 2 Finding where you work | `detect`, and before this run's claim |
| 3 Looking up the labor law | `law` |
| 4 Checking every clause | `compare` |
| 5 Preparing your report | `complaint`, `translate` |

- **This run versus the last one.** A re-upload of the same file reuses the contract, so its document can still say `completed` or `failed` from last time. Until the page sees this run's `status: processing` (the claim), it shows step 2 running and ignores that old state. A cache hit never writes `processing`; its result comes from the HTTP answer.
- **Done** = the HTTP answer, or a `completed` document seen after this run's claim (the phone lost the answer).
- **Failed** = `error: {step, code}` on the document. The page shows a message per code and "Try again" (analyze again, no upload) unless the code is `poor_legibility`, `not_employment_contract`, `no_law_data` or `no_terms`. With no stored error (the upload failed, or the network), the HTTP status gives the message: 503 = AI busy, 504 = AI too slow. A failed upload goes back to the form with the file kept.
- **Slow step:** after 45 s on one step the page adds "Still working…" (D-54).

## How the app shows the report (NF-P2-011)

Once `status` is `completed`, the upload page (`ContractUpload.tsx`) reads the full report straight from Firestore — `users/{uid}/contracts/{id}/reports/{language}`, one `getDoc` (`useContractReport`, `contractService.getContractReport`) — rather than calling `POST .../reports/{language}`: the analyze request has already written that document before it answers, and `firestore.rules` already lets the owner read it (same pattern as `watchContractProgress` for the progress document). The standalone endpoint is for the language switcher (NF-P2-012, next section) translating into a language with no stored report yet.

`components/contract/ReportCard.tsx` renders the score header (score, risk badge, the three counts, the summary, the complaint-pending note) and, for every clause (`ClauseRow.tsx`), a 🟢🟡🔴 flag, its category, and the clause's exact words next to `law_reference` (or a fallback when there is none), the explanation and any recommendation — side by side from the `md:` breakpoint up, stacked with their own labels on a phone. Nothing here reads `radar_entities/` or renders `report.complaint`; those are NF-P3-023 and NF-P2-013.

## Switching the report language (NF-P2-012)

Above the report, `ReportLanguageSwitcher` lists the six languages by their own names. Choosing one changes only the report: neither the app language nor `users/{uid}.preferred_language` changes (D-40).

| Language | Where it comes from | Cost |
|---|---|---|
| In the analysis' `report_languages` | `reports/{language}` read from Firestore | One read |
| Not stored yet | `POST /api/v1/contracts/{id}/reports/{language}`: the backend translates the English report once and stores it | A few seconds, one Gemini call |
| Already seen in this visit | The app's cache | None |

While a new language loads, the previous language of the same contract stays on screen, dimmed, with a "Translating your report…" note, so the score does not vanish. A report of another contract is never shown in its place. On failure the page shows the message for the status (busy, too slow, offline, or "out of date, check your contract again" for a `409`), with Try again except for the `409`. The switcher stays usable, and going back to a language already seen is instant. The report block carries `lang`, so a screen reader speaks it in the report's language.

Code: `useContractReport(contractId, language, storedLanguages)` and `reportQueryOptions` in `hooks/useContract.ts`, `switchReportLanguage` in `services/contractService.ts`, `reportFailureKey` in `utils/reportLanguage.ts`.

## E2E testing (NF-P2-008)

The full pipeline was exercised for all 5 target countries (SG, AU, KR, MY, JP) against real Firestore-backed repositories and real curated data, with Gemini's answers scripted (no live-quota cost) — see `docs/runbooks/NF-P2-008-contract-e2e-testing.md`. It found and closed **D-60** (`report_languages` is alphabetically sorted, not source-first). The real-Gemini live pass for AU, KR, MY and JP is written and ready but blocked by D-58 (shared quota exhausted); SG's live path is already covered by NF-P2-007's own test.
