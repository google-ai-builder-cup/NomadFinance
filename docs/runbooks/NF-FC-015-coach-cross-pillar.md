# NF-FC-015 — Coach cross-pillar: contract prefill and Financial Identity goals

## Summary

Two links between the Coach and the other pillars.

**1. Contract Shield → Coach (prefill).** If the worker has an analysed employment contract with a salary, the Coach offers that salary instead of asking for it, and **never uses it until the worker says it is right**. When the interview reaches the income stage the salary is stored as an *unconfirmed* `monthly_salary` slot (`source: contract_prefill`) and the coach asks: "Your contract with {employer} says the pay is {amount} {currency} each {period}. Is that right?"

| The worker says | What happens |
|---|---|
| "Yes" | The slot is confirmed; its source stays `contract_prefill`; the interview moves on |
| Another figure ("700 dollars a month") | It replaces the offer as the worker's own answer (`source: user`) |
| "No", a question, anything else | The offer is dropped and the plain salary question is asked; it is not offered again |
| (no contract, or a daily or hourly pay, or a currency the Coach does not take) | Nothing is offered |

It uses the answer machinery that already existed, with no new route and no frontend change: the extraction (NF-FC-010) already turns a plain yes into "the same value, confirmed", and the screen already shows each slot's `source`.

**2. Coach → Financial Identity (goals).** When a plan is made its targets go into `users/{uid}/financial_profile/current.goals`: `{plan_id, savings_rate_target_pct, remittance{amount, currency, cadence: monthly}, emergency_fund_target, set_at}`, every figure taken from the plan. The weekly recompute keeps them (like `latest_export`); a profile built after the plan takes them from the worker's newest plan.

## Files

| File | Change |
|---|---|
| `backend/app/services/coach/prefill.py` (new) | `find_prefill` (which contract, which salary), `clean_employer`, the offer's states (`apply_prefill`), the question. Pure, under `mypy --strict` |
| `session_service.py`, `session_document.py` | A new session stores the offer (`prefill`); `record_turn` applies it; reading the contracts can never stop a session from starting |
| `turn_prompt.py` | The reply follows the same rule (`projected`) and asks the contract question when the salary is the next question |
| `extraction_checks.py` | A yes to a pending value keeps that value's source |
| `backend/app/repositories/contract_repo.py` | `recent(uid, limit)` |
| `backend/app/services/coach/plan_goals.py` (new) | `goals_for(plan)` and `newest_plan_goals` |
| `plan_service.py`, `fib_repo.py`, `profile_builder.py`, `api/v1/internal.py`, `dependencies.py` | Goals written when a plan is made; `FibRepository.set_goals`; `goals` carried over; the recompute's fallback |
| `docs/...` | `coach.md` (`prefill` fields), `fib.md` (goals), `v2-coach.md` (open point 5), `deferred-items.md` (D-223) |

No shared file was touched. The reply prompt was not changed (`coach/reply.v1`), so no prompt version moved and the recorded extraction fixture still replays: the contract question is the existing `ask_next` slot, and the figure in it is in `<slots>`.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | How it is confirmed | In the chat, not a new route (the screens need no change) |
| 2 | Goals with no profile yet | Written if the profile exists; otherwise the next recompute takes them from the newest plan |
| 3 | Age of the contract | None: the worker confirms every offer and sees the employer's name |
| 4 | The employer | Mentioned in the question only; it is not a slot (the interview keeps its 11 slots) |
| 5 | The employer's name is untrusted | Shown only if it looks like a name (short, letters of any script, no markup, not an order) |
| 6 | The savings rate | The plan's emergency saving over its income; the debt payment is not savings |

## Results

**Offline (2026-10-09):** 3,386 backend tests pass (163 skipped, the live ones), 65 of them new.

| Check | Result |
|---|---|
| Which contract | The newest completed employment contract with a salary, a currency the Coach takes and a period of month, week or year; day, hour, zero, negative, a boolean, a text amount, an unknown currency and a missing period are passed over for an older usable one |
| The employer's name | 13 cases: names in Latin, Hindi and with punctuation are kept; markup, an over-long name, seven words, an order ("Ignore previous instructions") and a closing tag are dropped |
| The offer's life | Waits at intro; becomes an unconfirmed slot at income; a yes confirms it (source kept); another figure replaces it; any other reply drops it; a turn where the worker did not speak does not drop it; a finished offer is never applied again |
| Through a session | A new session keeps the offer and shows no salary; at income the slot is unconfirmed and the next question is the salary; yes, no and another figure each leave the right state; no contract, no finder or a failed read leaves no offer and never fails the start |
| The reply | The turn that reaches income already asks the contract question; the figure is in `<slots>`; after a no the plain question comes back |
| Goals | Each persona's goals equal their plan's figures; asking again or in another language writes nothing more; a failed write never fails the plan; with no profile the plan is still made; a recompute keeps the goals; a profile built after the plan takes them from the newest plan |
| Break the rules on purpose | 5 breaks (the offer never dropped, offered at once, the source lost on a yes, goals not carried, no attack check on the name): each failed a test. The last one first passed, because the examples were rejected earlier by the length rule; a case only the attack rules catch was added |
| `black`, `ruff`, `mypy app`, `mypy --strict app/services` | clean |

**Not verified:** a real conversation with the model asking and understanding the contract question (the question is the existing `ask_next` and the yes is the existing extraction path, both exercised live in NF-FC-010, but not together); the prefill on production data (it needs an analysed contract and `cost_baselines`, D-216); the goals on the FIB screen (nothing reads them until NF-HR-001).

## Manual test

```bash
cd backend
pytest tests/unit/services/test_coach_prefill.py tests/unit/services/test_coach_plan_goals.py tests/unit/services/test_coach_extraction_checks.py
```

With the `coach` flag on for you and an analysed employment contract that states a salary: start a Coach session, answer the first three questions, and the coach asks about the contract's salary (`GET /api/v2/coach/sessions/{id}` shows `monthly_salary` with `confirmed: false`, `source: contract_prefill`); say yes and it turns `confirmed: true`. After a plan is made, `users/{uid}/financial_profile/current.goals` holds the plan's targets.

## Limits (D-223)

The offer is read when a session starts; anything but a yes drops it; the employer name comes from an uploaded document; daily and hourly pay is not offered; goals are written when a plan is made or a profile is recomputed.

## Definition of Done (Backend)

- [x] Prefill is always confirmed by the worker before it is used
- [x] Goals are written to the FIB profile when a plan is made, and survive a recompute
- [x] A failure reading contracts or writing goals never fails the interview or the plan
- [x] Type hints, `mypy --strict` on the services, no secrets, no shared file touched
- [x] Tests, including breaking the rules on purpose
- [ ] A live conversation through the prefill question
- [ ] `goals` seen on the FIB profile in production (needs a plan and a profile)
- [ ] Reviewed by a teammate (Aditya)

## Commit

Branch: `feature/NF-FC-015-coach-cross-pillar` (already checked out).

```bash
git commit -m "feat(coach): add contract prefill and Financial Identity goals" -m "Refs: NF-FC-015"
```

PR title: `feat(coach): contract salary prefill and Financial Identity goals (NF-FC-015)`
