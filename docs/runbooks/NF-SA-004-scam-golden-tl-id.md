# NF-SA-004 — Scam golden eval set: Tagalog and Indonesian

## Summary

40 labelled messages, 20 Tagalog and 20 Indonesian, that a correct Scam Analyzer should classify in a known way: **28 scams and 12 benign look-alikes**, each with a scam type, tactics, a risk level and a one-line reason. It is the second of three sets (NF-SA-003 English and Hindi, NF-SA-005 Nepali and Bengali) and uses the format and the checker NF-SA-003 defined. The eval runner (NF-SA-014) scores the analyzer against it.

The rules for the labels are in [`docs/evals/scam-golden-set.md`](../evals/scam-golden-set.md). The file is `data-scripts/evals/scam_golden_tl_id.jsonl`. Not in this task: the other two sets, the runner, and any analyzer.

## What is in it

| | Tagalog | Indonesian |
|---|---|---|
| Scams | 14 | 14 |
| Benign look-alikes | 6 | 6 |
| Fake job offer / illegal recruitment fee / remittance or OTP phishing / loan app / authority impersonation / investment or romance | 2 each | 2 each |
| Lottery / other scam | 1 each | 1 each |
| Risk of the scams: high / medium / low | 10 / 3 / 1 | 10 / 3 / 1 |
| `script` | `native` on all 20 | `native` on all 20 |
| Routes | SG-PH 10, AU-PH 4, JP-PH 4, none 2 | MY-ID 17, none 3 |

Tactics used in the 28 scams: urgency 19, authority 11, fear 8, scarcity 7, social proof 6, reciprocity 2. Channels: 19 SMS, 15 WhatsApp, 4 email, 2 social. Risk of the 28 scams: 20 high, 6 medium, 2 low.

The 12 benign messages each imitate a scam type and get it right (every type is imitated by at least one across the two languages):

| Look-alike | Tagalog | Indonesian |
|---|---|---|
| Real one-time password that warns not to share it | yes | yes |
| Agency interview invitation: no fee, passport shown at the counter | yes | yes |
| Agency saying no placement fee is owed | yes | |
| Embassy passport reminder that says to use the official site | yes | yes (KBRI) |
| Lender's due-date reminder with an offer to talk | yes | yes (a cooperative) |
| Colleague on a new number who asks for nothing | yes | |
| Bank deposit-maturity notice | | yes |
| In-person company dinner raffle with no fee | | yes |

The routes Devam left for this set (MY-ID and JP-PH) are used. Hindi's `latin` option has no counterpart here: Tagalog and Indonesian are written in Latin letters natively, so every row is `native` (decided with the team lead; the rubric now says so).

## The messages are invented

No real message is used. Every link and address is on `.example`, every phone and account number holds a run of zeros, the agencies, banks, apps and people are fictional (`Lakbay Manpower`, `SendaPay`, `KirimCepat`, `Bank Nusa Raya`, `Koperasi Pekerja Sejahtera`), and where a scam imitates a real authority it is named the way real scams name it (ICA, the embassy, immigration, PDRM, a labour office). The two benign embassy reminders name the real embassy offices, as the NF-SA-003 benign ministry notice does, and ask for nothing. The checker refuses a row that breaks any of this.

One thing to know when adding Indonesian rows: an amount of 8 or more digits without a run of six zeros counts as a number that could be real. `Rp 12.500.000` is refused; `Rp 6.500.000` and `Rp 10.000.000` pass.

## Files

| File | Purpose |
|---|---|
| `data-scripts/evals/scam_golden_tl_id.jsonl` (new) | The 40 rows |
| `data-scripts/tests/test_scam_golden_tl_id.py` (new) | 9 tests: the committed set passes, the planned mix per language, tactics, script, routes, no four in a row of one class, the command |
| `data-scripts/tests/test_scam_golden.py` | The spot-check command test now names its file (it assumed a single file in `evals/`) |
| `data-scripts/README.md` | A paragraph under the golden-set section |
| `docs/evals/scam-golden-set.md` | `script` row: Tagalog and Indonesian are `native` |

No change to the checker, the schema or any shared file.

## Run it

From `data-scripts/`, virtual environment active (see the README, "Setup"):

```bash
python -m src.validators.scam_golden evals/scam_golden_tl_id.jsonl
```

Expected: `OK   scam_golden_tl_id.jsonl: 40 rows, 28 scam, 12 benign, 0 reviewed`. A bad row prints `FAIL`, then the line, the field and the reason.

## The 10 labels to review (second teammate)

`python -m src.validators.scam_golden evals/scam_golden_tl_id.jsonl --spot-check 10` prints this same list every time (fixed seed), each with its text, label and rationale:

| Row | Label |
|---|---|
| `gold-id-003` | fake job offer, scarcity and urgency, high |
| `gold-id-006` | loan app trap, urgency, medium |
| `gold-id-012` | benign, resembles lottery |
| `gold-id-018` | benign, resembles loan app |
| `gold-tl-002` | illegal recruitment fee, urgency and scarcity, high |
| `gold-tl-004` | remittance or OTP phishing, urgency and authority, high |
| `gold-tl-010` | lottery, authority, low |
| `gold-tl-013` | benign, resembles authority impersonation |
| `gold-tl-018` | investment or romance, social proof and scarcity, medium |
| `gold-tl-019` | other scam, urgency, high |

For each, the reviewer asks the five questions in the rubric ("Reviewing a set") and puts their initials in `reviewed_by` on that row. A reviewer who does not read the language checks the English rationale and the label against the rubric and says so in the pull request. Before the pull request merges:

```bash
python -m src.validators.scam_golden evals/scam_golden_tl_id.jsonl --require-reviewed 10
```

It fails until ten rows carry a reviewer's initials, and refuses a row reviewed by its own curator (`AB`).

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black --check`, `ruff check`, `mypy src tests` (data-scripts) | clean |
| `pytest` (data-scripts) | **327 passed**; 9 of them are new |
| The committed file | 40 rows, 28 scam, 12 benign; every scam type, tactic and risk level present; all 8 types imitated across the benign rows |

## Not done, and why

- **Not reviewed by a second person yet** (D-131). The tracker's acceptance is not met until it is.
- **Written without native speakers** (D-130). Natural wording is part of what the set measures.
- **No analyzer has seen these messages.** The set is scored by NF-SA-014 once the classifier exists (NF-SA-007).
- **Per-type numbers will be noisy**: one or two messages per type per language. Judge the analyzer on scam-versus-benign F1 per language, as the tracker says, and do not tune on one type's number.

## Definition of Done (curated dataset)

- [x] 40 rows in `data-scripts/evals/scam_golden_tl_id.jsonl` passing schema validation
- [x] Every row has a type or none, tactics, risk level and a rationale; curator initials recorded
- [x] Validated against a schema; the checker is read-only and idempotent
- [x] Synthetic only, enforced by the checker
- [ ] A second teammate spot-checked 10 labels (D-131)
