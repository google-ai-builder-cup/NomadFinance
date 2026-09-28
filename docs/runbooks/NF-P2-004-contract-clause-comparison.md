# NF-P2-004 — Contract Shield: Clause Comparison

## Summary

Step 4 of Contract Shield, the core reasoning step. It checks every term of a contract against the host country's curated labor-law rules and gives each term a risk:
- 🟢 `safe`
- 🟡 `caution`
- 🔴 `danger`

Each term also gets a plain-English explanation, a recommendation, and the law it rests on. Code then computes the report's `health_score`, `risk_level` and `clause_counts`.

**How it works.** The model reads the numbered **blocks** from step 1 and the rules of step 3 (only the variant for the worker's job type). It answers with block ids, not copied clause text, which keeps its output small and gives the report the contract's exact words, pages and clause numbers.

**What code enforces, whatever the model says:**
- **Law references come only from the curated data.** Each is the rule's reference whose law matches the variant that was applied, for example the Work Passes Regulations for a domestic worker in Singapore, not the Employment Act that doesn't cover her.
- **"Danger" needs a rule that regulates the matter.** Without one, the model can only raise "caution".
- **Unknown or repeated block ids are dropped**, and skipped terms are reported.

**The score.** The worst risk sets the band, so one illegal term makes a contract "danger".

**Scope.** Loan agreements and other documents are refused (422), as step 2's hand-off note asked. `POST /api/v1/contracts/compare` exposes the step like the other steps' endpoints.

**Live results.** The comparisons take 20 to 38 s:
- **Malaysian contract (Indonesian text):** the four violations were caught.
- **Fair Singapore contract:** no danger; its two cautions are real gaps.
- **Singapore sample:** "danger" on its rest-day clause. Its passport clause got **caution, not danger**, correctly: the curated SG rule says it doesn't cover the passport itself (D-57).

The reasoning model was often overloaded (503), and the day's free-tier quota ran out (429) before the final live run could finish (D-58).

## Files

| File | Change |
|---|---|
| `backend/app/prompts/contract/compare.v1.yaml` | Reworked before first use: input is numbered blocks (not raw text), output is block ids + category + risk + texts; no citations from the model |
| `backend/app/schemas/contract_compare.py` (new) | `TermAssessment`, `ComparisonAnswer` (Gemini schema), `ContractCompareRequest`, `ComparedClause`, `ClauseCounts`, `ContractComparison` |
| `backend/app/services/contract/comparator.py` | `compare_contract()`, `render_blocks()`, `build_clauses()` (checks and reference choice), `COMPARE_PROMPT` for `prompt_versions` |
| `backend/app/services/contract/risk_scorer.py` | `score_contract()`: health score, risk level, counts |
| `backend/app/api/v1/contracts.py` | `POST /api/v1/contracts/compare` |
| `backend/app/config.py`, `backend/.env.example` | `GEMINI_COMPARE_TIMEOUT_SECONDS` (default 90) |
| `backend/tests/unit/services/test_contract_comparator.py`, `test_risk_scorer.py` | 23 unit tests |
| `backend/tests/integration/api/test_contracts_compare.py` | 13 endpoint tests |
| `backend/tests/integration/api/test_contracts_compare_live.py` | Real Gemini, rules from the curated files (no Firestore): SG sample, MY-ID photo, fair SG contract |
| `backend/tests/fixtures/contracts/*.blocks.json` | Blocks of the two samples (from step 1, live) and a hand-written fair SG contract |
| `docs/api/endpoints.md`, `docs/pipelines/contract-shield.md`, `docs/deferred-items.md` | Endpoint, step 4, D-08/D-09 updated, D-57, D-58 new |

## Decisions

1. **Blocks, not re-split text.** The model points at block ids, so its output is only the judgement: about 600 to 1,000 output tokens for 8 to 11 terms.
2. **References attached by code, from the applied variant.** On the real data, 47 of 90 rules have several references for different worker groups, so "first reference" would often cite the wrong law. The pick is the reference whose law name shares the most words with the applied variant's requirements.
3. **Danger needs a regulating rule.** On `not_regulated` or `unclear` coverage, on `other`, or on a category the country lacks, danger becomes caution. The model can't make something "illegal" that our law data doesn't say is.
4. **Health score bands:**

   | Contract has | Score | Level |
   |---|---|---|
   | Any danger | 49, minus 10 per further danger and 2 per caution (at least 0) | danger |
   | Caution only | 79, minus 3 per further caution (at least 50) | caution |
   | Nothing flagged | 100 | safe |

5. **Only employment contracts and recruitment agreements are checked.**
6. **Timeout 90 s per attempt.** Measured 20 to 38 s, with 3.6k to 4.8k thinking tokens. No thinking budget: the quality is right and the time is acceptable. `gemini-3.8-flash` is still 503 on the free tier (D-09).
7. **English explanations.** Step 5 translates; the clause `text` stays in the contract's language.

## Flow

```
POST /api/v1/contracts/compare {blocks, host_country, job_type, document_kind}
  body checks: 1..1000 blocks, ≤ 200,000 chars, known country / job type      (422)
  get_labor_law_context(host_country, job_type)   [step 3, Firestore]         (404)
  compare_contract(blocks, law, gemini, document_kind)
    ├─ loan_agreement / other                        → NotComparableError      (422)
    ├─ Gemini reasoning tier, compare.v1, timeout 90 s, up to 3 attempts
    │    contents: "a domestic worker working in Singapore" + rules JSON + numbered blocks
    ├─ build_clauses(): drop bad ids · danger→caution without a regulating rule ·
    │                   law_reference from the curated rule · reading order · unassessed ids
    ├─ no clause left                                → NoTermsError            (422)
    └─ score_contract(): health_score, risk_level, clause_counts
  200 ContractComparison
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

As on CI, without Google credentials (Git Bash):

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent CLOUDSDK_CONFIG=/tmp/empty APPDATA=/tmp/empty python -m pytest -q
```

### 2. Live tests (real Gemini; about 3 reasoning calls from the daily quota)

```bash
RUN_LIVE_GEMINI=1 python -m pytest tests/integration/api/test_contracts_compare_live.py -v -s
```

PowerShell:

```powershell
$env:RUN_LIVE_GEMINI = "1"; python -m pytest tests/integration/api/test_contracts_compare_live.py -v -s; Remove-Item Env:RUN_LIVE_GEMINI
```

- A 503 "temporarily unavailable" means the model is overloaded: run again later.
- A fast failure with "busy" is the daily quota (429): it resets at midnight Pacific time (12:30 IST).

### 3. Call the endpoint by hand

Start the server with `uvicorn app.main:app --host 127.0.0.1 --port 8080`. You need a Firebase ID token; from the running frontend's browser console: `await (await import("/src/lib/firebase.ts")).auth.currentUser.getIdToken()`.

bash:

```bash
python -c "import json; print(json.dumps({'blocks': json.load(open('tests/fixtures/contracts/sample_contract_my_id.blocks.json', encoding='utf-8')), 'host_country': 'MY', 'job_type': 'plantation_worker'}))" > body.json
curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data @body.json http://127.0.0.1:8080/api/v1/contracts/compare
```

PowerShell: build `body.json` with the same `python -c` line, then `curl.exe` with the same arguments (`$env:TOKEN`).

This reads the real `labor_laws/MY` from Firestore, so it needs your gcloud login.

## Verified results (2026-09-28)

| Check | Result |
|---|---|
| `pytest -q` | 306 passed, 17 skipped (all opt-in live tests) |
| The same without Google credentials (as CI) | 306 passed |
| `ruff check .`, `black --check .`, `mypy app tests` | Pass |
| Reference choice on the real curated data (offline) | SG domestic worker rest days → Work Passes Regulations 2012; SG factory worker rest days → Employment Act 1968; MY → Employment Act 1955 |

Live runs, reasoning tier `gemini-3.5-flash`, rules from the curated files:

| Contract | Result | Time, tokens |
|---|---|---|
| MY-ID photo, Indonesian (plantation worker) | score 19, **danger**: salary RM 1,500 below the RM 1,700 minimum; RM 300 a month agency-fee deduction; 60 hours a week; passport kept by the employer. All with the MY rule's reference; English explanations | 20.6 s |
| SG sample (domestic worker) | **danger**: 1 rest day a month where the rule requires one every 7 days. Passport clause **caution**: the curated SG rule names only the work permit and visit pass (D-57) | 32.0 to 33.7 s; 5.3k in, 0.6k out, 4.4k thinking |
| Fair SG contract (hand-written to meet the rules) | **no danger**; caution 73 to 76. Two real gaps: every rest day can be worked for pay (the rule keeps one real rest day a month), and no personal accident insurance | 33.0 to 38.3 s; 5.5k in, 1.0k out, 3.6k thinking |
| Long 24-term contract | 26.0 s, placeholder terms safe, the SGD 2,400 placement fee paid by the worker flagged | 26.0 s |

What changed after these runs, and what is still to re-run:
- The SG sample run found that the rest-day clause cited the Employment Act, which doesn't cover domestic workers. The reference choice (decision 2) was fixed after that and checked on the real data offline.
- The final live run then hit the free-tier quota (429, D-58). **After the quota resets, run step 2 once and record the three results here.**

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 503 "temporarily unavailable" | Reasoning model overloaded (very common on 2026-09-27/28); the client retried 3 times. Try again later |
| 503 "busy" within seconds | Daily free-tier quota used up (429 behind it, D-58). Resets at midnight Pacific time |
| 504 | Every attempt took over 90 s. Very long contract, or Gemini hanging; try again |
| A clause you expected as danger comes back as caution | Check the curated rule: `coverage` and `notes`. If the rule doesn't regulate it, caution is correct (example: SG passport, D-57) |
| `unassessed_block_ids` not empty | The model skipped terms; the log line `compare_unassessed_blocks` has the ids. Re-run; keep the contract for NF-P2-008 if it repeats |
| Wrong `law_reference` | The applied variant's requirements don't name their law clearly; fix the curated text (NF-P1-017) rather than the code |
| 422 "covers employment contracts" | `document_kind` from step 2 is `loan_agreement` or `other` |
| 404 | No curated labor law for the country in Firestore (NF-P1-018) |

## Definition of Done (Gemini Pipeline Step)

- [x] Correct model tier: reasoning (`gemini-3.5-flash`, ADR-002)
- [x] Structured output via Pydantic `response_schema` (`ComparisonAnswer`), no free-text parsing
- [x] Retry logic via tenacity (unchanged)
- [x] Timeout set: 90 s per attempt, from measurements (`GEMINI_COMPARE_TIMEOUT_SECONDS`)
- [x] Token usage logged (`gemini_call operation=contract.compare ... thinking_tokens`)
- [x] Prompt in a versioned file (`contract/compare.v1.yaml`)
- [x] Tested with 3+ diverse inputs. Non-English (Indonesian, Malaysian law), a fair contract, a long contract (25 terms), and a Singapore contract with violations: all run live on the comparison logic. The final full re-run after the reference fix is pending the quota reset (see Verified results)

## For teammates

- **Nobody** needs a new package or a `.env.local` change. `GEMINI_COMPARE_TIMEOUT_SECONDS` is optional, default 90.
- **Aditya (NF-P2-005, translation):** translate `summary` and each clause's `text`, `explanation` and `recommendation`; keep `category`, `risk`, `law_reference`, numbers and `index`.
- **Pranjal (NF-P2-006, complaint):** the clauses with `risk == "danger"` are the violations; each has `category` (the complaint template type) and `law_reference`.
- **Aditya (NF-P2-011, report UI):**
  - `risk` maps to 🟢🟡🔴.
  - `page` and `number` point into the contract.
  - `health_score` and `risk_level` go in the header.
  - `law_reference` can be null: show "no specific rule found", not "safe".
- **Curators (NF-P1-017):** D-57, the passport rules.
- **Everyone:** the reasoning model's free-tier quota is shared and small (D-58). Use the live tests sparingly.

## Commit and PR for this task

Branch: `feature/contract-clause-compare` (already checked out).

```bash
git add backend docs
git status
```

```bash
git commit -m "feat(contracts): compare contract terms with labor law and score risk" -m "Refs: NF-P2-004"
```

PR title: `feat(contracts): clause-by-clause labor-law comparison with health score (NF-P2-004)`

## Not covered here

- Translation (NF-P2-005), complaint letter (NF-P2-006), storing and caching reports (NF-P2-007, D-53), report UI (NF-P2-011)
- Curating the SG passport rule (D-57); a paid Gemini key (D-58)
