# NF-FC-006 — Coach preparedness scoring rubric

> The rubric page this task wrote has since been removed from the repository; the rubric itself lives in `backend/app/services/coach/scoring.py`, and the page stays in git history.

## Summary

The rule that turns a worker's answers into the 0 to 100 preparedness score of the Financial Coach, written down before any code uses it. It was a document, not a program: the page held the formula, the weights, the bands and a worked example. The scoring engine (NF-FC-011) and the twelve test personas (NF-FC-007) are built from it, and the score screen (NF-FC-020) shows its factors.

The tracker row: *Define the 0 to 100 preparedness score: debt-to-income, months of emergency buffer, remittance-to-income ratio, recruitment fee vs legal cap (from labor_laws), banked / unbanked. Document weights and bands.* Finish line: *a rubric page with formula, weights, worked example; rubric is deterministic and model-free.*

The tracker lists this task for Pranjal; Aditya did it.

## The rubric in one table

Version 1. Each factor turns one measured figure into points out of 100 (a straight line between listed anchors); points are rounded half up to whole numbers; the total is the half-up rounded weighted sum.

| Factor | Weight | Figure | Anchors (figure → points) |
|---|---|---|---|
| `debt_to_income` | 0.30 | Debt in months of pay | 0 → 100, 1 → 85, 3 → 60, 6 → 30, 12 → 0. Minus 10 if the yearly interest is at least 24%, minus 20 if at least 48% |
| `emergency_buffer` | 0.25 | Savings ÷ (typical essential costs + remittance), at least a quarter of pay | 0 → 0, 1 → 35, 3 → 75, 6 → 100 |
| `remittance_ratio` | 0.15 | Remittance ÷ pay | up to 0.30 → 100, 0.50 → 70, 0.70 → 30, 0.90 → 0. At most 25 if pay minus essentials minus remittance is below 0 |
| `recruitment_fee_vs_cap` | 0.20 | Fee ÷ pay, less the host's legal cap in months | at or under the cap → 100, +0.25 → 75, +0.5 → 55, +1 → 30, +2 → 0 |
| `banked_status` | 0.10 | Account kind | both 100, bank account 90, wallet 55, none 0 |

**Bands:** `needs_work` 0 to 39, `getting_ready` 40 to 69, `well_prepared` 70 to 100. **Floor rule:** if any factor has fewer than 20 points, the band is at most `getting_ready`; the total is not changed.

**Fee cap by host** (from `labor_laws/{host}/rules/recruitment_fees`, as the files say on 2026-10-09): SG 2 months (the most generous reading, because contract length is not asked), MY 1 month, HK 10% of the first month, KR 0, JP 0, AU 0 (low confidence: "no cap found", D-199).

**Everything is converted into the host currency first**, with the stored corridor rate; a currency with no rate (NPR, BDT today, D-170) means the score is not computed and the coach asks for the amount in the host currency. The weights are the ones the API contract samples already carried, so the screens and mocks needed no change.

## Why it is built this way

- **Debt weighs most (0.30)**: it decides how much of the first months' pay is already spoken for. The **fee comes next (0.20)** because an excessive or illegal fee is also what creates most of the debt.
- **Whole-number points**, so the total can be worked out by hand and checked against `round(sum(score x weight))` in the contract samples.
- **Floor rule**: a worker with a debt they cannot carry should not be told they are "well prepared" because the other four factors are good.
- **Generous fee caps**: when the law is unclear, the cap is the higher one, so a fee flagged as over the cap is over it for certain. A fee paid in the home country falls under the home country's law, so the explanation says "more than the host country usually allows an agent to charge", never "illegal".
- **No model, no clock, no randomness**: the same answers, rates and caps always give the same score.

## What changed

| File | Change |
|---|---|
| `docs/api/v2-coach.md` | The `band` row and open point 2 now point to the rubric (the band ids and cut-offs are fixed; the sample totals are still placeholders) |
| `docs/data-model/collections/coach.md` | The `score` row points to the rubric |

No code, no tracker, no shared file.

## The worked example

The mid sample of the contract (an Indian care worker going to Australia), with one illustrative rate, 1 AUD = 54 INR (not a real rate): salary AUD 4,200, remittance 900, fee INR 150,000, debt INR 120,000 at 3% a month, savings INR 25,000, a bank account. Essential costs for AU are 1,257 + 600 + 163 + 42 = 2,062.

| Factor | Figure | Points |
|---|---|---|
| Debt | 0.53 months; 100 - 0.5291 x 15 = 92.06; 36% a year, minus 10 | 82 |
| Buffer | 0.16 months (AUD 462.96 ÷ 2,962) | 5 |
| Remittance | 0.21 | 100 |
| Fee | 0.66 months over the Australian cap of 0; 55 - 0.3228 x 25 = 46.93 | 47 |
| Banked | bank account | 90 |

Total: 0.30 x 82 + 0.25 x 5 + 0.15 x 100 + 0.20 x 47 + 0.10 x 90 = 59.25, so **59**, `getting_ready`.

The three samples of the contract under the rubric: mid **59** (sample says 57), low **17** (7), high **91** (91). Every band is the same; D-200 lists aligning the numbers.

## Check it yourself

1. Work the example above with a calculator; it should give 59.
2. The plain copy of the rubric used by the tests reproduces the three worked examples of the page (59, 17, 91) and the twelve personas' stored scores:

   ```bash
   # from backend/, virtual environment active
   python -m pytest tests/unit/test_coach_personas.py -q
   ```

   Expect `29 passed`.

## Checks run (2026-10-09)

| Check | Result |
|---|---|
| The three worked examples of the page | Re-computed by a script written from the page: 59, 17 and 91, with the factor points listed in the page |
| Personas and the plain rubric copy | `tests/unit/test_coach_personas.py`: 29 passed |
| The page's statements about the files | The fee caps match the labor-law files; the weights match the contract samples (they add up to 1) |

**Not verified:** a second reader's hand check (D-201), the fee caps with the labor-law reviewer (D-199), and the scoring engine against the rubric (NF-FC-011 is not built; the personas' expected scores are the test it must pass).

## Definition of Done

Tracker row: *a rubric page with formula, weights, worked example; rubric is deterministic and model-free.*

- [x] The rubric page existed with the formula, the weights, the bands and a worked example
- [x] Deterministic and model-free (stated in the page; no model call is described anywhere in it)
- [x] Fee cap taken from `labor_laws`, listed per host
- [ ] Second-reader hand check (D-201; the tracker's reviewer is Devam)
- [ ] Fee caps confirmed by the labor-law reviewer (D-199)

## Noticed, not fixed

Left for later: D-199 (the fee caps, AU in particular), D-200 (the 17 sample files in `docs/mocks/coach/` and the `CoachScore` description still carry placeholder points and a "provisional" note), D-201 (second reader; the tracker names Pranjal as owner).

## Commit

Written on `main`. Commit message:

```
docs(coach): add NF-FC-006 runbook
Refs: NF-FC-006
```
