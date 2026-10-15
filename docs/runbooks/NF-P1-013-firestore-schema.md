# NF-P1-013 — Firestore Schema

## Summary

The Firestore data model is now written down: every collection path, its fields and types, an example document, who may read and write it, the indexes it needs, and how its version is handled. Before this task the original design had one line per collection and all nine files in `docs/data-model/` were empty. Nothing was created in Firestore: this task is documentation only, and the live database (`(default)`, Native, `asia-south1`) is still empty.

The original design's table could not be used as written. Four of its paths have the wrong number of segments for Firestore, one has a variable where a collection name must be, and one collection the tasks need (`savings`) was missing. Those were fixed and are listed in the table below. The real Firestore client library rejects the original paths and accepts the corrected ones (see "Verified results").

This is the document Devam needs for the security rules (NF-P1-014), Aditya for the corridor loader (NF-P1-016), and everyone for the pillar tasks that read or write these collections.

## Files

| File | What it holds |
|---|---|
| `docs/data-model/firestore-schema.md` | Start here. Collection map, fixes to the original design, conventions, access matrix, required indexes, Cloud Storage paths, open questions |
| `docs/data-model/collections/users.md` | `users/{uid}`, `notifications`, account deletion |
| `docs/data-model/collections/contracts.md` | Contracts, per-language reports (the cache), complaint templates |
| `docs/data-model/collections/corridors.md` | RPW provider prices, exactly as the NF-P1-015 parser writes them |
| `docs/data-model/collections/rates_cache.md` | Live FX rates and rate history |
| `docs/data-model/collections/labor_laws.md` | Labor-law rules, the version document, the 15 categories |
| `docs/data-model/collections/radar.md` | Reports, embeddings, entities, alerts |
| `docs/data-model/collections/fib.md` | Transfers, income, bills, savings, financial profile |
| `docs/data-model/versioning.md` | Data, prompt and schema versions, and how to change a schema |
| `docs/runbooks/NF-P1-013-firestore-schema.md` | This runbook |

The tracker and the original design say "docs/data-model.md". The repo already had the folder above, so the existing files were filled instead of creating a second structure.

## What was decided

| # | Decision | Where |
|---|---|---|
| 1 | Fill the existing folder stubs, not a single `data-model.md` | Files table |
| 2 | Fix the invalid original design paths (table below) | `firestore-schema.md` |
| 3 | Add `users/{uid}/savings/{id}` | `fib.md` |
| 4 | Embeddings use `gemini-embedding-001` at 768 dimensions (Firestore allows at most 2048; the model's default is 3072). Vectors are normalized before storing. | `radar.md` |
| 5 | The 15 labor-law categories (list in `labor_laws.md`) | `labor_laws.md` |
| 6 | The contract cache is the per-language report document, valid only when file hash, language, law version and prompt versions all match. It is per user. | `contracts.md` |
| 7 | Money is a number in major units plus a separate ISO currency | `firestore-schema.md` |
| 8 | Radar reports store an HMAC hash of the reporter, never the uid | `radar.md` |

Path fixes:

| Original design | Problem | Now |
|---|---|---|
| `users/{uid}/financial_profile` | 3 segments is a collection | `users/{uid}/financial_profile/current` |
| `labor_laws/{country}/_meta` | Same | `labor_laws/{country}/_meta/current` |
| `radar_alerts/{corridor}/current` | Same | `radar_alerts/{corridor}/current/{alertId}` |
| `complaint_templates/{country}/{type}` | Variable in the collection position | `complaint_templates/{country}/types/{type}` |
| `rates_history/{pair}/points` | Same as row 1 | `rates_history/{pair}/points/{pointId}` |
| (missing) | NF-P3-010 needs `POST /fib/savings` | `users/{uid}/savings/{id}` |

## Where each shape comes from

Every table says how firm it is:

- **[D]** stated in the original design, **[T]** needed by a tracker task, **[built]** already in the repo (the corridors shape is the NF-P1-015 parser's output);
- **[P]** proposed here because nothing else defines it. Most field names beyond the original design's table are [P]. The task owner may refine them but should tell the team when a name changes.

## All commands, in order

Run from the repo root. The check needs the backend virtualenv (it already has the Firestore client library).

### 0. Prerequisites

The backend virtualenv from `NF-P1-001-local-dev-setup.md` (`backend/.venv`). No emulator, no network and no credentials are needed.

### 1. Read the overview

Open `docs/data-model/firestore-schema.md` and read the collection map and "Questions the team still needs to settle". Then open the collection file for your own tasks (see "Who should review what").

### 2. Check every example and path against the real Firestore client

The check reads each `**Example** — <path>` block from the docs, requires valid JSON, and asks the Firestore client to build the document reference. The client rejects a path whose segment count is wrong.

Save this as `check_schema_docs.py` anywhere (do not commit it), then run it from the repo root:

```python
import json
import re
from pathlib import Path

from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore

client = firestore.Client(project="demo-nomadfinance", credentials=AnonymousCredentials())
bad = 0
for md in sorted(Path("docs/data-model").rglob("*.md")):
    text = md.read_text(encoding="utf-8")
    for path, body in re.findall(r"\*\*Example\*\* — `([^`]+)`[^\n]*\n\n```json\n(.*?)\n```", text, re.S):
        json.loads(body)  # the example must be valid JSON
        try:
            client.document(path)  # rejects a path with the wrong number of segments
            print("ok ", path)
        except ValueError as exc:
            bad += 1
            print("BAD", path, exc)
print("bad paths:", bad)
raise SystemExit(bad)
```

**bash**
```bash
backend/.venv/bin/python check_schema_docs.py
```

**Windows PowerShell**
```powershell
backend\.venv\Scripts\python.exe check_schema_docs.py
```

Expected: 19 lines starting with `ok`, then `bad paths: 0`.

### 3. See why the original design paths had to change

```bash
backend/.venv/bin/python - <<'EOF'
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
c = firestore.Client(project="demo", credentials=AnonymousCredentials())
for p in ["users/x/financial_profile", "labor_laws/SG/_meta", "radar_alerts/SG-IN/current",
          "rates_history/SGD_PHP/points", "users/x/financial_profile/current",
          "labor_laws/SG/_meta/current", "radar_alerts/SG-IN/current/a_01",
          "rates_history/SGD_PHP/points/2026-09-27T08"]:
    try:
        c.document(p)
        print("accepted:", p)
    except ValueError:
        print("rejected:", p)
EOF
```

Expected: the first four (the original design's paths) are rejected and the last four (the corrected ones) accepted. On PowerShell, save the same lines as a `.py` file and run it with `backend\.venv\Scripts\python.exe`.

### 4. Check the corridors example against the real model and data

The corridors document must match what the NF-P1-015 parser writes. Run the data-scripts tests, which include a test that validates the committed JSON with the same Pydantic models:

```bash
cd data-scripts
source .venv/bin/activate    # PowerShell: .\.venv\Scripts\Activate.ps1
pytest -q
```

Expected: `18 passed`. The example provider in `corridors.md` was also compared with the first provider of `SG-PH` in `data-scripts/data/processed/rpw_corridors.json` and is identical.

### 5. Read the docs' consistency once more before merging

- The 15 category ids in the table in `labor_laws.md` and in the `_meta` example are the same 15.
- The six corridor ids and six currency pairs match `data-scripts/src/config.py`.
- No document mentions KR→NP (the corridor list is SG-PH, SG-IN, AU-IN, MY-ID, JP-PH, AU-PH).

## Who should review what

| Person | Read | Look for |
|---|---|---|
| Devam (NF-P1-014 rules) | The access matrix in `firestore-schema.md`; the access line of each collection file | Is each read and write rule what you would put in `firestore.rules`? Anything the browser must write directly? |
| Aditya (NF-P1-016 loader; radar embeddings NF-P3-002) | `corridors.md`; the embeddings part of `radar.md` | The two fields the loader adds (`source`, `loaded_at`); 768 dimensions and normalizing |
| All three | The 15 categories in `labor_laws.md` | Confirm or change the list **before NF-P1-017 curation starts** |
| All three | "Questions the team still needs to settle" in `firestore-schema.md` | Four open items, with the default each doc uses |

## How later tasks use it

| Task | Reads |
|---|---|
| NF-P1-014 security rules | Access matrix, access line per collection |
| NF-P1-016 corridor load | `corridors.md` |
| NF-P1-017, NF-P1-018 labor laws | `labor_laws.md`, `versioning.md` |
| NF-P1-019 FX cron, NF-P2-015 trends | `rates_cache.md` |
| NF-P1-022, NF-P1-023 profile | `users.md` |
| NF-P2-001 to NF-P2-013 Contract Shield | `contracts.md`, `labor_laws.md` |
| NF-P2-014 to NF-P2-022 Remittance | `corridors.md`, `rates_cache.md`, `fib.md` (transfers) |
| NF-P3-001 to NF-P3-009, NF-P3-025 Radar | `radar.md`, `users.md` (notifications) |
| NF-P3-010 to NF-P3-018, NF-P3-024 Financial Identity | `fib.md` |
| Any schema change | The rules in `versioning.md` and its checklist |

## Verified results (2026-09-25)

| Check | Result |
|---|---|
| Sample documents in the docs | 19 examples: valid JSON, all paths legal for the Firestore client |
| Collection map in `firestore-schema.md` | 22 paths, all legal document paths |
| The four original design paths with the wrong number of segments | Rejected by the client; the corrected ones accepted |
| Vector field | A 768-number `Vector` is accepted (limit 2048) |
| Corridors example | Identical to the real `SG-PH` provider and header; the provider passes the `ProviderRecord` model |
| Largest real document (`JP-PH`) | 25,832 bytes, about 2.5% of the 1 MiB limit |
| Category list | 15 ids, the same in the table, the `_meta` example and the contract clause example |
| Corridor ids and currency pairs | Match `data-scripts/src/config.py` |
| Links between the docs | All resolve |
| Live database | `(default)`, Native, `asia-south1`, no collections and no indexes |

**Not verified** (be aware when reviewing):

- **No emulator round trip.** The Firestore emulator is not installed on this machine (only the emulator UI is), and installing it is a download. The path check uses the Firestore client library, which validates paths offline, but it did not write documents. Someone with the emulator should write one document per collection when NF-P1-014 adds rules.
- **Security rules and index files are not written.** The access matrix and index table are intent, for NF-P1-014 and the feature tasks.
- **The 15 categories and all [P] field names are unconfirmed** by the team.
- **The vector index syntax** is taken from `gcloud firestore indexes composite create --help` on 2026-09-25 and has not been run.

## Definition of Done

Documentation:
- [x] Written in Markdown with consistent headings, tables and code blocks
- [ ] Reviewed by at least one other teammate
- [ ] Committed to `/docs`
- [x] No AI attribution in the files

Firestore Schema Change checklist:
- [x] Migration script: not needed, no data exists yet and nothing was written to Firestore
- [ ] Security rules updated: not part of this task (NF-P1-014), the access matrix is ready for it
- [ ] Firestore Emulator tests pass: not run (see above); paths and examples checked with the client library instead
- [x] Docs updated (this task)
- [x] Version metadata: defined in `versioning.md` (`_meta.version`, prompt versions, `schema_version`)

## Commit

Branch: `docs/data-firestore-schema`. No shared files were changed.

```bash
git add docs/data-model docs/runbooks/NF-P1-013-firestore-schema.md
git commit -m "docs(data): document the Firestore schema and collection paths" -m "Refs: NF-P1-013"
```

Before pushing, run `git status` and confirm nothing else is listed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: google.cloud` when running the check | Use the backend virtualenv's Python, not the system one |
| The check prints `BAD <path>` | A sample document's path has the wrong number of segments. A document path must have an even number (`collection/doc/collection/doc`). |
| `json.JSONDecodeError` | A sample document is not valid JSON (trailing comma, comment or unquoted key). Fix the block. |
| The check prints fewer than 19 `ok` lines | A new example does not use the exact marker `**Example** — \`path\`` followed by a blank line and a `json` block |
| Someone asks where the docs are, since the tracker says `docs/data-model.md` | The repo has the folder `docs/data-model/`. Start at `firestore-schema.md`. |
| A field in a doc disagrees with code | If the code is right, fix the doc in the same pull request and follow the checklist in `versioning.md`. |

## Not covered here

- The security rules file: NF-P1-014
- Index files (`firestore.indexes.json`): the feature tasks that add the queries
- Loading data: NF-P1-016 (corridors), NF-P1-018 (labor laws), NF-P3-005 and NF-P3-015 (demo data)
- Pydantic models and TypeScript types for these documents: each pillar task
- Updating the original design's table 4.7 (and the `.docx`) to the corrected paths
- The final review of these docs after the pillars are built: NF-P4-020
