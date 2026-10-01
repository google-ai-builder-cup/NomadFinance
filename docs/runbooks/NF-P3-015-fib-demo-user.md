# NF-P3-015 — FIB: Demo User with History

Assigned to Pranjal; built by Aditya.

## Summary

Seeds one fictional demo worker, **Priya** (domestic worker in Singapore, sends money to India, reads Hindi), with 6 months of income, transfers, bills and savings, so the Financial Identity profile and PDF have rich, believable data for the pitch. Data-scripts only: no backend or frontend change.

Not in this task: the other two demo users, Rajesh and Miguel, and the demo Firebase accounts (NF-P3-021, which fills the two empty seed files and reuses this loader), verified-contract income (NF-P3-024), and the FIB screens (NF-P3-016, -017).

## Files

| File | Change |
|---|---|
| `data-scripts/data/seed/users/priya_sg_domestic.json` | Priya's profile fields and 31 entries |
| `data-scripts/src/validators/demo_user.py` (new) | The schema; `python -m src.validators.demo_user` checks every file |
| `data-scripts/src/loaders/seed.py` (was an empty stub) | The loader |
| `data-scripts/src/config.py` | `SEED_USERS_DIR` |
| `data-scripts/tests/test_demo_user_seed.py` (new) | 47 tests |
| `data-scripts/scripts/seed_demo.sh`, `data-scripts/README.md` | The loader is part of the demo seeding; documented |

## What the data looks like

Dates in the file are `months_ago` (0 to 5) and `day`; the loader turns them into real dates relative to the day it runs. Salary is on the 1st, savings the 4th, transfers the 3rd, the phone bill the 8th, the transport top-up the 12th.

| Collection | Entries | Story |
|---|---|---|
| `income` | 9 | Salary of 650 SGD every month, 2 overtime entries (90 SGD) and a festival bonus (150 SGD). All `manual`, `category_source: user`, `verified: false` |
| `transfers` | 6 | About 450 SGD a month on SG-IN. The first three through Ample Transfer (2.5 to 2.6% cost), the last three through Wise (0.7 to 0.8%) with the note "Switched after comparing in Remittance X-Ray". Fees and rate ratios follow the World Bank RPW SG-IN survey (2025 Q1); the mid-market rates are invented. `source: remittance_log`, with the RPW ids |
| `bills` | 12 | Phone (6, one unpaid, the two newest `bill_ocr`), transport (5), one clinic visit (`category_source: user`). The rest have `category_source: model` with a confidence |
| `savings` | 4 | Three deposits (200, 200, 150 SGD) and one withdrawal (80 SGD, "Phone repair") |

Provider names and survey costs are real; everything else (people, employer, amounts, rates, who used which provider when) is invented. `Example ...` names are fictional on purpose.

## What `fib-recompute` makes of it

Checked by running the seeded entries through the backend's own metric code (`profile_metrics.py`, rate 64.8 INR per SGD), on three different run days:

| Run day | Income stability | Savings rate | Remittance consistency | Bill reliability | Overall |
|---|---|---|---|---|---|
| 2026-10-01 | 92 | 56 | 100 | 91 | 85 |
| 2026-10-15 | 92 | 56 | 100 | 92 | 85 |
| 2026-11-20 | 92 | 56 | 100 | 92 | 85 |

Savings is moderate on purpose: 470 SGD net saved is 11% of 4,230 SGD income, against the 20% target. Remittance consistency is 100 because there is a transfer in every month.

## Decisions

1. **Dates are relative to the run day.** The history is the current month and the 5 before it, so it always ends today and always sits inside the profile's 12-month window. An entry that would fall after today (this month's transfer on the 3rd, say) is left out and counted; the next run adds it. Days are 1 to 28 so no month lacks one.
2. **Entry ids start with `demo_`.** Writing again replaces them, a `demo_` entry removed from the file is deleted, and any entry with another id (a real transfer, a bill the account owner added) is never touched.
3. **No Firebase Auth user is created, and the default uid is `uid_priya_demo`**, the one in the data-model examples. Nobody can sign in as it. To show the data in the app, sign in once with the account you will demo with (a Firebase test phone number, for example) and load under its uid with `--uid`.
4. **`users/{uid}` is written only if it does not exist.** A real account's onboarding answers are never overwritten. If the account has not been onboarded, the loader creates the document (SG, India, domestic worker, Hindi, SG-IN alerts) so the app does not send the demo user back to onboarding.
5. **The profile is not seeded.** The weekly job computes it from these entries, so the scores, the Hindi report text and the PDF come from the real pipeline, and the metric formulas are not copied into data-scripts. The cost is one command and a Gemini call before the demo.
6. **Bill photos have no image.** The two `bill_ocr` bills carry the `extraction` map and a `bill_date` but no `image_path`: there is no photo to store.
7. **One atomic batch per user**, 32 writes, well under Firestore's 500 limit. If a file does not validate, nothing is written for any file.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy src tests` | Clean (30 files) |
| `pytest` (all of data-scripts) | 184 passed |
| `python -m src.validators.demo_user` | Priya OK (9 income, 6 transfers, 12 bills, 4 savings); the two other files reported as empty and skipped |
| `python -m src.loaders.seed --dry-run` | `5 transfers, 11 bills` today (1 October): this month's transfer (3rd) and phone bill (8th) are still ahead |
| Backend metrics on the seeded entries | See the table above |
| New tests | The planned history and numbers (6 months of salary and transfers, income 4,230 and net savings 470, one unpaid bill, the provider switch, each transfer's cost recomputed from its own figures); the date arithmetic (including across a year); entries left out when ahead; the document shape of each kind; timestamps never in the future; the user document; idempotent writes; an existing user left alone; stale and foreign entries; a later run adding what was ahead; the command (dry run, `--uid`, ambiguous `--uid`, unknown name, invalid file writes nothing, blank files); 20 schema rejections |

**Not verified:** a real write to Firestore (the loader is tested against a fake client with the same calls the radar seed loader uses), and the profile and PDF on the actual demo account (needs your `--uid` and the cron job).

## Manual steps for the demo

1. **Sign in** to `https://nomadfinance-prod.web.app` with the account you will demo with (for example the Firebase test number `+61 491 570 156`). Finish onboarding, or skip it and let the loader create the user document.
2. **Find its uid:** Firebase console → Authentication → Users → the *User UID* column.
3. **Load the history**, from `data-scripts/` with the venv active and `gcloud auth application-default login` done:
   ```bash
   python -m src.loaders.seed --only priya_sg_domestic --uid <uid> --dry-run
   ```
   ```bash
   python -m src.loaders.seed --only priya_sg_domestic --uid <uid>
   ```
   Expect `wrote 9 income, 6 transfers, 12 bills, 4 savings` (fewer transfers or bills in the first days of the month) and `user document left as it was` (or `created`).
4. **Build the profile and report text:**
   ```bash
   gcloud scheduler jobs run fib-recompute --project nomadfinance-prod --location asia-south1
   ```
   Then Firestore → `users/<uid>/financial_profile/current`: overall about 85, `narrative.language` `hi` (the account's `preferred_language`; change it first for another language).
5. **Export the PDF** (`POST /api/v1/fib/report/export`, NF-P3-014) and open it.
6. **Run the loader again a day or two before recording**, so this month's entries are in, then `fib-recompute` again.

To remove the demo data: delete the account (Profile → Delete account, which also tests NF-P1-023), or delete the `demo_*` documents in the console.
