# NF-P1-018 — Load Labor Laws into Firestore

## Summary

`data-scripts/src/loaders/ilo_natlex.py` reads the six curated files in `data-scripts/data/source/labor-laws/` (NF-P1-017) and writes them to Firestore: one header document, 15 rule documents and one version document per country. It validates **every** file with the same model as the checker (`LaborLawFile`) before it writes anything; if one file is broken, nothing is written. Each country is then written in a single batch, so it is never half-loaded.

The important field is `labor_laws/{country}/_meta/current.version`. Contract Shield stores each contract report with the `law_version` it was made against and remakes the report when the version has moved (NF-P2-007). So the loader must raise the version when a country's rules change, and must **not** raise it when the loader is simply run again. It decides by comparing a hash of the country's rules with the hash stored last time.

Firestore access uses the Firebase Admin SDK and Application Default Credentials, the same as the corridor loader (NF-P1-016). The security rules from NF-P1-014 already let any signed-in user read `labor_laws/**` and let nobody write from a browser, so no rules change was needed.

The tracker names the file `data-scripts/load_labor_laws.py`; the repo keeps loaders under `src/loaders/`, and the empty `ilo_natlex.py` stub (which `load_bootstrap.sh` already pointed at) is the one filled.

## Files

| File | Purpose |
|---|---|
| `data-scripts/src/loaders/ilo_natlex.py` | The loader: reads and validates the files, hashes the rules, decides the version, writes one batch per country, CLI |
| `data-scripts/tests/test_labor_law_loader.py` | 15 tests against a fake Firestore (no emulator needed) |
| `data-scripts/scripts/load_bootstrap.sh` | Now calls the loader after the corridor loader (replaced the TODO) |
| `data-scripts/README.md` | "Labor-law loader" section; the stale "SG, AU, KR, MY are still stubs" line corrected |
| `docs/data-model/collections/labor_laws.md`, `versioning.md` | "Loading" steps now say exactly how the hash and version work |

Shared files: none changed (`firebase-admin` was already pinned in NF-P1-016; `firestore.rules` is untouched).

## What gets written

Per country (`SG`, `KR`, `MY`, `JP`, `HK`, `AU`): 17 documents, 102 in total.

| Path | Content |
|---|---|
| `labor_laws/{CC}` | `country`, `name`, `rule_count` (15), `updated_at` |
| `labor_laws/{CC}/rules/{category}` (15) | The rule as curated (coverage, title, summary, variants, references, confidence, notes, ...) plus `country`, `category`, `schema_version: 1` |
| `labor_laws/{CC}/_meta/current` | `version`, `updated_at`, `category_ids`, `content_hash`, `curated_by`, `reviewed_by`, `last_verified_on`, `notes`, `schema_version` |

Field-by-field tables and examples: `docs/data-model/collections/labor_laws.md`.

## How the version works

```
read all 6 files ── validate each ── any failure? ── yes → write nothing, exit 1
                                          │ no
             for each country:  hash = SHA-256 of canonical JSON of its 15 rules
                                read labor_laws/{CC}/_meta/current
                                  missing          → version 1              ("new")
                                  same hash        → keep version           ("unchanged")
                                  different hash   → stored version + 1     ("changed")
                                one batch: 15 rules + header (+ _meta if new or changed)
```

| What you did | Result |
|---|---|
| Ran the loader again with no edits | Every country `unchanged`; `_meta` is not rewritten; versions stay |
| Edited one rule of one country | Only that country becomes `changed`, version + 1 |
| Changed `reviewed_by`, the file-level `notes`, JSON layout or line endings | `unchanged` (the hash covers the validated rules only) |
| Changed anything inside a rule, including `last_verified_on` | `changed` |
| Put an edited rule back to its old text | `changed` again, version + 1: the old number is not restored, which is right because reports made in between must not be reused |
| Loaded into an empty Firestore | All `new`, version 1 |

The hash is computed from the validated data, not the file bytes, so a Windows checkout with different line endings cannot cause a spurious bump.

## All commands, in order

Everything runs from `data-scripts/`.

### 0. Prerequisites

- The venv from NF-P1-015 with `pip install -r requirements-dev.txt` (it now includes `firebase-admin`; an older venv without it fails with `No module named 'firebase_admin'`).
- Write access to the target Firestore: `gcloud auth application-default login` against a project you can write to, or a running emulator with `FIRESTORE_EMULATOR_HOST` set.

### 1. Dry run (validates, touches nothing, needs no credentials)

```bash
python -m src.loaders.ilo_natlex --dry-run
```

Expected: six `Validated <CC>: 15 rules, content hash ...` lines, then six `[dry-run] would write labor_laws/<CC>` lines.

### 2. Start the emulator

**bash** (from `frontend/`; needs the Firebase CLI and Java 11+)
```bash
cd ../frontend
firebase emulators:start --only firestore --project demo-nomadfinance
```

Firestore listens on `127.0.0.1:8085` and the UI on `http://127.0.0.1:4000/firestore`. The first run downloads the emulator jar (about 136 MB) into `~/.cache/firebase/emulators/`; the NF-P1-014 rule tests use the same jar.

### 3. Load into the emulator

**bash**
```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085
export FIREBASE_PROJECT_ID=demo-nomadfinance
python -m src.loaders.ilo_natlex
```

**Windows PowerShell**
```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m src.loaders.ilo_natlex
```

Expected:

```
SG  15 rules  version 1  new
KR  15 rules  version 1  new
MY  15 rules  version 1  new
JP  15 rules  version 1  new
HK  15 rules  version 1  new
AU  15 rules  version 1  new
Loaded 6 countries into 'labor_laws': 6 new, 0 changed, 0 unchanged
```

Open the emulator UI to see `labor_laws/SG` with `rules` and `_meta` under it.

### 4. Check that a re-run changes nothing

Run step 3 again. Every line must say `version 1  unchanged`, and the summary `0 new, 0 changed, 6 unchanged`.

### 5. Check that a rule change bumps only its country

Copy the folder, edit one sentence in one rule, load from the copy:

**bash**
```bash
cp -r data/source/labor-laws /tmp/ll_edit
# edit a summary in /tmp/ll_edit/HK.json, then:
python -m src.loaders.ilo_natlex --input-dir /tmp/ll_edit
```

Expected: `HK  15 rules  version 2  changed` and the other five `unchanged`. Load the original folder again to put the emulator back (HK goes to version 3, as explained above). Restart the emulator to start from empty.

### 6. Load into real Firestore (`nomadfinance-prod`)

Only after steps 1 to 5 look right. This writes to the project all three of you share, and it is a **one-person step**: do not run two loaders at once, because the version is read just before each write.

```bash
unset FIRESTORE_EMULATOR_HOST FIREBASE_PROJECT_ID     # PowerShell: Remove-Item Env:FIRESTORE_EMULATOR_HOST, Env:FIREBASE_PROJECT_ID
gcloud auth application-default login
python -m src.loaders.ilo_natlex --dry-run
python -m src.loaders.ilo_natlex
```

Verify one country (Firebase console: Firestore, `labor_laws`, `SG`, `_meta`, `current`) or from Python with your credentials:

```bash
python -c "from src.firestore_client import get_firestore_client as g; print(g().collection('labor_laws').document('SG').collection('_meta').document('current').get().to_dict()['version'])"
```

To rehearse on prod without touching the real collection, add `--collection labor_laws_staging` (note the security rules do not cover that path, so it is unreadable from browsers; delete it afterwards in the console).

### 7. Run the checks

```bash
pytest
ruff check .
black --check .
mypy src tests
```

Expected: `66 passed`, `All checks passed!`, `... would be left unchanged.`, `Success: no issues found`. `pytest` uses a fake Firestore and never touches a real one.

## Options

| Option | Effect |
|---|---|
| `--dry-run` | Validate and log only; no Firestore client is created |
| `--only SG JP` | Load just these countries |
| `--require-all` | Fail if any country file is still an empty `{}` stub (the "task complete" check) |
| `--input-dir DIR` | Read the files from another folder |
| `--collection NAME` | Write under another collection (default `labor_laws`) |

Without `--require-all`, a stub file is skipped with a warning and the others load.

## Definition of Done

Data ingestion script:
- [x] Idempotent: `set` on fixed ids; the version and `_meta` change only when the rules' hash changes (15 tests plus an emulator run: second load `unchanged`)
- [x] Validates before writing: all files checked with `LaborLawFile`; a failure stops the run with nothing written
- [x] Logs counts: one line per country (rules, version, new/changed/unchanged) and a summary; problems are listed with the file and field
- [x] Admin SDK with Application Default Credentials, same pattern as NF-P1-016
- [x] Documented in `data-scripts/README.md`

Firestore schema change:
- [x] Migration script: not needed (no existing `labor_laws` data)
- [x] Security rules: already correct from NF-P1-014 (`labor_laws/**` readable when signed in, no browser writes); not changed
- [x] `docs/data-model` updated (Loading section, versioning)
- [x] Emulator run: loaded, re-run unchanged, one-rule change bumped only that country
- [x] Version metadata: this task is what writes and bumps `_meta.version`

Task specific:
- [x] One `_meta` document per country with version metadata (`version`, `content_hash`, `category_ids`, `curated_by`, `reviewed_by`, `last_verified_on`, `schema_version`)
- [x] All six countries load with 15 rules each (102 documents)
- [x] Run once against `nomadfinance-prod` on 2026-09-26 (step 6): 6 countries, 90 rules, all at version 1; a second run reported all six `unchanged`. The corridor loader (NF-P1-016) was run the same day, so `corridors` (6 documents) now exists too.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'firebase_admin'` | Old venv: `pip install -r requirements-dev.txt` |
| `Nothing was written: fix the files above` | A country file failed validation; the lines above list the file and the field. Fix it and run the checker: `python -m src.validators.labor_law` |
| `<CC>.json is still an empty stub, skipped` | Expected while a file is `{}`. `--require-all` turns it into a failure |
| `No curated files found in ...` | Wrong `--input-dir`, or every file is a stub |
| `DefaultCredentialsError` / permission errors | Run `gcloud auth application-default login`, or set `FIRESTORE_EMULATOR_HOST` for the emulator |
| Connection refused on 8085 | The emulator is not running (step 2), or `FIRESTORE_EMULATOR_HOST` points elsewhere |
| A country jumps by 2 versions | It was loaded twice with changed content in between; each change counts once |
| Version went up though I only fixed a typo | Any text inside a rule counts, including `last_verified_on`. Only file-level fields (`reviewed_by`, `notes`, layout) are ignored |
| Two people loaded at the same time | Versions are read then written; if it happened, load again, and agree who runs it |

## Not covered here

- Reading rules by country and comparing a contract: NF-P2-003, NF-P2-004
- The report cache keyed on `law_version`: NF-P2-007
- ILOSTAT number checks (`src/loaders/ilostat.py` is still an empty stub) and NATLEX record numbers
- Deleting rule documents that a future category rename would leave behind (the 15 ids are fixed; a rename needs a migration)
