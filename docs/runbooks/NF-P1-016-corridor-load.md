# NF-P1-016 — Load Corridor Data into Firestore

## Summary

`data-scripts/src/loaders/corridors.py` reads the committed, already-parsed
`data-scripts/data/processed/rpw_corridors.json` (NF-P1-015) and writes one document per
corridor to Firestore `corridors/{corridor_id}`: `SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`,
`AU-PH`. It re-validates the JSON against the same Pydantic models the parser used
(`data-scripts/src/validators/corridor.py`) before writing anything, adds two loader-owned
fields (`source`, `loaded_at`), and writes with a plain `set()` on the corridor's fixed id, so
re-running it replaces the six documents instead of duplicating them. Nothing is read from the
World Bank Excel or recomputed; this task only moves the already-validated JSON into Firestore.

Firestore access uses the Firebase Admin SDK with Application Default Credentials
(`data-scripts/src/firestore_client.py`), the same pattern as the backend
(NF-P1-005). The security rules deployed in NF-P1-014 make `corridors` writable only through
the Admin SDK — this script — with any signed-in user able to read it.

## Files

| File | Purpose |
|---|---|
| `data-scripts/src/loaders/corridors.py` | Reads and re-validates the JSON, builds each document, writes it, CLI entry point |
| `data-scripts/src/firestore_client.py` | Process-wide Firestore client (Admin SDK, ADC) |
| `data-scripts/tests/test_corridor_loader.py` | Unit tests against a fake Firestore client |
| `data-scripts/requirements.txt` | Added `firebase-admin==7.7.0` (same pin as `backend/requirements.txt`) |
| `data-scripts/README.md` | "Corridor loader" section added |
| `data-scripts/scripts/load_bootstrap.sh` | Calls the loader; labor-law half left as a TODO for NF-P1-018 |
| `docs/data-model/collections/corridors.md` | Loader file path noted under "Loading and refreshing" |

## Flow

```
data/processed/rpw_corridors.json   (committed, built by NF-P1-015)
  └─ RpwCorridorFile.model_validate_json(...)   re-validates the whole file
       └─ for each of the 6 CorridorDoc entries:
            add source {name, url, attribution} + loaded_at (SERVER_TIMESTAMP)
              └─ corridors/{corridor_id}.set(...)   replaces, never duplicates
```

## All commands, in order

Everything runs from `data-scripts/`.

### 0. Prerequisites

- Python 3.11.9 and the venv from NF-P1-015 (`pip install -r requirements-dev.txt` — now also
  installs `firebase-admin`).
- Write access to the target Firestore project: either
  - `gcloud auth application-default login` against a project you can write to, or
  - a running Firebase emulator with `FIRESTORE_EMULATOR_HOST` set (see the "Firestore rule
    tests" section of `docs/runbooks/NF-P1-014-firestore-security-rules.md` for starting one).

### 1. Install

**bash**
```bash
cd data-scripts
source .venv/bin/activate
pip install -r requirements-dev.txt
```

**Windows PowerShell**
```powershell
cd data-scripts
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### 2. Dry run (validates, writes nothing)

```bash
python -m src.loaders.corridors --dry-run
```

Expected: a validated line with the corridor/provider counts and period, then one
`[dry-run] would write ...` line per corridor. Nothing is written to Firestore.

### 3. Load against the emulator first

**bash**
```bash
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8085
export FIREBASE_PROJECT_ID=demo-nomadfinance
python -m src.loaders.corridors
```

**Windows PowerShell**
```powershell
$env:FIRESTORE_EMULATOR_HOST = "127.0.0.1:8085"; $env:FIREBASE_PROJECT_ID = "demo-nomadfinance"
python -m src.loaders.corridors
```

Expected: one `<corridor_id>  <N> providers  written` line per corridor, then
`Wrote 6 corridor documents to 'corridors'`. Check the emulator UI
(`http://127.0.0.1:4000/firestore`, if running with `--project demo-nomadfinance`) for the six
documents.

### 4. Check it is idempotent

Run step 3 again. Same six ids, same output, no duplicates and no new documents.

### 5. Load against real Firestore (`nomadfinance-prod`)

Only after step 3/4 look right. This writes to the live project everyone shares.

```bash
python -m src.loaders.corridors
```

(No env vars needed: `FIREBASE_PROJECT_ID` defaults to `nomadfinance-prod`, and ADC is picked
up from `gcloud auth application-default login`.) Verify with:

**bash**
```bash
curl -s "https://firestore.googleapis.com/v1/projects/nomadfinance-prod/databases/(default)/documents/corridors/SG-PH" | head -c 300
```

**Windows PowerShell**
```powershell
curl.exe -s "https://firestore.googleapis.com/v1/projects/nomadfinance-prod/databases/(default)/documents/corridors/SG-PH"
```

Anonymous reads are allowed by the NF-P1-014 rules, so this should return the document (200),
not 403.

### 6. Run the checks

```bash
pytest
ruff check .
black --check .
mypy src tests
```

`pytest` uses a fake Firestore client (`_FakeClient` in `test_corridor_loader.py`), so it needs
no emulator and never touches real Firestore.

## Definition of Done

Data ingestion script:
- [x] Script is idempotent (plain `set` on a fixed id; re-run replaces, never duplicates)
- [x] Validates data before writing (re-validates the whole file against the Pydantic models
      before any Firestore call)
- [x] Logs count of records processed per corridor; a schema failure stops the run before any
      write
- [x] Uses service account or admin SDK correctly (Firebase Admin SDK, Application Default
      Credentials, same pattern as the backend)
- [x] Documented in `data-scripts/README.md`

Task specific:
- [x] Reads the committed `rpw_corridors.json`, does not touch the Excel or recompute values
- [x] Writes all 6 corridors with `source` (name/url/attribution) and `loaded_at` added
- [x] `--dry-run` validates without writing, for safe local checking before touching prod

## Not covered here

- Parsing the World Bank Excel: NF-P1-015
- Firestore schema and security rules: NF-P1-013 / NF-P1-014
- Labor-law loader: NF-P1-018 (`load_bootstrap.sh` has a TODO for it)
- Comparison engine and UI: NF-P2-014 and later
