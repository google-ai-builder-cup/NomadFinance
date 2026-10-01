# NF-P3-020 — Sample Contracts for Demo (6 countries)

Assigned to Pranjal; built by Aditya.

## Summary

Six fictional employment contracts, one per host country, so the demo has something real to upload to Contract Shield. They are in `data-scripts/data/seed/contracts/` and are copied to Cloud Storage by a loader. Data-scripts only: no backend, frontend, rules or dependency change.

Not in this task: the live Gemini pass over these files (NF-P2-008 is still waiting for quota, see its runbook), the radar badge on the report card (NF-P3-023), and the demo accounts (NF-P3-021).

## Files

| File | Change |
|---|---|
| `data/seed/contracts/source/*.txt` (6, new) | The contract texts: the part a human edits |
| `data/seed/contracts/*.pdf` (6, new) | Built from the texts. The six empty `*.pdf.placeholder` stubs are removed |
| `data/seed/contracts/manifest.json` (new) | Per contract: country, job type, worker language, employer, agency, radar slug, overall label and the planted issues |
| `src/loaders/sample_contract_pdf.py` (new) | Text to PDF, standard library only; `--check` finds a stale PDF |
| `src/validators/sample_contract.py` (new) | Schema and cross-checks for the manifest and the files |
| `src/loaders/sample_contracts.py` (new) | Uploader |
| `src/config.py` | `SEED_CONTRACTS_DIR` |
| `scripts/seed_demo.sh`, `README.md` | The uploader is part of the demo seeding; documented |
| `tests/test_sample_contracts.py` (new) | 21 tests |

## The six contracts

Dates are August to October 2026. All people and companies are invented; the three radar names (marked ★) are the ones in the radar seed (NF-P3-005), so the community-flagged badge has something to show.

| Country | File | Worker / employer | Label | What is wrong in it |
|---|---|---|---|---|
| SG | `sg_domestic_worker` | Priya Sharma (IN) / Mrs. Lim Hui Min, "Example Household", 650 SGD | fair | Only a soft spot: a rest day may be paid out at the employer's choice |
| KR | `kr_manufacturing_worker` | Rajesh Kumar (IN) / Han River Metals Co. ★ | risky | 1,950,000 KRW wage (under the 2026 minimum for a 209-hour month), 60-hour week, no overtime premium, passport held, 1.8M KRW agency fee, 2M KRW penalty for leaving, dismissal without notice, 400,000 KRW dormitory charge |
| MY | `my_plantation_worker` | Agus Pratama (ID) / Sawit Jaya Plantations | mixed | Wage is exactly the RM1,700 minimum, but overtime at the normal rate and passport held; housing deduction and 2-week notice are caution |
| JP | `jp_care_worker` | Miguel Santos (PH) / Sakura Gardens Care | mixed | Residence card and passport held by the office, 300,000 JPY penalty for resigning within 3 years; dormitory and support fees are caution |
| HK | `hk_domestic_worker` | Maricel Dela Cruz (PH) / Mr. Wong, "Lantau Bay Household" ★ | risky | HK$4,800 wage and HK$900 food allowance (minimums are 5,100 and 1,236), 2 rest days a month, HK$21,000 placement fee against a cap of 10% of the first month, passport held, full-cost damage deductions, helper pays return flight |
| AU | `au_working_holiday` | Karan Mehta (IN) / Outback Harvest, via Bayanihan Overseas Recruitment ★ | risky | AUD 22/hour (casual minimum from 1 July 2026 is 33.05), "inclusive of super", 2,500 AUD agency fee taken from the first five pay packets; accommodation and shuttle deductions are caution |

Amounts and thresholds come from the curated labor-law files in `data/source/labor-laws/` (verified 2026-09-25). Each country has at least one clause that is fine, so the report card shows green, amber and red. Set: 1 fair, 2 mixed, 3 risky. The manifest check enforces that the labels mean different things (fair: no danger issue; mixed: 1 to 2; risky: 3 or more).

## Decisions

1. **Where the files live.** `demo-samples/contracts/{file}.pdf` in the default bucket. The folder is outside the per-user folders in `frontend/storage.rules`, so browsers cannot read it and the file needs no rules change. It is also outside `USER_FILE_FOLDERS`, so deleting an account never touches it. Storing them under `contracts/{uid}/...` would have needed a demo uid, which NF-P3-021 creates later.
2. **English only.** The PDFs use the built-in Helvetica fonts, which have no CJK or Indic glyphs, and adding a font library would mean a new dependency. The texts are checked to be Windows-1252 only, so a stray character fails the build instead of printing as a box. The Korean, Japanese and Malay originals a worker would really hold are a known gap.
3. **PDFs are committed, built from texts.** Reviewers read the `.txt` diff; `sample_contract_pdf --check` (and a test) fail if a PDF no longer matches. The output has no dates or random ids, so rebuilding gives identical bytes. Streams are uncompressed so any extractor, and `grep`, can read them.
4. **Idempotent upload.** An object whose MD5 and metadata already match is skipped, a changed one is replaced, and an object in the folder that is no longer in the manifest is deleted. Nothing outside `demo-samples/contracts/` is touched. Each object carries `synthetic: true`, country, job type, worker language, label and (where there is one) the radar slug as custom metadata.
5. **Planted issues are a guide, not a contract with Gemini.** Contract Shield's wording and ratings will vary; the manifest says what each text was written to contain so a rehearsal can spot a miss.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .` / `black --check .` | Clean |
| `mypy src tests` | Clean (34 files) |
| `pytest` (all of data-scripts) | 205 passed |
| `python -m src.validators.sample_contract` | 6 contracts OK; every planted clause number exists in its text; every radar slug exists in the radar seed |
| `python -m src.loaders.sample_contract_pdf --check` | All PDFs match their text |
| `python -m src.loaders.sample_contracts --dry-run` | 6 objects listed, no network access |
| PDFs | Each is 2 pages; the KR file was rendered and checked by eye (title, wrapping, indented clauses, footer) |

**Not verified:** a real upload to Cloud Storage (the uploader is tested against a fake bucket with the same calls; no credentials or storage emulator were used), and a run of these files through the live Contract Shield pipeline (Gemini quota, see NF-P2-008). Both are in the steps below.

## Manual steps

From `data-scripts/` with the venv active.

1. **Check and dry run**
   ```bash
   python -m src.validators.sample_contract
   python -m src.loaders.sample_contracts --dry-run
   ```
2. **Upload** (after `gcloud auth application-default login` with write access to the bucket)
   ```bash
   python -m src.loaders.sample_contracts
   ```
   Expect `done: 6 uploaded, 0 unchanged, 0 deleted`; a second run says `0 uploaded, 6 unchanged`. Console: Storage → `demo-samples/contracts/`.
3. **Get the files back for a rehearsal**
   ```bash
   gcloud storage cp "gs://nomadfinance-prod.firebasestorage.app/demo-samples/contracts/*.pdf" ./demo-contracts/
   ```
4. **Rehearse.** Upload each PDF on the Contract Shield page with the worker's country and language from the manifest, compare the report with `planted_issues`, and note misses for NF-P4-019.
5. **After editing a text:** `python -m src.loaders.sample_contract_pdf`, then the check and the upload again.

## Limits

- The extractor reads text PDFs well; these have no scan noise. A phone-photo version (the real-world case) is covered by the existing `sample_contract_my_id_photo.jpg` fixture, not by this set.
- Contract Shield decides the country and job type from the text. If it picks differently, the manifest's `country` and `job_type` are what the demo form should be set to.
- Rajesh is written as an Indian national on an E-9 visa; India is not one of the Employment Permit System's sending countries. Harmless for the demo, but change the nationality (or the visa line) if a judge from Korea is likely to look closely.
