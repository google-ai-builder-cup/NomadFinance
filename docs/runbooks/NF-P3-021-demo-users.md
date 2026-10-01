# NF-P3-021 — Demo User Accounts (Pre-seeded)

Assigned to Devam; built by Aditya.

## Summary

Three fictional demo workers with six months of activity each, and the Firebase Auth accounts to sign in as them: Priya (Singapore, domestic worker), Rajesh (South Korea, manufacturing) and Miguel (Japan, care). Priya's history came from NF-P3-015; this task fills the two empty seed files with Rajesh's and Miguel's, and adds a loader for the accounts. Data-scripts only: no backend, frontend, rules or dependency change.

Not in this task: Contract Shield reports saved under each user (they need Gemini; run the NF-P3-020 sample contracts through the app), "verified employment" income from contracts (NF-P3-024), and the computed profiles (the `fib-recompute` job makes them).

## Files

| File | Change |
|---|---|
| `data/seed/users/rajesh_kr_manufacturing.json` | Was an empty stub: 8 income, 0 transfers, 12 bills, 4 savings |
| `data/seed/users/miguel_jp_care.json` | Was an empty stub: 10 income, 6 transfers, 13 bills, 7 savings |
| `src/loaders/demo_accounts.py` (new) | Creates the three Auth users |
| `scripts/seed_demo.sh`, `README.md` | The accounts step runs before the history step; documented |
| `tests/test_demo_users.py` (new) | 21 tests |
| `tests/test_demo_user_seed.py` | The two "still empty" assertions now say all three files are filled |
| `src/loaders/sample_contract_pdf.py`, `src/loaders/sample_contracts.py`, `tests/test_sample_contracts.py` | Fix to NF-P3-020, see "Found on the way" |

## The three workers

| | Priya | Rajesh | Miguel |
|---|---|---|---|
| Place and job | Singapore, domestic | Siheung, Korea, press operator | Saitama, Japan, care worker |
| Home, language | India, `hi` | India, `hi` | Philippines, `tl` |
| uid | `uid_priya_demo` | `uid_rajesh_demo` | `uid_miguel_demo` |
| Test phone number | `+61 491 570 156` | `+61 491 570 157` | `+61 491 570 158` |
| Salary logged | 650 SGD | 1,235,000 KRW | 152,000 JPY |
| Entries | 9 / 6 / 12 / 4 | 8 / 0 / 12 / 4 | 10 / 6 / 13 / 7 |
| Story | Moderate saver, moved to a cheaper provider | Underpaid, saves almost nothing, two late bills | Strong saver, left a flagged operator |

Entries are income / transfers / bills / savings. Salary figures follow each worker's sample contract (NF-P3-020) after the deductions it lists: Rajesh's 1,950,000 KRW less the 400,000 dormitory charge, the 150,000 agency fee and insurance; Miguel's 215,000 JPY less dormitory, support fee and statutory deductions. The first salary entry says so in its note.

**Rajesh.** Salary every month, no overtime income (the contract folds it into the wage), two small cash side jobs. Phone and transit bills, one hospital bill (hand injury, category set by the user), the phone bill unpaid in the two months around the hospital visit (the month of the visit and the one after). Savings: three deposits, one withdrawal for the hospital, net 150,000 KRW, 2.0% of income against the 20% target.

**Miguel.** Salary, three night-shift allowances, one attendance bonus. Six transfers of 60,000 JPY on JP-PH: three through Kapitan Padala at 5.8 to 6.2% cost, then three through DCOM Money Express (World Bank RPW id 521253120) at 1.9 to 2.0%, with the note "Switched after the community warning in Exploitation Radar" on the first one. Kapitan Padala is the invented operator that has two reports in the radar seed, so the warning story holds. One transport bill unpaid; one clinic visit and one language-school bill with user categories. Savings: net 180,000 JPY, 17.9% of income.

Provider names for DCOM Money Express and its fees follow the World Bank RPW JP-PH survey (2025 Q1); the mid-market rates, amounts and everything else are invented. Each transfer's `cost_pct` is `1 - received / (sent x mid-market)`, checked by a test.

## What `fib-recompute` makes of it

Checked by running the seeded entries through the backend's own metric code (`profile_metrics.py`), on three different run days:

| Worker | Income stability | Savings rate | Remittance consistency | Bill reliability | Overall |
|---|---|---|---|---|---|
| Miguel (all three run days) | 93 to 94 | 88 to 90 | 100 | 92 | 94 |
| Priya (all three run days) | 92 | 56 | 100 | 91 to 92 | 85 |
| Rajesh (all three run days) | 97 | 10 to 12 | no data | 82 to 83 | 63 to 64 |

Run days checked: 2026-10-01, 10-14 and 10-30. Rajesh's remittance metric has no score, so his overall is the mean of the three that do; the narrative should say so rather than read it as a failure.

## Decisions

1. **Rajesh has no transfers.** None of the six corridors starts in KR (KR-NP was replaced by AU-IN in NF-P1-015) and the validator only accepts the six. Logging him on another corridor would have meant a scope and validator change. It also makes a useful third case: the score without remittance data.
2. **The accounts are created by a loader, not by hand.** Each gets the uid from its seed file and one of the three Firebase test phone numbers, so the history and the sign-in cannot drift apart and nobody pastes a uid. Test numbers send no SMS and the sign-in code is the shared one from the console. The loader never touches an existing account that belongs to a different uid.
3. **Paydays are the 25th**, as in the contracts. Before the 25th of a month the running month shows only its bills, and the later entries are added by the next run. The metrics do not count the running month against a worker until it has an entry, so the scores above hold on any day. Run the history loader again just before recording.
4. **Everything else follows NF-P3-015**: `demo_` ids, one atomic batch per user, relative dates, `users/{uid}` written only if missing, no profile seeded. The loader and validator are unchanged.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .` / `black --check .` | Clean |
| `mypy src tests` | Clean (36 files) |
| `pytest` (all of data-scripts) | 227 passed |
| `python -m src.validators.demo_user` | All three files OK |
| `python -m src.loaders.demo_accounts --dry-run` | Three accounts listed, no Firebase access |
| `python -m src.loaders.seed --dry-run` | Priya 5 transfers, Rajesh 0, Miguel 5 (today is the 1st: this month's later entries are ahead) |
| Backend metrics on the seeded entries | See the table above |

**Not verified:** a real run against Firebase Auth or Firestore. Both loaders are tested against fakes with the same calls, and no credentials or emulators were used. Not checked either: that the demo sign-in actually lands on the seeded uid with a test number (the loader depends on Firebase matching an existing user by phone number, which is its documented behaviour).

## Manual steps for the demo

From `data-scripts/` with the venv active and `gcloud auth application-default login` done.

1. **Check:**
   ```bash
   python -m src.validators.demo_user
   python -m src.loaders.demo_accounts --dry-run
   python -m src.loaders.seed --dry-run
   ```
2. **Make sure the three test numbers are configured** (Firebase console → Authentication → Sign-in method → Phone → Phone numbers for testing; see `NF-P1-009-frontend-firebase-auth.md`). Do this before step 3 if anyone could sign in with them first.
3. **Create the accounts and load the histories:**
   ```bash
   python -m src.loaders.demo_accounts
   python -m src.loaders.seed
   ```
   Expect `created` three times, then one `wrote ...` line per worker. A second run says `unchanged`. If a number is reported as already signing in under another uid, load that worker with `python -m src.loaders.seed --only <name> --uid <that uid>` (Authentication → Users shows it).
4. **Build the profiles:**
   ```bash
   gcloud scheduler jobs run fib-recompute --project nomadfinance-prod --location asia-south1
   ```
   Then `users/<uid>/financial_profile/current` for each worker: overall about 94, 85 and 63.
5. **Sign in as each worker** with their number (table above) at `https://nomadfinance-prod.web.app`: the dashboard, Financial Identity timeline and Remittance X-Ray should show their data and language.
6. **Run it again a day or two before recording**, then `fib-recompute` again, so the running month is filled.

To remove a demo worker: Authentication → Users → delete the account (the account-deletion job clears its data), or delete the `demo_*` documents.

## Found on the way

NF-P3-020's PDFs fail `test_every_pdf_matches_its_text` on a fresh Windows checkout. With `core.autocrlf=true`, git rewrote the line feeds of the all-ASCII PDFs to CRLF (the committed blobs are LF), which shifts their xref offsets and changes their bytes. Fixed by reading the PDFs through `read_pdf()`, which undoes the conversion, in the PDF builder's check and in the uploader (so the uploaded bytes are the same on every machine); a test covers it. The real fix is a `.gitattributes` line such as `*.pdf -text` (this also helps the four PDFs in `backend/tests/fixtures/contracts/`); that is a new repo-wide file, so it is left for you to decide.

## Limits

- Rajesh is an Indian national on an E-9 visa; India is not one of the Employment Permit System's sending countries (noted in NF-P3-020 too).
- Kapitan Padala is not in the World Bank comparison, so a provider picker will not list it; Miguel's history is the only place it appears next to a DCOM transfer.
- Contract Shield results are not seeded: to show a saved report for a worker, upload that worker's sample contract in the app while signed in as them.
