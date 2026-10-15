# NF-FC-007 — Coach regression personas

## Summary

Twelve invented workers, two for each of the six corridors, for testing and demonstrating the Financial Coach.

1. **The personas**, in `backend/tests/fixtures/coach_personas.json`. Each has the messages the worker types in order, the slots a correct reading must end with, and the score the rubric (version 1) gives those answers.
2. **A loader and models**, `backend/tests/fixtures/coach_personas.py`, that refuse a file that has drifted from the shape its readers rely on. The expected slots are a `CoachProfile`.
3. **A plain copy of the rubric**, `backend/tests/fixtures/coach_rubric_reference.py`, used to re-work every stored score. It is not the engine (NF-FC-011).
4. **29 tests**, `backend/tests/unit/test_coach_personas.py`.

No endpoint, no Gemini call, no production code. The readers are the scoring engine tests (NF-FC-011), the multi-turn runner (NF-FC-024) and the demo seed (NF-HR-003).

The tracker lists this task for Pranjal; Aditya did it.

## The twelve

| Id | Corridor | Language | Job | Score | Band | What it exercises |
|---|---|---|---|---|---|---|
| `p01_sg_ph_maricel` | SG-PH | tl | domestic | 22 | needs_work | Fee far over the Singapore cap, 5% a month debt, no savings, wallet only |
| `p02_sg_ph_jun` | SG-PH | en | construction | 90 | well_prepared | Pay by the **week**; destination and job in one answer; the coach asks "week or month?"; no debt, so no interest question |
| `p03_sg_in_priya` | SG-IN | hi | domestic | 65 | getting_ready | **Demo user Priya**; fee inside the cap, small debt at 2% a month |
| `p04_sg_in_ravi` | SG-IN | en | manufacturing | 93 | well_prepared | Short answers; no debt; strong savings |
| `p05_au_in_gurpreet` | AU-IN | hi, en | care | 75 | getting_ready | **Language switch** in answer 5; total over 70 but a buffer of 17 points: the **floor rule** holds the band down |
| `p06_au_in_anil` | AU-IN | en | construction | 77 | well_prepared | Pay as a **yearly** figure; does not know his leaving date, so the slot stays empty |
| `p07_my_id_slamet` | MY-ID | id | plantation | 36 | needs_work | Fee well over the Malaysian cap, 4% a month loan, no account |
| `p08_my_id_siti` | MY-ID | id | domestic | 81 | well_prepared | Fee inside the cap; destination and job in one answer |
| `p09_jp_ph_mark` | JP-PH | tl | manufacturing (intern) | 49 | getting_ready | Pay with **no currency** (follow-up), a fee with an **extra zero** (out-of-range follow-up, then corrected) |
| `p10_jp_ph_miguel` | JP-PH | tl | care | 94 | well_prepared | **Demo user Miguel**; no fee, no debt; the shortest script (10 messages) |
| `p11_au_ph_jenny` | AU-PH | tl | care | 68 | getting_ready | Fee above what Australia would expect, 2% a month loan |
| `p12_au_ph_ricardo` | AU-PH | en | other | 30 | needs_work | Plans to send more than he can afford: the **shortfall cap** (25 points) |

Bands: 3 needs_work, 4 getting_ready, 5 well_prepared. Languages (the first one of each persona): English 4, Tagalog 4, Hindi 2 (Priya, and Gurpreet who switches to English), Indonesian 2.

## The file

Per persona: `script` (the messages: `say`, `language`, `fills` = the slots a correct reading takes from it, `coach_follow_up` = the follow-up the coach must ask next), `skipped_slots` (not asked: the interest question when there is no debt), `declined_slots` (asked, not answered), `expected_turn_count`, `expected_slots`, and `expected_score` (the rate used, every amount in the host currency, each factor's `value`, `points` and `weight`, the `total` and the `band`).

**Rates are fixed** (units of the home currency per unit of the host currency): SGD→PHP 42, SGD→INR 62, AUD→INR 54, MYR→IDR 3,700, JPY→PHP 0.38, AUD→PHP 37. They are illustrative, so an expected score never depends on the live rate.

**Last message.** Every script ends with a message that confirms the review and fills nothing, so `expected_turn_count` includes it.

## Two scores by hand

Re-work these from the rubric in `backend/app/services/coach/scoring.py`; they come out as the file says.

**Maricel** (Singapore, domestic worker; salary SGD 650; essentials SGD 0 + 0 + 100 + 12 = 112).

| Factor | Working | Points |
|---|---|---|
| Debt | PHP 100,000 / 42 = SGD 2,380.95; / 650 = 3.66 months; 60 - 0.66 x 10 = 53.4; 5% a month = 60% a year, minus 20 | **33** |
| Buffer | no savings | **0** |
| Remittance | 400 / 650 = 0.62; 70 - (0.62 - 0.5) / 0.2 x 40 = 47; leftover 650 - 112 - 400 = 138, no cap | **47** |
| Fee | PHP 120,000 / 42 = SGD 2,857.14; / 650 = 4.40 months; cap 2; excess 2.40, at least 2 | **0** |
| Banked | `mobile_wallet` | **55** |

Total: 0.30 x 33 + 0 + 0.15 x 47 + 0 + 0.10 x 55 = 9.9 + 7.05 + 5.5 = 22.45, so **22**, `needs_work`.

**Ricardo** (Australia, other; salary AUD 3,000; essentials 1,257 + 600 + 163 + 42 = 2,062).

| Factor | Working | Points |
|---|---|---|
| Debt | PHP 200,000 / 37 = AUD 5,405.41; / 3,000 = 1.80 months; 85 - 0.80 x 12.5 = 75; 6% a month = 72% a year, minus 20 | **55** |
| Buffer | no savings | **0** |
| Remittance | 1,200 / 3,000 = 0.40; 100 - 0.1 / 0.2 x 30 = 85 is the line value, but 3,000 - 2,062 - 1,200 = -262 is a shortfall, so at most 25 | **25** |
| Fee | PHP 150,000 / 37 = AUD 4,054.05; / 3,000 = 1.35 months; Australia 0, excess 1.35; 30 - 0.35 x 30 = 19.5 | **19** |
| Banked | `mobile_wallet` | **55** |

Total: 0.30 x 55 + 0 + 0.15 x 25 + 0.20 x 19 + 0.10 x 55 = 16.5 + 3.75 + 3.8 + 5.5 = 29.55, so **30**, `needs_work`.

(The remittance line value: between 0.30 and 0.50 the points run from 100 to 70, so 0.40 gives 85. The shortfall cap lowers it to 25.)

## What the tests check

- The file is valid; twelve personas with different ids and names; two per corridor; the corridor matches the countries; the six rates match the corridor pairs and every money slot is in the host or the home currency.
- The languages are among the six; the set used is `en`, `hi`, `tl`, `id`; only Gurpreet switches mid-session; Priya and Miguel are the demo users.
- The expected slots are a valid `CoachProfile` and survive a round trip; every slot is present except the skipped and the declined; the interest question is skipped exactly when the debt is 0.
- Every value is one the question bank would keep without asking again (`range_issue` is empty).
- Each slot is filled once, in the bank's order; the last message fills nothing; a message with a follow-up fills nothing and the next one answers it; the follow-ups used are `unclear_period`, `missing_currency` and `out_of_range`; the number a worker states is in the message that fills the slot.
- The plain rubric copy reproduces the three worked examples of the rubric page (59, 17, 91).
- The stored score of each persona equals the rubric applied to its answers (total, band, every factor's points and value, the amounts); the weights add up to 1; the total is the half-up weighted sum.
- The set reaches all three bands, the floor rule (Gurpreet), the shortfall cap (Ricardo) and fees over the cap (Maricel, Slamet, Mark).

Changing a stored total makes two tests fail, which was checked.

## Files

| File | Change |
|---|---|
| `backend/tests/fixtures/coach_personas.json` | New: the twelve personas |
| `backend/tests/fixtures/coach_personas.py` | New: models and `load_personas()` |
| `backend/tests/fixtures/coach_rubric_reference.py` | New: a plain copy of the rubric for checking |
| `backend/tests/unit/test_coach_personas.py` | New: 29 tests |

No shared file (requirements, `pyproject.toml`, `package.json`, Dockerfile, rules, workflows) was touched. No application code changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | Where the fixtures live | `backend/tests/fixtures/`, a JSON file and a loader, like the other fixtures. The runner (NF-FC-024) and the seed (NF-HR-003) read the same file |
| 2 | Only the six corridors | Hosts SG, AU, MY, JP and homes PH, IN, ID. South Korea and Hong Kong have no persona (D-205) |
| 3 | Demo users | Priya and Miguel are the personas of the same name, with answers close to their seed files (`data-scripts/data/seed/users/`) |
| 4 | Fixed rates | The stored scores use fixed illustrative rates, not the live ones |
| 5 | Money as stated | A weekly or yearly pay is stored as the worker said it (period `week` or `year`), as `CoachProfile` keeps it |
| 6 | Second implementation | The tests carry a plain copy of the rubric to re-work the scores. It guards against a slip in the numbers, not against a misreading of the page (D-204) |
| 7 | Fixed leaving dates | Dates between 2026-11-15 and 2027-03-01; a live runner must shift them (D-203) |
| 8 | Words | The Tagalog, Hindi and Indonesian lines were written by the team (D-202) |

## Run it

From `backend/` with its virtual environment active (`source .venv/Scripts/activate` in bash, `.venv\Scripts\Activate.ps1` in PowerShell):

```bash
python -m pytest tests/unit/test_coach_personas.py -q
```

Expect `29 passed`. To see the whole unit suite:

```bash
python -m pytest tests/unit -q
```

Lint and types for the new files:

```bash
python -m black --check tests/ && python -m ruff check tests/ && python -m mypy tests/unit/test_coach_personas.py tests/fixtures/coach_personas.py tests/fixtures/coach_rubric_reference.py
```

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| New tests | 29 passed |
| Backend unit suite | 1,904 passed, 1 skipped, **1 failed**: `test_coach_question_bank.py::TestTheFile::test_the_file_is_utf8_json_with_a_final_newline`, the line-ending test of D-181 on a Windows checkout. Not related to this task |
| `black --check`, `ruff check` | clean |
| `mypy` | the three new files are clean |
| Tamper check | changing one stored total made the score test and the weighted-sum test fail; restored |

**Not verified:** the scripts against the real interview (NF-FC-009, -010 are not built); the expected scores by a second reader (D-204); the backend integration suite (no application code changed).

## Definition of Done

Tracker row: *Fixtures validate against CoachProfile; expected scores hand-computed from the rubric.*

- [x] Twelve personas, two per corridor, with scripted answers, expected slot values and expected score band
- [x] The expected slots validate against `CoachProfile`
- [x] Expected scores worked out from the rubric, stored with their arithmetic, and re-worked by a second implementation in the tests
- [ ] Hand-checked by a second teammate (D-204)
- [x] No real worker data: every name and number is invented
- [x] Markdown, under `docs/`, no attribution lines
- [ ] Teammate review

## Noticed, not fixed

Left for later: D-202 (native-speaker read), D-203 (fixed leaving dates), D-204 (second reader), D-205 (no KR, HK, ne or bn persona). Also outside this task: D-181, the CRLF-sensitive test, still fails on this Windows checkout.

## Commit

Branch: `feature/NF-FC-007-data-coach-personas` (already created).

Commit message:

```
test(coach): add twelve regression personas
Refs: NF-FC-007
```
