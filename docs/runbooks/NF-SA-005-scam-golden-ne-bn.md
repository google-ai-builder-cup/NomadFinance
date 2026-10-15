# NF-SA-005 — Scam golden eval set: Nepali and Bengali

## Summary

40 labelled messages, 20 Nepali and 20 Bengali, that a correct Scam Analyzer should classify in a known way: **28 scams and 12 benign look-alikes**, each with a scam type, tactics, a risk level and a one-line reason. It is the third of three sets (NF-SA-003 English and Hindi, NF-SA-004 Tagalog and Indonesian) and uses the format and the checker NF-SA-003 defined, unchanged. The eval runner (NF-SA-014) scores the analyzer against it.

The rules for the labels are in [`docs/evals/scam-golden-set.md`](../evals/scam-golden-set.md). The file is `data-scripts/evals/scam_golden_ne_bn.jsonl`. Not in this task: the runner, and any analyzer.

This task also did the second review the tracker names for NF-SA-003: ten of Devam's English and Hindi labels (below).

## What is in it

| | Nepali | Bengali |
|---|---|---|
| Scams | 14 | 14 |
| Benign look-alikes | 6 | 6 |
| Fake job offer / illegal recruitment fee / remittance or OTP phishing / loan app / authority impersonation / investment or romance | 2 each | 2 each |
| Lottery / other scam | 1 each | 1 each |
| Risk of the scams: high / medium / low | 10 / 3 / 1 | 10 / 3 / 1 |
| `script`: `native` / `latin` | 17 / 3 | 17 / 3 |
| `corridor_id` | none on any row | SG-IN 2, AU-IN 2, none 16 |

Tactics used in the 28 scams: urgency 22, scarcity 10, authority 10, fear 6, reciprocity 4, social proof 2. Channels: 18 SMS, 17 WhatsApp, 3 email, 2 social. Risk of the 28 scams: 20 high, 6 medium, 2 low.

The 12 benign messages each imitate a scam type and get it right, and between them they imitate all eight types:

| Look-alike | Nepali | Bengali |
|---|---|---|
| Real one-time password that warns not to share it | yes | yes |
| Agency interview invitation: passport shown at the counter, no fee | yes | yes |
| Lender or cooperative due-date reminder with an offer to talk | yes | yes |
| Embassy or high-commission passport reminder that points to the official site | yes (Seoul) | yes (Singapore) |
| Colleague on a new number who asks for nothing (typed in Latin letters) | yes | |
| In-person company raffle with no fee | yes | |
| Bank deposit-maturity notice that never asks for a PIN or code | | yes |
| Courier delivery notice with no fee | | yes |

## Corridors

**This set deliberately has almost no corridor.** None of the six corridors starts in Nepal or Bangladesh (`KR→NP` was replaced by `AU→IN` in NF-P1-015, and D-102 says it is not coming back), so a Nepali row carries `corridor_id: null` and puts the host country in the text instead (Malaysia, Japan, Korea, Australia, Hong Kong, Singapore). A Bengali row carries `SG-IN` or `AU-IN` only for a worker from West Bengal, and `null` for a worker from Bangladesh. Across the three sets all six corridors already appear (SG-PH, SG-IN, AU-IN, MY-ID, JP-PH, AU-PH in the English, Hindi, Tagalog and Indonesian rows), and no set has to cover them all: the analyzer is scored on scam against benign, not on the route.

The tracker row for this task said "KR→NP corridor". It was reworded in the local tracker to "Nepali- and Bengali-speaking workers in the six host countries", and the `corridor_id` rule in the rubric now says the same (D-102).

## The messages are invented

No real message is used. Every link ends in `.example`, every phone and account number holds a run of six zeros, and the agencies, banks, apps and people are fictional (`हिमाल सेभ बैंक`, `টাকাপে`, `নদীপার ব্যাংক`, `हिमाल म्यानपावर`, `আলো ম্যানপাওয়ার`, `Ramesh`). Where a scam imitates a real authority it is named the way real scams name it (immigration, the embassy, the police). The two benign embassy reminders name the real offices, as the earlier sets do, and ask for nothing. The checker refuses a row that breaks any of this, and it reads Devanagari and Bengali digits the same as ASCII ones: a negative test with a made-up number written in Devanagari digits was refused.

Two things the Latin-letter rows are for: workers often type Nepali and Bengali in Latin letters ("Roman Nepali", "Banglish"), and the analyzer must read them. They are the weakest rows for wording, so they are the first for a native speaker to check (D-132).

## Files

| File | Purpose |
|---|---|
| `data-scripts/evals/scam_golden_ne_bn.jsonl` (new) | The 40 rows |
| `data-scripts/tests/test_scam_golden_ne_bn.py` (new) | 11 tests: the committed set passes, the planned mix per language, tactics, 17 native and 3 Latin rows each, each native row in its own script, corridors, all six hosts named, no four in a row of one class, the command |
| `data-scripts/evals/scam_golden_en_hi.jsonl` | `reviewed_by` set to `PP` on 7 rows (below). Nothing else changed |
| `data-scripts/README.md`, `docs/evals/scam-golden-set.md` | A paragraph; the `script` and `corridor_id` rows |

No change to the checker, the schema or any shared file. The file name is exactly `scam_golden_ne_bn.jsonl`, as Devam asked.

## Run it

From `data-scripts/`, virtual environment active (see the README, "Setup"):

```bash
python -m src.validators.scam_golden evals/scam_golden_ne_bn.jsonl
```

Expected: `OK   scam_golden_ne_bn.jsonl: 40 rows, 28 scam, 12 benign, 0 reviewed`. A bad row prints `FAIL`, then the line, the field and the reason.

## The 10 labels to review (Aditya)

`python -m src.validators.scam_golden evals/scam_golden_ne_bn.jsonl --spot-check 10` prints this same list every time, each with its text, label and rationale:

| Row | Label |
|---|---|
| `gold-bn-001` | fake job offer, scarcity and urgency, high |
| `gold-bn-002` | illegal recruitment fee, urgency and scarcity, high |
| `gold-bn-003` | benign, resembles remittance or OTP phishing |
| `gold-bn-019` | other scam, urgency, high (typed in Latin letters) |
| `gold-ne-003` | benign, resembles remittance or OTP phishing |
| `gold-ne-004` | remittance or OTP phishing, authority and urgency, high |
| `gold-ne-010` | benign, resembles illegal recruitment fee |
| `gold-ne-013` | lottery, authority, low |
| `gold-ne-015` | loan app trap, urgency and scarcity, medium |
| `gold-ne-018` | investment or romance, reciprocity and urgency, high |

For each, the reviewer asks the five questions in the rubric ("Reviewing a set") and puts their initials in `reviewed_by` on that row. A reviewer who does not read the language checks the English rationale and the label against the rubric and says so in the pull request. Before the pull request merges:

```bash
python -m src.validators.scam_golden evals/scam_golden_ne_bn.jsonl --require-reviewed 10
```

It fails until ten rows carry a reviewer's initials, and refuses a row reviewed by its own curator (`PP`).

## My review of Devam's English and Hindi labels (D-128)

The tracker names me as the second reviewer of NF-SA-003. I ran `--spot-check 10` on `scam_golden_en_hi.jsonl` and judged each of the ten by the rubric's five questions. **I agree with seven and put `PP` in `reviewed_by` on them. Three need Devam.**

| Row | Verdict |
|---|---|
| `gold-en-003` benign OTP | Agree |
| `gold-en-006` benign agency interview | Agree |
| `gold-hi-004` remittance or OTP phishing, urgency and fear, high | Agree |
| `gold-hi-013` benign lender reminder | Agree |
| `gold-hi-015` loan app trap, fear and urgency, high | Agree |
| `gold-hi-018` investment or romance, social proof and scarcity, medium | Agree |
| `gold-hi-019` other scam, urgency and authority, high | Agree |
| **`gold-en-010`** lottery, `authority`, low | **Type and risk right; the tactic is not shown.** "Your number won 25,000 SGD in the monthly draw. Reply WIN" does not pretend to be anyone official, and the rubric says not to add a tactic the text does not show. The Tagalog and Indonesian lotteries do say "official" and "national". `gold-hi-010` has the same wording and the same issue (it is not in my ten) |
| **`gold-en-012`** illegal recruitment fee, `urgency` and `authority`, high | **Type, urgency and risk right; `authority` is not shown.** The sender asks for a placement fee "to release your visa" but does not claim to be an official body |
| **`gold-hi-001`** fake job offer, `scarcity` and `urgency`, high | **Type, scarcity and risk right; `urgency` is not shown.** "Only 3 places" is scarcity; the message has no deadline (the English twin, `gold-en-001`, says "today") |

For each of the three, either the tactic changes or the wording gets the missing element, then I mark the row. That is Devam's call and was not changed here. `--require-reviewed 10` passes for the English and Hindi set after that. I read the Hindi rows but am not a native Hindi speaker (D-127).

One finding about my own set, from applying the same standard: `gold-bn-019` first listed `fear`, but a family emergency is pressure, not a threat, so it is `urgency` only, like its Nepali counterpart.

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black --check`, `ruff check`, `mypy src tests` (data-scripts) | clean |
| `pytest` (data-scripts) | **338 passed**; 11 of them are new |
| The committed file | 40 rows, 28 scam, 12 benign; every scam type, tactic and risk level present; all 8 types imitated across the benign rows |
| Every checker rule on this file | A real link, a real-looking number, a number in Devanagari digits and a bare domain were each refused when planted in a copy; a row reviewed by its own curator was refused |
| `python -m src.validators.scam_golden` (all three files) | OK on all three |

## Not done, and why

- **Not reviewed by a second person yet** (D-133). The tracker's acceptance is not met until Aditya marks ten rows.
- **Written without native speakers** (D-132), by a teammate who does not read Nepali or Bengali natively. Natural wording is part of what the set measures, and these two languages are among those that must reach F1 0.75 for the analyzer to ship. A native read of all 40 rows is the most valuable next step.
- **Three English and Hindi labels are open** (above).
- **No analyzer has seen these messages.** The set is scored by NF-SA-014 once the classifier exists (NF-SA-007).
- **Per-type numbers will be noisy**: one or two messages per type per language. Judge the analyzer on scam-versus-benign F1 per language, as the tracker says, and do not tune on one type's number (D-129).

## Definition of Done (curated dataset)

- [x] 40 rows in `data-scripts/evals/scam_golden_ne_bn.jsonl` passing schema validation
- [x] Every row has a type or none, tactics, risk level and a rationale; curator initials recorded
- [x] Validated against a schema; the checker is read-only and idempotent
- [x] Synthetic only, enforced by the checker
- [ ] A second teammate spot-checked 10 labels (D-133)

## Commit

Branch: `feature/NF-SA-005-data-scam-golden-ne-bn`.

```bash
git commit -m "feat(scam): add nepali and bengali golden eval set" -m "Refs: NF-SA-005"
```

PR title: `feat(scam): Nepali and Bengali golden eval set, and a review of ten English and Hindi labels (NF-SA-005)`
