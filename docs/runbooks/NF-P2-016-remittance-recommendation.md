# NF-P2-016 — Remittance X-Ray: Gemini Recommendation

## Summary

`POST /api/v1/remittance/recommend` takes a finished comparison (the unmodified body of `POST /remittance/compare`, and optionally `GET /remittance/trends`) and writes a short, personal recommendation directly in the worker's own language: one headline and two to four sentences, plus a timing tip when a best day to send exists. Step 9 of the Remittance X-Ray pipeline, classification tier (`gemini-3.1-flash-lite`, prompt `remittance/recommend.v1`) — the only remittance step that calls Gemini, and on a separate quota bucket from Contract Shield's reasoning tier (ADR-002).

The recommended provider is never a name Gemini chose. `recommended_rpw_id` and `recommended_firm` are always the comparison's own top-ranked comparable provider (`summary.best_rpw_id` / `best_firm`, already computed by step 6); Gemini's own `best_provider` field is only checked against them, and a mismatch is a `502`. There is no radar-flag data yet (NF-P3-022) that would make picking a different provider correct.

No new package, no shared file changed.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/remittance_recommend.py` (new) | `RemittanceRecommendRequest`, `RecommendationAnswer` (Gemini schema), `RemittanceRecommendation` |
| `backend/app/services/remittance/recommender.py` (was a stub) | `generate_recommendation()`, `_comparison_json()`, `_check_answer()`, `_timing_tip()`, `RecommendationIncompleteError` |
| `backend/app/api/v1/remittance.py` | `POST /api/v1/remittance/recommend` |
| `backend/app/prompts/remittance/recommend.v1.yaml` | One rule added: never write the data's own field names (`fx_margin_pct`, ...), always describe a fee or rate markup in plain words (see decision 4) |
| `backend/tests/unit/services/test_remittance_recommender.py` (new) | 13 tests |
| `backend/tests/integration/api/test_remittance_recommend.py` (new) | 14 tests |
| `backend/tests/integration/api/test_remittance_recommend_live.py` (new) | Opt-in live test, 3 calls (`RUN_LIVE_GEMINI=1`) |
| `docs/api/endpoints.md` | Endpoint; step 9 marked built, with the recommended-provider and timing-tip guards documented |

`requirements*.txt`, `pyproject.toml`, `Dockerfile`, the workflows and `firestore.rules` are unchanged. `remittance/recommend.v1.yaml` was written by NF-P1-029 and edited here: the prompts README says a `.v1` file may still be edited while its owning step is being built, since no stored result depends on it yet.

## Decisions

1. **The recommended provider is set by code, never trusted from Gemini.** `recommended_rpw_id` / `recommended_firm` are always `comparison.summary.best_rpw_id` / `best_firm`. The prompt still asks for `best_provider` (forward-compatible with a future radar-flag override, NF-P3-022), but today any name other than the top-ranked one is a wrong answer, not a legitimate choice, so a mismatch is `RecommendationIncompleteError` (502), not silently corrected. Case and surrounding space are ignored in the comparison (`"  instarem  "` matches `"InstaReM"`), but the response always carries the comparison's own casing.
2. **`timing_tip` is forced to `null` whenever `trend` is missing or has no `best_day`**, whatever text Gemini wrote. A live check found the model happily invents a plausible-sounding tip ("Send on Fridays...") when given no trend data at all; the same reasoning as never trusting `law_reference`/`category` elsewhere in this codebase applies to a fact the model was never given data to compute.
3. **Only what the prompt names is sent to the model**, trimmed by `_comparison_json()`: the amount and corridor, the ranked comparable providers (rank, firm, fee, margin, total cost, recipient receives, speed), the summary numbers, and `best_day` when a trend was given. Not sent: `note`, `network_coverage`, the survey block, the exact live rate, and every non-comparable provider — smaller prompt, and nothing the prompt asks the model to mention.
4. **A prompt rule added after a live check.** The first live run (see "Verified results") had the model write `"...dahil sa mataas na fx_margin_pct ng Maybank"` in a Tagalog explanation: it copied the JSON field name instead of describing the rate markup in words. Added one rule to `recommend.v1`'s system prompt and reran the live test: all three languages then described the cost in plain words. Recorded here because it was fixed before this task closed.
5. **`comparison` is the request body, not a re-fetch.** The endpoint takes what the worker's own `/compare` call already returned, the same pattern as Contract Shield's translate and complaint steps taking the prior step's output. No Firestore read, no repository.
6. **`trend` is optional and separate from `comparison`.** Steps 4/7 (NF-P2-015) and step 9 are independent Firestore reads and Gemini calls; a slow or missing trend never blocks the recommendation.
7. **Bounded and validated at the request boundary.** `MAX_PROVIDERS = 60` (a real corridor has at most 44) and a check that at least one provider has `rank == 1`, both as pydantic field validators, so a malformed body is a plain 422 before any Gemini call — same pattern as `MAX_CLAUSES`/`MAX_BLOCKS` elsewhere.
8. **A closing tag inside a firm name is neutralised** before it reaches the prompt's `<comparison>` section, the same defensive pattern as every step that sends structured text inside a named block, even though corridor firm names are curated reference data, not worker-supplied text.
9. **No dedicated timeout setting.** The output is four short fields on the fast classification tier; live calls took 1.5 to 3.9 s. `GEMINI_TIMEOUT_SECONDS` (30 s default) is used as is.

## Flow

```
POST /api/v1/remittance/recommend
  {comparison, trend?, target_language}
  auth (401), body checked: comparison has a rank-1 provider, ≤60 providers, valid language (422)
  generate_recommendation(comparison, trend, target_language, gemini)   [services/remittance/recommender.py]
    └─ _comparison_json(): amount/corridor, ranked comparable providers, summary, best_day if trend given
    └─ GeminiClient.generate_structured(
         operation="remittance.recommend", tier=CLASSIFICATION,
         system=recommend.v1 system, contents=recommend.v1 user with the data inside <comparison>,
         response_model=RecommendationAnswer)                3 attempts on timeout/503/429
    └─ _check_answer(): headline/explanation non-empty; best_provider matches summary.best_firm
                                                               → mismatch or empty → RecommendationIncompleteError
    └─ _timing_tip(): null unless trend.best_day was given
  200 {corridor_id, target_language, recommended_rpw_id, recommended_firm, headline, explanation, timing_tip}
```

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

As CI runs it:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/nonexistent python -m pytest -q
docker build --platform linux/amd64 -t nomadfinance-backend:ci .
```

### 2. Live test (3 calls, classification tier)

```bash
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_remittance_recommend_live.py -v -s
```

### 3. Try the endpoint by hand

Start the API, get a Firebase ID token as in the NF-P2-001 runbook, call `/remittance/compare` for a corridor and amount, then send its response as `comparison` (optionally with a `/remittance/trends` response as `trend`) to the example in `docs/api/endpoints.md`.

## Verified results (2026-09-30)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy app`, `mypy app tests` | Pass |
| `pytest -q`, with and without Google credentials | 562 passed, 47 skipped (opt-in live and emulator tests) |
| New tests | 13 service, 14 endpoint |
| Mutation check | Two safety-critical guards (the provider-name match, the timing-tip null-forcing) each deliberately broken and each caught by the tests; the service file was restored byte-for-byte afterwards |
| `docker build --platform linux/amd64 -t nomadfinance-backend:ci .` | **Not run**: the Docker daemon was not running on this machine this time. `Dockerfile` and `requirements.txt` are unchanged; NF-P2-014 already built and smoke-tested an image from the same `Dockerfile` |
| **Live Gemini test, first run** | 3 passed (SG-PH in `hi` with a trend, `ne` and `tl` without one), 1.5 to 3.9 s each. All three correctly recommended InstaReM (the top-ranked provider); the Hindi and English-currency numbers matched the comparison exactly; the Nepali and Tagalog `timing_tip` were correctly `null`. **But** the Tagalog explanation wrote the raw field name `fx_margin_pct` instead of describing it in words |
| Prompt fix, then **live Gemini test, second run** | 3 more passed, same three languages. All three now describe the cost in plain words (for example "mas mataas na exchange rate markup ng Maybank", "खराब विनिमय दर") and never a field name. 6 live calls total, both runs |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| 502 `The AI service returned an unusable answer` | Either the answer had no headline/explanation, or it named a provider other than `comparison.summary.best_firm`. Retry; a repeated mismatch on the same input would mean the prompt needs a `.v2` |
| `timing_tip` is always `null` | Send `trend`, the response of `/remittance/trends`, and check its `best_day` is not `null` (`best_day_reason` explains why) |
| The explanation mentions a field name (`fx_margin_pct`, `total_cost_pct`) | Should not happen after the fix in `recommend.v1`; if it recurs, that is a `.v2` change, tracked as its own finding, not silently patched again |
| 422 `comparison has no ranked provider to recommend` | The `comparison` sent is not a real `/compare` response, or every provider in it is non-comparable |
| A country's corridor never gets a timing tip | AU-IN and MY-ID are the only corridors with a clear best day today (see the trends runbook); this is expected, not a bug |

## Definition of Done (Gemini Pipeline Step)

- [x] Correct model tier: classification (`gemini-3.1-flash-lite`, ADR-002)
- [x] Structured output via Pydantic `response_schema` (`RecommendationAnswer`), no free-text parsing
- [x] Retry logic via tenacity (unchanged; 3 attempts on timeout, 503, 429)
- [x] Timeout set (default 30 s; not dedicated, see decision 9)
- [x] Token usage logged (`gemini_call operation=remittance.recommend ...`, automatic in the client)
- [x] Prompt in a versioned file (`remittance/recommend.v1.yaml`, edited here per decision 4)
- [x] Tested with 3+ diverse inputs: three languages, with and without trend data, a mismatched provider, an empty answer, a hallucinated timing tip, a prompt-injection attempt inside a firm name — against a fake client, and 6 calls against real Gemini

Backend endpoint items:

- [x] Pydantic request and response models
- [x] Firebase token check (401 without it)
- [x] Structured request logging: from NF-P1-028, automatic
- [x] Specific error codes (401, 422, 429, 502, 503, 504)
- [x] AI rate limit applied (`limit_ai_calls`)
- [x] `docs/api/endpoints.md` updated
- [ ] Manual Swagger try-out with a real token: yours

## Commit and PR for this task

Branch: `feature/remittance-recommend` (already checked out).

```bash
git commit -m "feat(remittance): write a personal recommendation from a finished comparison" -m "Refs: NF-P2-016"
```

PR title: `feat(remittance): personal recommendation in the worker's language (NF-P2-016)`

## For teammates

- **Aditya (NF-P2-017, transfer log):** a logged transfer is keyed by `rpw_id`, the same as the comparison; the recommendation is not stored and does not need to be logged.
- **Devam (NF-P2-022, savings):** the recommendation does not use the savings figure yet (that step is not built); `recommend.v1`'s `variables` are unchanged, so a savings field can be added to `_comparison_json()` without a prompt version bump if the prompt's own wording doesn't need to change.
- **Aditya / whoever builds NF-P2-019 or a recommendation card:** call `/compare` (and `/trends` if you have it), then `/recommend` with both bodies unmodified. Show `headline` first, `explanation` under it, `timing_tip` only when not null.
- **NF-P3-022 (radar flags) owner:** when `ProviderResult` gains a `flagged` field, `_check_answer()`'s exact match against `summary.best_firm` has to become a lookup permitting the second-ranked provider when the top one is flagged; `recommend.v1`'s own instruction for that case is already written and untested against real flagged data.

## Not covered here

- Historical savings (NF-P2-022), transfer logging (NF-P2-017), the corridor comparison table and any recommendation card in the UI (NF-P2-019)
- Radar flags changing which provider is recommended (NF-P3-022)
- `docker build`: not run this time (daemon not running); see NF-P2-014's runbook for the last successful run
