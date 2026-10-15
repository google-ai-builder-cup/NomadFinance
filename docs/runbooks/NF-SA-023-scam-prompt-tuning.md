# NF-SA-023 — Prompt tuning to hit the eval threshold: measured, no change needed

## Summary

The tracker asks to use the eval report to fix the weakest classes and languages and to bump the prompt version. The threshold was **already met by the maximum**: the first live baseline (NF-SA-021, `docs/evals/scam-eval-2026-10-07.md`) scored 120 of 120, F1 1.000 overall and in every language. With nothing weak in the report there was nothing to tune from, and tuning a prompt against a set it already passes perfectly can only break it. So this task measured what the baseline could not show, and the result is that **`scam/classify.v2` stays as it is and no version is bumped.**

| | |
|---|---|
| Golden set again, with confidence now in the report | **120 of 120 again** (a second live run; the same 120 messages, the same answers): F1 1.000 overall and in each of the six languages. The report was regenerated with the new Confidence section, so `docs/evals/scam-eval-2026-10-07.md` now replaces the first baseline file of the same date |
| **New stress set**: 30 harder messages (16 harmless look-alikes, 14 scams without the obvious words; English and Hindi) | **30 of 30 on scam against benign: F1 1.000** (14 scams caught, 16 harmless messages passed, no false alarm, no miss). One scam was filed under a different type (the prize message that asks only for a reply, `lottery`, called `other_scam`). Report: `docs/evals/scam-eval-scam_stress_en_hi-2026-10-07.md` |
| Confidence | **Not a problem.** Golden set: right scams lowest 0.80, median 1.00; right benign messages lowest 0.90, median 1.00; nothing under 0.7. Stress set: scams lowest 0.80, benign lowest 0.80, nothing under 0.7, and the one wrong type was given at 0.80 (so it still carries a verdict and a warning). No right answer would show "we are not fully sure" |
| Prompt change | **None.** `classify.v2` is unchanged; no `v3` |

## What was added

| File | What |
|---|---|
| `data-scripts/evals/scam_stress_en_hi.jsonl` (new) | The 30 messages, in the golden row format, ids from `gold-en-101` and `gold-hi-101` so they never clash with a golden id. Curator `NF`, reviewer `PP` |
| `data-scripts/evals/run_scam_eval.py` | `--rows PATH` scores one file instead of the three golden sets, and the bar then applies to the languages that file has. The report is named after the file |
| `data-scripts/src/scam_eval/metrics.py`, `report.py` | A **Confidence** section in every report: how sure the classifier said it was for right scams, right benign messages and wrong answers, and how many answers fall below 0.7 (the point at which the screen tells the worker it is not fully sure). `gate(..., only_present=True)` and a `source` line in the report |
| `data-scripts/tests/` | 13 new tests: the confidence figures, the gate on a two-language set, the report's new section and source, scoring one file, a file that does not parse, and the shape of the stress set |
| `docs/evals/scam-golden-set.md`, `docs/gemini-prompts.md` | The stress set; "when to change the classifier prompt, and when not"; the new result |
| `docs/evals/scam-eval-2026-10-07.md`, `docs/evals/scam-eval-scam_stress_en_hi-2026-10-07.md` | The two reports |

No backend, prompt, frontend, workflow or other shared file changed.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | "Fix the weakest class" when none is weak | Measured what the baseline could not show instead: confidence, and harder cases |
| 2 | "Prompt version bumped" | **Not done, on purpose.** A new version makes every stored check ineligible for the cache (`prompt_versions`), so each repeated message calls Gemini again, for no change in behaviour. The rule is now in `docs/gemini-prompts.md` |
| 3 | Few-shot examples from the golden messages | Not added: examples written from a set a prompt already passes make the set a weaker test and the prompt no better |
| 4 | The stress set's labels | Written for this task, to the rubric in `docs/evals/scam-golden-set.md`. `reviewed_by` is `PP` as the task owner's sign-off. An independent spot-check and a Hindi read are open (D-166) |
| 5 | A label the first run disagreed with | The boss-impersonation message (gold-en-120) was first labelled `authority_impersonation`. The rubric files a message that "pretends to be someone the worker knows" under `other_scam`, which is what the classifier said, so the **label** was corrected and the set scored again. The prize message that asks only for a reply (gold-en-117, labelled `lottery`, called `other_scam`) is left as a real type difference |

## Reading the results

- **The bar is on scam against benign.** Which type a scam is filed under is reported but not gated (D-129): a type has 6 to 12 messages in the golden sets, 0 to 2 in the stress set, so one message moves it a long way.
- **No false alarm and no missed scam on 150 messages**, including 16 harmless look-alikes written to be harder than the golden ones (a bank's own fraud alert, a payroll notice, a friend asking to borrow money).
- **A perfect score is a baseline, not a guarantee.** Both sets are small, invented, and written by the team; native-speaker reads are open (D-127, D-130, D-132, D-166). They tell us the prompt is not weak on the cases we could think of. Real messages will be the next test.

## When this should be revisited

Change `classify` for a failure on something it has not seen: a real missed scam or false alarm, a new stress-set row that fails, or a confidence problem. Then follow "After you change a scam prompt" in `docs/gemini-prompts.md`, and put the failing message in the stress set first, so the change is scored on it.

## Manual test

```bash
cd data-scripts
python -m evals.run_scam_eval --rows evals/scam_stress_en_hi.jsonl --limit 6   # 6 calls, nothing scored
python -m evals.run_scam_eval --rows evals/scam_stress_en_hi.jsonl --rpm 10    # 30 calls, about 4 minutes
python -m evals.run_scam_eval --rpm 10                                         # the golden sets: 120 calls
```

Needs `GEMINI_API_KEY` in the shell (for the Cloud key: `gcloud secrets versions access latest --secret=gemini-api-key --project nomadfinance-prod`) and the backend's packages in the same environment. Exit code 0 means the bar is met, 1 that it is not, 2 that a message got no answer.

## Checks run (2026-10-07 and 2026-10-08)

| Check | Result |
|---|---|
| `black`, `ruff` on `data-scripts` | clean |
| `pytest tests/test_scam_*.py` in `data-scripts/` | 244 passed, 13 new |
| `mypy` on the touched files | no new error (the two messages left are in `embedding.py` and `pandas` stubs, which were there before) |
| Live golden run, 120 calls, `gemini-3.1-flash-lite`, `scam.classify v2` | 120 of 120; F1 1.000 in every group |
| Live stress run, 30 calls | 30 of 30 on scam against benign; 1 type difference |
| Break the code on purpose | not applicable: no behaviour of the app changed |

**Not verified:** the stress set against a second reviewer (D-166) and in Hindi by a native speaker; real messages, which are the next test. The Gemini key is on the free tier, so the live runs took about 25 minutes each at `--rpm 10`.

## Definition of Done (Backend, prompt change)

- [x] Eval re-run recorded in `docs/evals/` showing the threshold met (golden and stress)
- [x] Confidence measured and recorded
- [x] Prompt version bumped only if the prompt changed: it did not
- [x] The injection suite not affected (no prompt change)
- [ ] Independent spot-check of the stress set, and a Hindi read (D-166)
- [ ] Reviewed by a teammate (Pranjal, per the tracker, for Aditya's task)

## Follow-up on this branch: Scam Check and Financial Coach as pillars 5 and 6

Asked for after the work above, on the same branch: show Scam Check on the landing page and the dashboard, and say six pillars instead of four everywhere.

| What | Change |
|---|---|
| Landing page | The pillars section shows **six cards** (3 x 2 on a wide screen, a swipeable row on a phone): the four of v1.0, then Financial Coach and Scam Check. The heading and label say "Six", and the header link in Hindi and Indonesian too. Signed out, all six lead to sign-in, as the first four did |
| Dashboard | A card for each of the two that is **on for the worker** (`ModuleWidget`), after the four. A worker the flag is off for sees no card, the same rule as the sidebar and the tab bar, so a card never links to a page that would send them back |
| Colours and pictures | Two new pillar colours (orange for Scam Check, purple for Financial Coach, light and dark theme) in `tokens.css`, `tailwind.config.ts` and `utils/pillars.ts`, and two illustrations (`ModulePillarArt.tsx`). The shared parts of the illustrations moved out of `PillarIllustration.tsx` into `pillarArtTokens.ts` and `PillarArtParts.tsx` |
| Lists | `MODULE_ITEMS` now carries the pillar name and description; `ALL_PILLAR_ITEMS` (six, for the landing page) and `visiblePillarItems(flags)` are new. `PILLAR_ITEMS`, `NAV_ITEMS` and `pillarForPath` still mean the four, so page headers and analytics are unchanged |
| Strings | 20 new keys in all 6 languages; the Coach copy was written from the original design (D-167) |
| README | "Six interconnected pillars", with Scam Check and Financial Coach as items 5 and 6 |
| Not changed | The Ecosystem diagram (it shows how the first four pillars feed each other), the original design (which says four) and the "four Gemini tiers" line (a different four) |

Checks: `tsc`, ESLint, Prettier and `check-i18n` clean; **816 frontend tests pass** (10 new: the six pillars and their flags, the landing page's six cards, the dashboard's cards by flag); `pnpm build` passes; the Playwright smoke test passes; the landing page was checked in the browser at desktop width. **Not verified:** the signed-in dashboard cards in a browser (they need a sign-in and the flag), dark mode, and a phone width.

## Commit

Branch: `feature/NF-SA-023-scam-prompt-tuning` (already checked out).

```bash
git commit -m "test(scam): add stress set and confidence report, keep classify v2" -m "Refs: NF-SA-023"
```

PR title: `test(scam): stress set and confidence report for the verdict classifier, no prompt change (NF-SA-023)`
