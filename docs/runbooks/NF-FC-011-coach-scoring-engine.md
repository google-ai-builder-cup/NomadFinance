# NF-FC-011 — Coach preparedness scoring engine

## Summary

The Financial Coach now works out the preparedness score. At `review` and `plan` the session carries `score` (total 0–100, band, five factors), worked out by the rubric (version 1) from the worker's answers, the host country's living costs, the legal recruitment-fee cap and the stored exchange rates. No model is involved: it is arithmetic, the same answers always give the same score.

| What is missing | What the worker sees |
|---|---|
| Nothing | The score and its five factors |
| An exchange rate (including NPR and BDT, D-170) | `score: null` ("try again"); the log says `coach_score_unavailable reason=no_rate:SGD_PHP` |
| The host's cost baseline (not loaded, D-216) | `score: null`; `reason=no_baseline:SG` |
| The host's recruitment-fee rule | `score: null`; `reason=no_fee_rule:SG` |
| Pay of zero | `score: null`; `reason=not_scorable:…` |

The rubric never guesses a missing figure, so the score is unavailable rather than wrong.

## Files

| File | Change |
|---|---|
| `backend/app/services/coach/scoring.py` (new) | The pure engine: anchors and interpolation, interest penalty, shortfall cap, half-up rounding, bands and the floor rule. Inputs in, `CoachScore` out; no I/O. `mypy --strict` |
| `backend/app/services/coach/scoring_inputs.py` (new) | Turns a profile and stored data into the engine's inputs: living costs, fee cap (`FEE_CAP_KEYS`), conversion to the host currency |
| `backend/app/services/coach/coach_scorer.py` (new) | `CoachScorer`: reads `cost_baselines`, `labor_laws` and `rates_cache`, then calls the engine |
| `backend/app/repositories/cost_baseline_repo.py` (new) | Reads `cost_baselines/{host}` |
| `backend/app/services/coach/session_document.py`, `session_service.py` | The scorer hook is now `async`; the service awaits it before building the session view (`to_session` no longer calls it) |
| `backend/app/dependencies.py` | `get_coach_sessions` passes the real scorer |
| `backend/tests/...` | 114 new tests (below); one existing test changed from a sync to an async scorer |
| `docs/api/v2-coach.md` | The fee-cap key table; status; D-207 and D-170 notes; D-216, D-217 |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Async scorer | Reading Firestore is I/O, so the scorer is async and `CoachSessions` computes the score before `to_session`. It touched Aditya's session service and one of its tests |
| 2 | One currency | The host's currency. The rate is the stored pair `HOST_QUOTE` (units of the home currency per one host unit), amount ÷ rate. A host-currency amount needs no rate |
| 3 | Fee cap | Read from `labor_laws/{host}/rules/recruitment_fees` by a named list of keys (`maximum_agency_fee`, `placement_fee_non_citizen`, `maximum_commission`); months as they are, percent ÷ 100, no number 0. Result: SG 2.0, MY 1.0, HK 0.10, KR/JP/AU 0 |
| 4 | Pure engine | The engine takes its inputs; the reading is in `coach_scorer.py`. NF-FC-012 can reuse it |
| 5 | Privacy | Logs hold only the reason, never a figure or a name |

## Results

| Check | Result |
|---|---|
| 12 personas against the hand-computed values | **12 of 12**: total, band, every factor's points and value, and the converted amounts (0.02 s, no Gemini) |
| 12 personas through the scorer with the stored-data shapes | 12 of 12 |
| Engine against the plain reference of NF-FC-007 | agree on all 12 |
| Properties on 2,000 random workers | total and points whole numbers 0–100; deterministic; never rises with more debt, a bigger fee or remittance, less savings, a worse account, a higher interest; never falls with a looser fee cap |
| Break the engine on purpose | 4 breaks (interest threshold, shortfall cap, minimum outgoings, rounding), each failed a test |
| Session at `review` | carries the persona's expected score; read again, the same |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |
| Backend suite | 2,915 passed, 151 skipped (the live ones) |

**Not verified:** a score on the real production data, because `cost_baselines` is not in production (D-216). The first live check comes after the load below.

## Before the demo: load the cost baselines (D-216)

A production write; run it only once you have decided to.

```bash
cd data-scripts
python -m src.loaders.cost_baselines --dry-run   # validates 6 hosts, writes nothing (run today: clean)
python -m src.loaders.cost_baselines             # writes cost_baselines/{AU,HK,JP,KR,MY,SG}
```

Needs the same Google credentials as the other loaders. Until it is loaded every score is `null`.

## Manual test

```bash
cd backend
pytest tests/unit/services/test_coach_scoring.py tests/unit/services/test_coach_scoring_personas.py tests/unit/services/test_coach_scorer.py tests/unit/services/test_coach_session_service.py
```

All free and under a second.

## Limits (D-216, D-217)

Computed on every read, not stored (NF-FC-012 should freeze it into the plan); one stored rate per currency; the AU cap is 0 with low confidence (D-199); living costs are the baseline's typical figure.

## Definition of Done (Backend)

- [x] Pure-Python rubric, live rates, fee cap from `labor_laws`; score, band and factor breakdown returned
- [x] Property tests (0–100, monotonic in debt) and hand-computed values for all 12 personas
- [x] Type hints, `mypy --strict` on the services, no secrets, no shared file touched
- [x] Failure of any input is a logged `null`, never a guess or a stack trace
- [x] Docs and open items updated
- [ ] `cost_baselines` loaded in production (D-216)
- [ ] Reviewed by a teammate

## Commit

Branch: `feature/NF-FC-011-coach-scoring-engine` (already checked out).

```bash
git commit -m "feat(coach): add preparedness scoring engine with fee cap and live rates" -m "Refs: NF-FC-011"
```
