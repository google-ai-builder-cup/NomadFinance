# NF-FC-012 — Coach 90-day plan generator

## Summary

After the worker confirms their answers, `POST /api/v2/coach/sessions/{id}/plan` makes the 13-week plan and `GET /api/v2/coach/plans/{id}` reads it. The plan has a monthly budget, a remittance schedule with the cheapest provider from Remittance X-Ray, a debt paydown, an emergency-fund target, warnings, a checklist and the "not professional advice" note.

**Code makes every figure; the model only writes sentences.** The tracker asks for Gemini structured output with a validator that rejects any figure not derivable from the inputs. Here the figures are never the model's: `plan_figures.py` works them out from the answers, the cost baselines and the stored rates, and the model is given them as facts and returns words only (`coach/plan.v1`, reasoning tier). `plan_validator.py` then rejects any number in those words that is not one of the facts, and any figure of the plan that differs from the worked-out ones. A wrong figure cannot reach a worker; a wrong sentence is asked for again once, and a second failure is `502 ai_bad_response` with nothing stored.

The rules (goal shares, the 3-month target, the send weeks, the warnings) are in [`docs/features/coach-plan.md`](../features/coach-plan.md).

| Situation | What happens |
|---|---|
| Answers confirmed, first request | Score, figures and provider found; sentences written and checked; stored as `coach_plans/{hash[:20]}`; session `completed`; `201` |
| Same answers again (any language, even after a failure of the step after storing) | The stored plan, `200`, no Gemini call |
| Not confirmed yet | `409 plan_not_ready` |
| Another request is making the same plan | `409 request_in_progress`, `Retry-After: 5` |
| A rate, the cost baseline or the fee rule is missing | `503 score_unavailable`, `Retry-After: 30`; nothing stored, no Gemini call |
| Sentences unusable twice | `502 ai_bad_response`; nothing stored |
| Gemini busy, down or slow | `503 ai_busy` / `ai_unavailable`, `504 ai_timeout`; the lock is released, the next try works |
| Route outside the six corridors (or no home country) | A plan without a provider, with a `no_provider_quote` note |
| Radar-flagged provider is the cheapest | The next one is chosen |

## Files

| File | Change |
|---|---|
| `backend/app/services/coach/plan_figures.py` (new) | The pure engine: budget, goal split, remittance, debt, emergency fund. `mypy --strict` |
| `plan_inputs.py`, `plan_facts.py` (new) | The inputs from a profile and the stored data; the facts given to the model, and which warnings and checklist items apply |
| `plan_validator.py` (new) | `check_text` (numbers, scale words, links, advice, ids, weeks) and `check_figures` |
| `plan_generator.py`, `app/prompts/coach/plan.v1.yaml`, `app/schemas/coach_plan_text.py` (new) | The Gemini step: facts in, sentences out, one retry with the reasons |
| `plan_quote.py` (new) | The cheapest unflagged provider from Remittance X-Ray |
| `plan_document.py`, `plan_service.py` (new) | The stored document and its view; idempotency by hash, the lock, the order of steps |
| `backend/app/api/v2/coach_plans.py` (new), `router.py`, `dependencies.py` | The two routes and their wiring |
| `coach_scorer.py`, `scoring_inputs.py` | `CoachScorer.load` and `essential_lines` so the score and the plan read the same data |
| `coach_session_repo.py`, `session_service.py` | `CoachPlanRepository.get/create`; `CoachSessions.write_fields` (the plan lock); `complete` clears the lock |
| `backend/app/config.py`, `.env.example` | `GEMINI_COACH_PLAN_TIER` (reasoning) and `GEMINI_COACH_PLAN_THINKING_BUDGET` (1024) |
| `docs/features/coach-plan.md` (new), `docs/api/v2-coach.md`, `docs/data-model/collections/coach.md`, `docs/deferred-items.md`, `backend/app/prompts/README.md` | The rules; the status and the new `503 score_unavailable`; `plan_lock`, `rates_as_of`; D-216/D-217 notes, D-218, D-219; the prompt row |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. Firestore rules need no change: plans are written by the backend only.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Who writes the figures | Code. The model words them (above) |
| 2 | Goal split | 50% of what is left to the debt, 40% to the emergency fund (70% / 25% for a debt at 24% a year or more; 80% to the fund with no debt); the rest is `left_over`. A product choice, written in `coach-plan.md` for the owner |
| 3 | Language | English only until NF-FC-014 (D-218); `language` is accepted |
| 4 | Score unavailable | New `503 score_unavailable`, because a plan carries its score |
| 5 | Home country | From `users/{uid}.home_country`, since it is not an interview slot; with the destination it gives the corridor |
| 6 | `fx_rate` | What the worker effectively gets: `receives ÷ (amount − fee)` |
| 7 | Advice | The validator rejects phrases that suggest borrowing, a new or safer loan, a lender, investing or insurance. The first live run showed the model suggesting "a safer loan" for a costly debt; the prompt was tightened and the check added |

## Results

**Offline (2026-10-09):** 3,042 backend tests pass (154 skipped, the live ones), 127 of them new for this task.

| Check | Result |
|---|---|
| 12 personas, real baselines, labor-law files, corridors and rates, stand-in model | **12 of 12** plans validate as `CoachPlanResponse`, hold the worked-out figures, pass the validator, and have a provider quote; the budget re-adds from the personas' hand-worked amounts (`expected_score.amounts_in_host_currency`) |
| Persona 1 (Maricel) by hand | pay 650 − costs 112 − sending 400 = 138 left; debt 96 (70%), fund 34, left over 8; target 336; 43 weeks; the payment does not cover the 5% a month, so `months_to_clear` is none and `debt_not_covered` is raised |
| Properties on 2,000 random workers | goals never negative; the split never overdraws what is left; the budget always adds up (the schema checks it); same inputs give the same figures |
| Validator | accepts rounded and cut figures, percents, week numbers; rejects an invented amount, a sum nobody gave, a helpline number, extra precision, "thousand/lakh", links, advice to borrow or invest, wrong ids, wrong weeks, an edited debt or remittance |
| Service and routes | idempotent by hash, lock held and released (also after a Gemini failure), a stale lock ignored, missing rate gives `503 score_unavailable` with no Gemini call, route outside the six corridors, Radar-flagged provider skipped, another worker's plan is a 404, a plan outlives its session; every refusal checked through the API with the error envelope |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |

**Live, real Gemini (`gemini-3.5-flash`, reasoning tier), the same day:**

| Persona | Result |
|---|---|
| 1, 2, 3, 4, 5, 6, 7, 8, 10, 11 | **Passed**: sentences accepted by the validator; 5 to 15 seconds each; persona 1, 4 and 7 needed the second call |
| 9, 12 | **Not finished**: the first answer was rejected by the checks, and the second call (with the reasons) was refused by Gemini with `429 RESOURCE_EXHAUSTED`, the **free-tier daily quota** (`PerDayPerProjectPerModel`, about 58,000 s to reset) |

So 10 of 12 personas have a live plan accepted; 9 and 12 are untested live. In about a third of the live runs the model's first answer was rejected (the reasons were not printed in those runs; the live test now prints them). Every rejected answer that got a second call (personas 1, 4 and 7) was accepted on it.

The first live run also found a real defect: for a debt at 60% a year the model wrote "see if you can get a safer loan", against the prompt. The advice check and a stricter prompt were added, and the two weaknesses tested for (a percent written as the word "percent" passing as a week number) were fixed the same day. **Not re-run live after those two changes**, because the quota ended; the offline tests cover them.

**Not verified:** personas 9 and 12 live; how often the first answer is rejected (and so how often a worker could meet `502 ai_bad_response`, which needs two rejections in a row); the plan on production data (D-216: `cost_baselines` is not loaded); the time of a plan on a billed key (5 to 15 s on this one, against the contract's 20 to 40).


## Manual test

```bash
cd backend
# free: figures, validator, the 12 personas, the service and the routes
pytest tests/unit/services/test_coach_plan_figures.py tests/unit/services/test_coach_plan_validator.py tests/unit/services/test_coach_plan_generator.py tests/unit/services/test_coach_plan_personas.py tests/unit/services/test_coach_plan_service.py tests/integration/api/test_coach_plans.py
# live, real Gemini (about 10 seconds a persona; a free-tier key needs the pause)
RUN_LIVE_GEMINI=1 LIVE_SPACING_SECONDS=12 PLAN_LIVE_PERSONAS=all pytest tests/integration/test_coach_plan_live.py -v -s
```

Against production, once `cost_baselines` is loaded (D-216) and the `coach` flag is on for you: finish an interview, confirm the answers, then `POST /api/v2/coach/sessions/{id}/plan` with `{"language": "en"}` and a bearer token (`201`), and repeat the call (`200`, same `id`, no new Gemini call in the logs).

## Limits (D-218, D-219)

English only until NF-FC-014; the goal split and send weeks are product choices; numbers written as words are not checked; the advice check is a list of phrases; the plan id ignores the home country.

## Definition of Done (Backend, Gemini step)

- [x] Correct tier (reasoning) via a setting
- [x] Structured output via a Pydantic response model; no free-text parsing
- [x] Prompt in the library as a versioned file, with its variables
- [x] Failures handled (Gemini errors keep their codes; unusable sentences are a 502; the lock is released)
- [x] Plan JSON matches the contract (`CoachPlanResponse`); a validator rejects any figure not derivable from the inputs; the same answers return the same plan
- [x] Tests with a stand-in model, and a live run recorded here
- [ ] `cost_baselines` loaded in production (D-216) so the route works there
- [ ] Reviewed by a teammate (Devam)

## Commit

Branch: `feature/NF-FC-012-coach-plan-generator` (already checked out).

```bash
git commit -m "feat(coach): add 90-day plan generator with checked figures" -m "Refs: NF-FC-012"
```

PR title: `feat(coach): 90-day plan generator with checked figures (NF-FC-012)`
