# NF-FC-001 — Coach interview slots and question bank

## Summary

What the Financial Coach (Future Scope, behind the `coach` flag) asks a worker, and what it keeps:

1. **Eleven slots**, as one Pydantic model, `CoachProfile`: destination country, job, departure date, salary, dependents, remittance target, recruitment fee paid, debt owed, interest, savings, bank or wallet.
2. **A question bank**, `question_bank.json`: for each slot the stage it is asked in, a plain-English question, a short "why we ask", an expected range, follow-up wording for when the answer is unclear, and skip rules.
3. **Two small functions** that apply the bank: `is_applicable` (skip rules) and `range_issue` (expected ranges). Without them the rules would be text nobody can test.

No endpoint, no Gemini call, no Firestore read or write and no screen. The session (NF-FC-008), the turn and the slot extraction (NF-FC-009, -010) and the scoring (NF-FC-006, -011) build on this.

This task also carries two analytics fixes from NF-SA-022 (last section).

**Not in this task:** the session state machine and which stage is next (NF-FC-008); the extraction prompt and the flow that asks a follow-up (NF-FC-010); the scoring rubric, the legal fee cap and FX (NF-FC-006, -011); the API contract (NF-FC-002); cost baselines (NF-FC-003 to -005); personas (NF-FC-007); contract prefill (NF-FC-015); frontend types. No Firestore rules or indexes change.

## The slots

The full table (value, stage, when it is asked) is in `docs/data-model/collections/coach.md`, "The slots". In short:

| Stage | Slots |
|---|---|
| intro | `destination_country`, `job_type`, `departure_date` (the only one that may stay empty) |
| income | `monthly_salary` |
| obligations | `dependents`, `remittance_target` |
| debt | `recruitment_fee_paid`, `debt_outstanding`, `debt_interest` (skipped when `debt_outstanding` is 0) |
| savings | `savings`, `bank_or_wallet` |

A money slot is `{ "amount", "currency", "period" }` (D-106). A stored slot is a `SlotRecord`: `value`, `confidence`, `source` (`user` or `contract_prefill`), `confirmed`, `updated_at`, `turn`.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/coach_profile.py` | New: `CoachProfile`, `Money`, `Interest`, `SlotRecord`, `parse_slot_value`, the slot names |
| `backend/app/schemas/coach_questions.py` | New: the models that check the bank file (`QuestionBank`, `Question`, the five kinds of range) |
| `backend/app/services/coach/question_bank.json` | New: the 11 questions, follow-up defaults, the pay scale |
| `backend/app/services/coach/question_bank.py` | New: `load_question_bank`, `is_applicable`, `range_issue`. Under `mypy --strict` |
| `backend/tests/unit/test_coach_profile.py` | New: 88 tests for the slot rules |
| `backend/tests/unit/services/test_coach_question_bank.py` | New: the file, its wording, skip rules, follow-ups |
| `backend/tests/unit/services/test_coach_question_ranges.py` | New: the expected ranges |
| `backend/tests/unit/services/test_coach_question_bank_edits.py` | New: 23 slips in the file that must be refused |
| `backend/tests/fixtures/coach_bank.py` | New: helpers shared by those three files |
| `docs/data-model/collections/coach.md` | New "The slots" section; the example no longer says the names are illustrative |
| `docs/deferred-items.md` | D-106 closed; D-164 corrected; D-168 to D-174 added |
| `frontend/src/lib/analytics.ts`, `analytics.test.ts` | The analytics fixes (last section) |
| `docs/data-model/collections/scam.md`, `docs/features/scam-analyzer.md`, `docs/runbooks/NF-SA-022-scam-stats-events.md` | Same fixes, in the docs |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. The bank ships in the image with the rest of `app/`.

## How the question bank works

```json
{
  "slot": "debt_interest",
  "stage": "debt",
  "prompt_en": "How much extra do you pay on this money (the interest)? ...",
  "why_en": "A high interest can make a debt grow fast.",
  "expected": { "kind": "rate", "month": {"low": 0, "high": 20}, "year": {"low": 0, "high": 240} },
  "skip_if": [ { "slot": "debt_outstanding", "field": "amount", "equals": 0 } ]
}
```

- **Order** is the order of the file, grouped by stage. The checker refuses a missing or repeated slot, a stage out of order or empty, and a kind of range that does not fit the slot.
- **`expected`** is what a worker would usually say. It is a question to ask again, never a refusal: the coach asks the `out_of_range` follow-up and keeps the value only when the worker confirms it. What the model refuses outright (a negative amount, 21 dependents) is in `CoachProfile`. For money, the range is a multiple of `monthly_pay_scale[currency]`, so one table of eleven numbers serves every amount. A yearly salary typed as monthly (50,400 AUD a month) is caught this way.
- **`skip_if`** lists rules; one matching rule skips the question. A rule may only look at an answer asked earlier, and an answer not given yet never skips a question.
- **Follow-ups** are the wording for the five reasons to ask again: `not_understood`, `low_confidence`, `out_of_range`, `missing_currency`, `unclear_period`. The bank has a default per kind of answer; a question lists only the ones it words differently (for example, the country question names the six countries). `bank.follow_up(slot, trigger)` returns the right one and refuses a reason that cannot happen (a total is never asked "which period?").
- **Wording** is for a worker who reads English as a second language: short sentences, no finance words. Tests check sentence length and a list of words not to use. The coach model re-words each question in the worker's language; the English text is the meaning it must keep.

### Editing the file

1. Edit the JSON. Keep the text short and plain (a prompt is at most 300 characters).
2. Run the tests (below). The checker tells you what is wrong.
3. Raise `version` when the meaning changes (a new slot, a changed range), not for a typo.

A new slot also needs a field in `CoachProfile`, its place in `_KIND` in `coach_questions.py`, and a question. The tests list the eleven names, so they fail until all are done.

## How later tasks use it

| Task | Use |
|---|---|
| NF-FC-008 session | `load_question_bank()`; `is_applicable(question, profile)` to find the next question to ask; `question.required` (only `departure_date` is optional); store answers as `SlotRecord`. See D-171 |
| NF-FC-009 turn | `question.prompt_en` and `why_en` as what the reply must ask and may explain |
| NF-FC-010 extraction | Check each extracted value with `parse_slot_value(name, raw)`, then `range_issue(bank, slot, value, today)` (pass today's date: it never reads the clock). `too_low` or `too_high` means ask `bank.follow_up(slot, "out_of_range")`. Never convert a week or a year to a month before storing: keep what was stated |
| NF-FC-006, -011 scoring | `CoachProfile` as input; `Money.per_month()` for a flow. NPR and BDT have no FX pair yet (D-170) |
| NF-FC-007 personas | Fixtures validate with `CoachProfile.model_validate`. Dates are text and the profile never compares them with today, so a fixture does not expire |

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where the bank lives | A static JSON beside the code that reads it (`services/coach/`), like `scam/indicator_data.json`. Not `data-scripts/`: no screen or job reads it from Firestore |
| 2 | No `home_country` slot | It is in the onboarding profile. A worker from outside the six corridors still gets a plan, without a provider quote |
| 3 | No `has_debt` slot | "Owes nothing" is `debt_outstanding` with amount 0, so two fields cannot disagree |
| 4 | Currencies | 11: the six hosts, PHP, INR, IDR, and NPR and BDT because onboarding offers Nepal and Bangladesh. No FX for those two yet (D-170) |
| 5 | Pay by the day or hour | Not accepted. The follow-up asks for a normal month; the coach does not guess working days |
| 6 | Stored as stated | A yearly figure stays `year`. A stored value is only what the worker said, as the extraction rule in the tracker requires (NF-FC-010) |
| 7 | The pay scale | Eleven round numbers, labelled in the file as rough and unsourced, because they only catch slips such as an extra zero (D-173) |
| 8 | Hard limit against expected range | Two layers, so a value the coach asked about can still be stored once the worker confirms it |
| 9 | Departure date window | Held in the bank (30 days back, 730 ahead) and checked against a date passed in, not in the model, so persona fixtures do not expire |
| 10 | Owner | D-106 named Aditya as the owner of NF-FC-001; the tracker says Devam. The tracker was followed |

## Run it

From `backend/`, with the virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell).

```bash
python -m pytest tests/unit/test_coach_profile.py tests/unit/services/test_coach_question_bank.py tests/unit/services/test_coach_question_ranges.py tests/unit/services/test_coach_question_bank_edits.py -q
```

Expect `196 passed`. To see the interview order (optional slot shows `False`):

```bash
python -c "from app.services.coach.question_bank import load_question_bank as l; [print(q.stage, q.slot, q.required) for q in l().questions]"
```

To see the range check catch a yearly salary typed as monthly (expect `too_high`; then change the amount to 4200 and expect `None`):

```bash
python -c "from datetime import date; from app.schemas.coach_profile import parse_slot_value as p; from app.services.coach.question_bank import load_question_bank as l, range_issue as r; print(r(l(), 'monthly_salary', p('monthly_salary', {'amount': 50400, 'currency': 'AUD', 'period': 'month'}), date.today()))"
```

The same commands work in PowerShell. Lint and types, as in the earlier runbooks:

```bash
python -m black --check app tests && python -m ruff check app tests && python -m mypy app && python -m mypy --strict app/services
```

## Checks run (2026-10-08)

| Check | Result |
|---|---|
| `black --check`, `ruff check` (all of `app` and `tests`) | clean (350 files) |
| `mypy app`, `mypy --strict app/services` | clean (179 and 61 files) |
| Backend unit tests | 1,724 passed, 7 skipped (the 7 were skipped before); 196 of them are new |
| Coverage of the new code | 100% (293 statements: `coach_profile`, `coach_questions`, `question_bank`) |
| The checker works | 23 edits of the bank file (a slot twice, a stage empty, a skip rule that looks ahead, a missing follow-up, a mistyped key, ...) each refused with the right message |
| Frontend ESLint and Prettier on the changed files | clean |
| Frontend tests | 756 passed. **3 files could not load** (`scamParts.a11y`, `scamPages.a11y`, `axe.test`): `axe-core` is in `package.json` but not installed on this machine (D-169) |
| Frontend `tsc -b` | 4 errors, all in `src/mocks/axe.ts` for the same missing package; none in changed files |
| Break the analytics code on purpose | Putting `language` back failed 3 tests (including the new reserved-name one); taking a route out of the id list failed 6 (including the router-drift one); both restored byte for byte |

**Not verified:** DebugView and anything on the live site (needs a deploy and a measurement ID); `pnpm build`; the browser preview (Analytics is off without a measurement ID, so there is nothing to see); commitlint (not installed here; both headers were counted by hand: 50 and 68 characters); the emulator-backed backend tests (this change does not touch Firestore).

## Definition of Done

Tracker row: *Pydantic CoachProfile model + question bank JSON reviewed; each slot has validation ranges and a plain-language prompt in EN.*

- [x] Pydantic `CoachProfile` model (11 slots, hard limits)
- [x] Question bank JSON, each slot with an expected range, an EN prompt, follow-ups
- [x] Skip logic and ranges are code with tests, not only text
- [ ] **Reviewed** by Pranjal (reviewer in the tracker)

Curated dataset checklist:

- [ ] Every figure carries source URL and retrieval date; curator recorded. The curator is recorded (`"Devam"`). The ranges are plausibility bounds, not facts; the eleven pay-scale numbers are **deliberately unsourced** and say so in the file (D-173). Tell me if you want them researched
- [x] Validated against schema; loading is read-only and cached (there is nothing to write, so nothing to repeat)
- [ ] Second teammate spot-check (the reviewer, above)
- [x] Synthetic only: no worker data, no key, no `.env` content

Documentation: [x] Markdown, [x] under `docs/`, [x] no AI attribution, [ ] teammate review.

## Fixes carried over from NF-SA-022

DebugView on the first production check found two problems that unit tests, which mock Google, could not. Both are fixed here, as the owner asked.

| # | Problem | Fix | Status |
|---|---|---|---|
| 1 | `language` never reached Analytics: Google already adds its own `language` to every web event | Renamed to `ui_language` in `analytics.ts`, its test, `scam.md`, the NF-SA-022 runbook, `scam-analyzer.md` and D-164 | Done |
| 2 | The id of a stored check reached Analytics in `page_location` | **Stripped** (the owner did not choose; stripping is the safer option, and "coarse values only" was untrue otherwise). One function, `anonymisePath`, turns `/scam-check/history/{id}` into `/scam-check/history/:id` | Done |
| 2b | Found while fixing #2: the same leak for `/contract/{id}` and `/radar/entity/{slug}`; `page_path` and the crash report used the raw path; and a message shared into the installed app opens `/scam-check?text=...`, so it was in the address of the first events | Every event now sends its own `page_location`: origin and path, no query, no fragment, no id. Same for `page_path`, a same-origin `page_referrer`, the crash report, and the first address Google uses for the events it sends itself | Done |
| 3 | Unit tests could not catch #1 | A test lists the names Google adds itself or reserves (from Google's two documentation pages) and fails if an event uses one. Shown to fail with `language` put back | Done |
| 3b | New routes with an id could leak again | A test reads `router.tsx` and fails if a route with a `:parameter` is not covered | Done |
| 4 | Parameter values only half-checked | A test asserts every parameter value is a short id or flag, apart from the address and a crash report. Clicking the two `scam_verdict_viewed` events in DebugView is still by hand | Test done; by hand open |
| 5 | Test data still in production | Not touched: it is live data. Steps in D-168 | Open (you) |
| — | Production index, custom dimensions (`ui_language`), first run of the stats job | Not done: they are console steps (D-164) | Open (you) |
| — | Review by Aditya | — | Open |
| — | Dashboard card "Rate · SG → IN: Could not load this" | Not checked: it needs the backend running. If it still fails, it is not the scam work (D-168) | Open |

### After the deploy

1. In DebugView repeat steps 1 to 3 of the NF-SA-022 runbook, then steps 6 and 7 (new): `ui_language` is there, `page_location` on a stored check ends in `/scam-check/history/:id`, and the two `scam_verdict_viewed` events say `source: check` and `source: history`.
2. In Google Analytics, Custom definitions: register `ui_language`, not `language`.
3. Delete the production test data and run the other one-time steps (D-164, D-168).

## Noticed, not fixed

All are in `docs/deferred-items.md`: D-168 (live checks and test data), D-169 (`pnpm install`), D-170 (NPR and BDT have no FX pair), D-171 (the session must tell "not sure" from "not asked", and record the bank version), D-172 (the rubric may need a repayment slot), D-173 (the pay scale is not sourced), D-174 (limits of the cleaned address).

## Commit

Branch: `feature/NF-FC-001-data-coach-slots` (already checked out). Two commits keep the Coach work and the analytics fix apart:

```bash
git add backend docs/data-model/collections/coach.md docs/runbooks/NF-FC-001-coach-slots.md
git commit -m "feat(coach): add interview slots and question bank" -m "Refs: NF-FC-001"
```

```bash
git add frontend docs/data-model/collections/scam.md docs/features/scam-analyzer.md docs/runbooks/NF-SA-022-scam-stats-events.md docs/deferred-items.md
git commit -m "fix(scam): send ui_language and strip ids from the analytics address" -m "Refs: NF-SA-022"
```

PR title: `feat(coach): interview slots and question bank (NF-FC-001)`
