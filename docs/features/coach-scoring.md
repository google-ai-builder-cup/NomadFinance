# Financial Coach: preparedness score

The rubric behind the 0 to 100 score that the Financial Coach shows a worker after the interview (design `docs/future-scope/design.md` section 4.4). It is the contract for the scoring engine (NF-FC-011), for the twelve test personas (NF-FC-007) and for the score screen (NF-FC-020).

**Version 1** (`rubric_version: 1` in the score). Any change to a weight, an anchor, a band or a cap raises it.

| | |
|---|---|
| Deterministic | The same answers, rates and caps always give the same score. No model, no randomness, no clock |
| Explainable | Five factors, each with a measured figure, points out of 100 and a weight. A worker can see why the number is what it is |
| What it is not | Not a credit score, not a prediction and not financial advice. It tells a worker how ready their money is for the move. Every score carries the "not professional financial advice" note (design 4.5) |
| Where the shape is fixed | `CoachScore` and `ScoreFactor` in `backend/app/schemas/coach_plan.py`; the API text is `docs/api/v2-coach.md`, "The score" |

## What goes in

Eleven answers are collected (`backend/app/schemas/coach_profile.py`); the score reads eight of them.

| Answer (slot) | Used by | Note |
|---|---|---|
| `destination_country` | essential costs, fee cap, the currency everything is converted to | The host currency: SG SGD, KR KRW, MY MYR, JP JPY, HK HKD, AU AUD |
| `job_type` | essential costs | Selects the `by_job_type` figures of `cost_baselines` (a live-in domestic worker in SG pays 0 for housing and food) |
| `monthly_salary` | all five | Turned into a month with `Money.per_month()` (a week is 52/12, a year is 12) |
| `remittance_target` | buffer, remittance ratio | Per month |
| `recruitment_fee_paid` | fee against the cap | A total |
| `debt_outstanding`, `debt_interest` | debt to income | A total; interest is a rate per month or per year |
| `savings` | emergency buffer | A total |
| `bank_or_wallet` | banked status | |
| `departure_date`, `dependents` | **not used** | They matter to the plan (timing, how much must be sent), not to how ready the money is. See "What the score does not see" |

**One currency.** Every amount is converted into the host currency before any arithmetic: an amount in another currency is divided by the stored host-to-home rate of its corridor (`rates_cache`, for example `AUD` to `INR`). The score is computed from `review` onwards, when every question except the departure date is answered, so no factor is ever left out and the weights always add up to 1.

**Cannot be scored.** If an amount is in a currency that has no rate to the host currency (NPR and BDT today, D-170), the score is not computed and the session shows "try again" (API contract, open point 9). The coach asks the worker to restate that amount in the host currency, or the rates are added. The rubric never guesses a rate.

## The five factors

Each factor turns one measured figure into 0 to 100 points. The points between two anchors are on a straight line: for a figure `x` between anchors `(x0, p0)` and `(x1, p1)`, `points = p0 + (p1 - p0) * (x - x0) / (x1 - x0)`. Below the first anchor the points of the first apply; above the last, those of the last. Each factor's points are then **rounded half up to a whole number** and that whole number is what is reported and weighted.

| Factor id | Weight | Measures |
|---|---|---|
| `debt_to_income` | 0.30 | Months of pay still owed |
| `emergency_buffer` | 0.25 | Months the savings last |
| `remittance_ratio` | 0.15 | Share of pay the worker plans to send home |
| `recruitment_fee_vs_cap` | 0.20 | What was paid to a recruiter, against what the host's law lets an agent charge |
| `banked_status` | 0.10 | A bank account or wallet |

The weights are the ones the contract samples already carry (they add up to 1). Debt weighs most because it decides how much of the first months' pay is already spoken for; the fee comes next because an illegal or inflated fee is also what creates most of the debt.

### 1. `debt_to_income` (0.30)

`value = debt_outstanding / monthly_salary` (months of pay owed, in the host currency). No debt is 0.

| Months owed | Points |
|---|---|
| 0 | 100 |
| 1 | 85 |
| 3 | 60 |
| 6 | 30 |
| 12 or more | 0 |

**Interest penalty**, only when there is a debt: turn the rate into a yearly figure (a monthly rate times 12, simple, so 3% a month is 36%). Subtract 10 points if the yearly rate is 24% or more, 20 if it is 48% or more. The result is not below 0. A debt at 12% a year or a family loan at 0% has no penalty.

### 2. `emergency_buffer` (0.25)

`essentials` is the sum of the **typical** figures of `accommodation`, `food`, `transport` and `phone_data` for the destination in `cost_baselines`, using the job-type override when there is one. `mandatory_deductions` is a share of pay, not an amount, so it is left out.

`outgoings = essentials + monthly remittance_target`, and never below a quarter of the monthly salary (so a worker whose employer pays for everything and who sends nothing does not divide by zero).

`value = savings / outgoings` (months).

| Months | Points |
|---|---|
| 0 | 0 |
| 1 | 35 |
| 3 | 75 |
| 6 or more | 100 |

### 3. `remittance_ratio` (0.15)

`value = remittance_target / monthly_salary`.

| Share of pay | Points |
|---|---|
| 0.30 or less | 100 |
| 0.50 | 70 |
| 0.70 | 30 |
| 0.90 or more | 0 |

**Shortfall cap.** If `monthly_salary - essentials - remittance_target` is below 0, the points are at most 25: the worker plans to send more than they can afford after living costs. (Sending nothing is not penalised: the score measures readiness, not generosity.)

### 4. `recruitment_fee_vs_cap` (0.20)

`value = recruitment_fee_paid / monthly_salary` (months of pay paid as a fee). The cap is also written in months of pay (next section). `excess = max(0, value - cap_months)`.

| Excess months | Points |
|---|---|
| 0 (at or under the cap) | 100 |
| 0.25 | 75 |
| 0.5 | 55 |
| 1 | 30 |
| 2 or more | 0 |

### 5. `banked_status` (0.10)

| Answer | Points | `value` |
|---|---|---|
| `both` | 100 | 1.0 |
| `bank_account` | 90 | 1.0 |
| `mobile_wallet` | 55 | 0.5 |
| `none` | 0 | 0.0 |

A wallet can receive and send money but usually cannot hold a regulated deposit or a loan record, which is why it scores below a bank account.

### The recruitment-fee cap, by host

The cap is the most the host's law lets an agent charge a worker, written as months of the worker's pay. The engine reads it from `labor_laws/{host}/rules/recruitment_fees` (`variants[].limits`); the table shows what the files say on 2026-10-09 (`data-scripts/data/source/labor-laws/`).

| Host | Law (labor-law file) | `cap_months` |
|---|---|---|
| SG | At most one month's salary per year of the pass or contract, up to 2 months (`maximum_agency_fee`, 2 months) | **2.0**. The contract length is not asked, so the most generous cap is used: a fee flagged as over the cap is over it for certain |
| MY | A placement fee of at most one month's basic wages (`placement_fee_non_citizen`, 1 month) | **1.0** |
| HK | A licensed agency may charge at most 10% of the first month's wages (`maximum_commission`, 10 percent) | **0.10** |
| KR | Permit-system hiring is through the government; taking money from an applicant is a crime. No number | **0** |
| JP | A placement provider may not charge a job seeker; a supervising organisation may not charge a technical intern. No number | **0** |
| AU | An employer cannot make a worker pay unreasonably for a job; paying for sponsorship is illegal. No cap found | **0**, with low confidence (D-199) |

Rule for the engine: a `unit` of `months` is used as it is, `percent` is divided by 100, and a rule with no number gives 0. Fees paid in the home country fall under the home country's law, so the explanation says "more than the host country usually allows an agent to charge", not "illegal".

## The total and the bands

`total = round_half_up( sum of weight x points )`, using the whole-number points of each factor. Because the points are whole numbers and the weights have two decimals, the total can be worked out by hand and checked against `round(sum(score * weight))` in the contract samples.

(Round half up means 90.5 is 91. Python's built-in `round()` rounds half to even and gives 90: use `math.floor(x + 0.5)`.)

| Band id | Total |
|---|---|
| `needs_work` | 0 to 39 |
| `getting_ready` | 40 to 69 |
| `well_prepared` | 70 to 100 |

These are the ids and cut-offs the contract samples already use, so the screens and mocks need no change.

**Floor rule.** If any single factor has fewer than 20 points, the band is at most `getting_ready`, even when the total is 70 or more. A worker with a debt they cannot carry should not be told they are well prepared because their other four factors are good. The total itself is not changed.

## Worked example

The mid sample of the contract (`docs/mocks/coach/session-04-plan-mid.json`): an Indian care worker going to Australia. One illustrative rate is used: **1 AUD = 54 INR** (not a real rate).

| Answer | Value | In AUD |
|---|---|---|
| Salary | 4,200 AUD a month | 4,200 |
| Remittance target | 900 AUD a month | 900 |
| Recruitment fee | 150,000 INR | 2,777.78 |
| Debt | 120,000 INR at 3% a month | 2,222.22 |
| Savings | 25,000 INR | 462.96 |
| Account | `bank_account` | |

Essential costs for AU (`cost_baselines/AU`, typical): 1,257 + 600 + 163 + 42 = **2,062**.

| Factor | Figure | Working | Points |
|---|---|---|---|
| `debt_to_income` | 2,222.22 / 4,200 = **0.53** months | 100 - 0.5291 x 15 = 92.06. Interest 3 x 12 = 36% a year, at least 24%, so minus 10 = 82.06 | **82** |
| `emergency_buffer` | outgoings 2,062 + 900 = 2,962; 462.96 / 2,962 = **0.16** months | 0.1563 x 35 | **5** |
| `remittance_ratio` | 900 / 4,200 = **0.21** | At most 0.30. Leftover 4,200 - 2,062 - 900 = 1,238, not a shortfall | **100** |
| `recruitment_fee_vs_cap` | 2,777.78 / 4,200 = **0.66** months; AU cap 0, excess 0.66 | 55 - (0.6614 - 0.5) / 0.5 x 25 = 46.93 | **47** |
| `banked_status` | **1.0** | | **90** |

Total: 0.30 x 82 + 0.25 x 5 + 0.15 x 100 + 0.20 x 47 + 0.10 x 90 = 24.6 + 1.25 + 15 + 9.4 + 9 = 59.25, so **59**, band **`getting_ready`**. The lowest factor is 5, below 20, so the floor rule would cap the band at `getting_ready` too. The biggest chance to improve is the buffer: three more months of savings would add about 18 points.

### The three samples of the contract under this rubric

The samples were written before the rubric and carry placeholder points (D-200). Under the rubric:

| Sample | Debt | Buffer | Remittance | Fee | Banked | Total | Band | Sample says |
|---|---|---|---|---|---|---|---|---|
| `session-04-plan-mid` (AU, care) | 82 | 5 | 100 | 47 | 90 | **59** | `getting_ready` | 57, same band |
| `session-05-plan-low` (SG, domestic, rate 1) | 33 | 0 | 47 | 0 | 0 | **17** | `needs_work` | 7, same band |
| `session-06-plan-high` (KR, manufacturing) | 100 | 62 | 100 | 100 | 100 | **91** | `well_prepared` | 91, same |

The `low` row: debt 2,400 SGD / 650 = 3.69 months gives 53.08, minus 20 for 5% a month (60% a year) = 33. Essentials for a live-in SG domestic worker are 0 + 0 + 100 + 12 = 112. Remittance 400 / 650 = 0.62 gives 46.92. Fee 3,000 / 650 = 4.62 months, excess 2.62, so 0. The `high` row: essentials for KR are 301,963 + 250,000 + 75,000 + 45,000 = 671,963; outgoings 1,271,963; 3,000,000 / 1,271,963 = 2.36 months gives 62.17; the total is 90.5, which rounds half up to 91.

## What the score does not see

- **A repayment amount or who the lender is.** The interview does not ask them, so the debt factor uses the balance and the rate (D-172). If this proves too blunt, add an optional slot and raise the rubric version.
- **Dependents.** A worker with four dependents and one with none get the same remittance factor. The plan handles the difference.
- **Income tax and the deductions from pay.** `mandatory_deductions` is a share of pay and is not taken off the salary here; the plan applies it.
- **Pay that is not the figure stated.** The score trusts the salary the worker gives (or the contract prefill the worker confirmed).
- **The departure date.** It does not change readiness; it sets the plan's timing.

## For the screen and for the tests

- **Words.** The explanation of a factor ("what this means", "how to improve") is chosen by factor and level, not written per score: level `strong` for 70 or more points, `fair` for 40 to 69, `weak` for under 40. NF-FC-020 and NF-FC-023 hold the six languages.
- **Hand-computed checks (NF-FC-007, NF-FC-011).** Each persona's expected score is worked out with this page and stored in `backend/tests/fixtures/coach_personas.json`; the engine must match all twelve (see `docs/runbooks/NF-FC-007-coach-personas.md`). Properties to test: the total is a whole number from 0 to 100; each factor's points are a whole number from 0 to 100; the weights add up to 1; more debt, less savings, a higher fee or no account never raises the score; the same answers always give the same score; the band follows the table and the floor rule.
- **Rounding of values.** `value` is reported to 2 decimals; the points are whole numbers.

## Changing the rubric

Edit this page and raise `rubric_version` in the same pull request. A plan stores the version it was scored with (`coach_plans.score.rubric_version`), so an old plan is never re-scored by a new rubric.
