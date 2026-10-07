# NF-SA-003 — Scam golden eval set: English and Hindi

## Summary

40 labelled messages, 20 English and 20 Hindi, that a correct Scam Analyzer should classify in a known way: **28 scams and 12 benign look-alikes**, each with a scam type, tactics, a risk level, and a one-line reason. The eval runner (NF-SA-014) will score the analyzer against them; this is the first of three sets (NF-SA-004 Tagalog and Indonesian, NF-SA-005 Nepali and Bengali) and defines the format the other two reuse.

The rules for the labels are in [`docs/evals/scam-golden-set.md`](../evals/scam-golden-set.md). The file is `data-scripts/evals/scam_golden_en_hi.jsonl`.

## What is in it

| | English | Hindi |
|---|---|---|
| Scams | 14 | 14 |
| Benign look-alikes | 6 | 6 |
| Fake job offer / illegal recruitment fee / remittance or OTP phishing / loan app / authority impersonation / investment or romance | 2 each | 2 each |
| Lottery / other scam | 1 each | 1 each |
| Risk of the scams: high / medium / low | 10 / 3 / 1 | 10 / 3 / 1 |
| Typed in Latin letters (Hinglish) | none | 5 of 20 |

Tactics used in the 28 scams: urgency 22, authority 11, fear 9, scarcity 6, social proof 5, reciprocity 2. The benign messages each imitate a scam type: a genuine bank one-time password, an agency saying "you pay no fee", a ministry reminder that says to use the website yourself, a lender's due-date reminder, a bank maturity notice, an interview invitation, a supervisor's shift message, and a friend on a new number with no request for money. Channels: 21 SMS, 14 WhatsApp, 3 email, 2 social. Routes: mostly SG-IN, AU-IN and SG-PH (MY-ID and JP-PH are left for the Tagalog and Indonesian set).

## The messages are invented

Nothing is a real message. Every link is on `.example`, every address is on `.example`, every phone and account number holds a run of zeros, the agencies and people are fictional, and where a scam imitates a real authority it is named the way real scams do (a ministry, a police force, an embassy). The checker refuses a row that breaks this, and it already caught one number of my own that had too few zeros. Details: "The messages are invented" in the rubric page.

## Files

| File | Purpose |
|---|---|
| `data-scripts/evals/scam_golden_en_hi.jsonl` (new) | The 40 rows |
| `data-scripts/src/validators/scam_golden.py` (new) | `GoldenRow` (the schema), `load_rows` (what the eval runner reads), `check_set` (size, mix, coverage), the invented-data check, the spot-check picker and the command |
| `data-scripts/tests/test_scam_golden.py` (new) | 63 tests; validates the committed file, so data CI fails on a bad row |
| `data-scripts/src/config.py` | `EVALS_DIR` |
| `data-scripts/README.md` | A section with the commands |
| `docs/evals/scam-golden-set.md` (new) | The rubric all three sets follow |
| `docs/deferred-items.md` | D-127 to D-129 |

No shared file, no new package, no workflow change.

## Run it

From `data-scripts/`, virtual environment active (see the README, "Setup"):

```bash
python -m src.validators.scam_golden
```

Expected: `OK   scam_golden_en_hi.jsonl: 40 rows, 28 scam, 12 benign, 0 reviewed`. A bad row prints `FAIL`, then the line, the field and the reason.

## The 10 labels to review (second teammate)

The tracker asks a second teammate to spot-check 10 labels, and it names Pranjal. `python -m src.validators.scam_golden --spot-check 10` prints this same list every time (fixed seed), each with its text, label and rationale:

| Row | Label |
|---|---|
| `gold-en-003` | benign, resembles OTP phishing |
| `gold-en-006` | benign, resembles fake job offer |
| `gold-en-010` | lottery, authority, low |
| `gold-en-012` | illegal recruitment fee, urgency and authority, high |
| `gold-hi-001` | fake job offer, scarcity and urgency, high |
| `gold-hi-004` | remittance or OTP phishing, urgency and fear, high |
| `gold-hi-013` | benign, resembles loan app |
| `gold-hi-015` | loan app trap, fear and urgency, high |
| `gold-hi-018` | investment or romance, social proof and scarcity, medium |
| `gold-hi-019` | other scam, urgency and authority, high |

For each, the reviewer asks the five questions in the rubric ("Reviewing a set") and puts their initials in `reviewed_by` on that row (`"reviewed_by": "PP"` at the end of the line). The list is for the file as it is now; if rows are renumbered, run the command again. Before the pull request merges:

```bash
python -m src.validators.scam_golden --require-reviewed 10
```

It fails until ten rows carry a reviewer's initials, and refuses a row reviewed by its own curator.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | One generic checker for every `scam_golden_<lang>_<lang>.jsonl`, in `data-scripts/src/validators/`. | Aditya and Pranjal write the same kind of file at the same time; whoever merges first defines the format, so it is made reusable. If either has already written their own, align to one. |
| 2 | Each benign row names `resembles`. | The report can then say which scam type causes false alarms, which is what tuning needs. |
| 3 | `script` records Latin-letter Hindi. | Real Hindi scams are often Hinglish and the analyzer must read it; a score on Hindi hides a failure on it unless it can be separated. |
| 4 | Labels follow written rules (the rubric), not taste: type by the mechanism being asked, risk by what is at stake, tactics only when the text shows them. | A reviewer can then check a label without asking the curator. |
| 5 | A benign message must be one a careful person would call safe. An ambiguous message was left out. | A look-alike that is merely unclear tests the label, not the analyzer. |
| 6 | The check for invented data lives in the validator, not in a reviewer's attention. | A real link or number in a repository that is public is a harm, and a rule is cheaper than vigilance. |
| 7 | The review is enforced by `--require-reviewed`, run by hand before merging, not in CI. | CI cannot know who reviewed; a flag in the file after the review would make the CI fail the first push. |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `black`, `ruff`, `mypy src tests` (data-scripts) | clean |
| `pytest` (data-scripts) | **318 passed**; 63 of them are new |
| The committed file | 40 rows, 28 scam, 12 benign, every scam type, tactic and risk level present, 7 different benign look-alike types |
| Tampered copies | A bad type, tactic, risk, id, rationale or script, a real-looking link, address or number, a missing scam type, a duplicate, a wrong size, a wrong file name, a bad line of JSON and a self-review each fail with the reason |
| Caught in my own work | A hotline number with four zeros instead of six; two scams ending one block and starting the next, which would have made four scams in a row (the test is "no four in a row of one class") |

## Not done, and why

- **Not reviewed by a second person yet** (D-128). The tracker's acceptance is not met until it is.
- **Hindi was written without a native speaker** (D-127). A natural-sounding message is part of what the set measures.
- **No analyzer has seen these messages.** The set is scored by NF-SA-014 once the classifier exists (NF-SA-007).
- **Per-type and per-language per-type numbers will be noisy** (D-129): one or two messages each.

## Definition of Done (curated dataset)

- [x] 40 rows in `data-scripts/evals/scam_golden_en_hi.jsonl` passing schema validation
- [x] Every row has a type or none, tactics, risk level and a rationale; curator initials recorded
- [x] Validated against a schema; the checker is idempotent (read-only)
- [x] Synthetic only, enforced by the checker
- [ ] A second teammate spot-checked 10 labels (D-128)
- [ ] Reviewed by Pranjal
