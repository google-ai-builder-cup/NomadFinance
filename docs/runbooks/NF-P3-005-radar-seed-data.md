# NF-P3-005 — Radar: Seed Data for Demo

## Summary

Loads 18 synthetic reports into `radar_reports` and the matching profiles into `radar_entities`, so the heatmap, the "community flagged" badges and the alert cron have something to show in the demo. Data-scripts only: no backend or frontend change.

Not in this task: alerts (the NF-P3-004 cron creates them from the reports), embeddings (need Gemini; see Limits), the heatmap UI (NF-P3-007), demo users and contracts (their seed files are still empty stubs).

## What the data looks like

Eight invented businesses (names are fictional; check none matches a real company before a public demo):

| Business | Type | Where | Reports / incidents | Profile |
|---|---|---|---|---|
| Merlion QuickSend | operator | SG-PH | 4 / 3 | medium, 3.5, flagged; 4 reports in 7 days = warning alert |
| Kapitan Padala | operator | JP-PH | 2 / 2 | medium, 4.0, flagged |
| Ganga Transfer Hub | operator | SG-IN | 2 / 2 | medium, 4.0, flagged |
| Southern Cross Remit | operator | AU-IN | 1 / 1 | low, no rating, not flagged |
| Nusantara Kirim | operator | MY-ID | 1 / 1 | low, no rating, not flagged |
| Bayanihan Overseas Recruitment | agency | AU-PH | 5 / 5 | **high**, 2.5, flagged; 4 in 7 days = warning alert |
| Han River Metals Co | employer | KR | 2 / 2 | medium, 4.0, flagged; 2 in 7 days = info alert |
| Lantau Bay Household | employer | HK | 1 / 1 | low, no rating, not flagged |

- All six corridors and all six host countries appear. Employer reports have `host_country` only (no corridor).
- `seed_02` repeats `seed_01`'s incident (same `cluster_id`), so Merlion shows 4 reports but 3 incidents; this demonstrates unique-incident counting.
- Languages: en, tl, hi, id. Short descriptions; have a native speaker check the tl, hi and id lines before showing them.
- Every report has `source: "seed"`, `validation.model: "seed"`, no `reporter_hash`, no `summary`, per `docs/data-model/collections/radar.md`.
- Profile numbers use the backend's rules (`services/radar/aggregation.py`: rating `max(0, 5 − 0.5 × incidents)`, null below 2 incidents, high at 5). The loader has its own copy of the constants; change both together.

## Files

- `data-scripts/data/seed/radar-reports/seed_reports.json` — the reports (`hours_ago` instead of timestamps)
- `data-scripts/src/validators/radar_seed.py` — schema and cross-checks (15 to 20 reports, valid corridors, clusters stay inside one business, every corridor covered)
- `data-scripts/src/loaders/radar_seed.py` — the loader
- `data-scripts/src/config.py` — `RADAR_SEED_FILE`
- `data-scripts/scripts/seed_demo.sh` — calls the loader
- `data-scripts/tests/test_radar_seed.py` — 10 tests with a fake Firestore client

## Run it

From `data-scripts/` with the venv active (see the README). Same Firestore identity as the other loaders: `gcloud auth application-default login`, or `FIRESTORE_EMULATOR_HOST` pointed at an emulator.

```bash
python -m src.validators.radar_seed
python -m src.loaders.radar_seed --dry-run
python -m src.loaders.radar_seed
```

PowerShell is the same; only the venv activation differs (`.\.venv\Scripts\Activate.ps1`).

Expected: `Wrote 18 reports and 8 profiles, removed 0 stale`. Run it again: same counts, no duplicates.

## Behaviour worth knowing

- **One atomic batch**: reports, profiles and stale deletes commit together or not at all.
- **Timestamps are relative to load time.** The alert cron looks at the last 7 days, so the surges above only appear if the loader ran within a few days. Re-run it the day before a demo, then trigger the cron once (`POST /api/v1/internal/aggregate-radar`, NF-P3-004; it needs the scheduler credentials) to get the alerts.
- **Stale cleanup**: a seed report deleted from the file is deleted from Firestore on the next run (matched on `source == "seed"`; worker reports are never touched).
- **Real reports win**: if a worker report already exists for a seed business (same slug), that profile is skipped with a warning rather than overwritten.
- **Emulator vs real project**: the default project is `nomadfinance-prod`. Set `FIREBASE_PROJECT_ID` to point elsewhere. Loading demo data into the production project is a team decision; use the emulator to try it.

## Limits

- No `report_embeddings`. Worker reports submitted later will not cluster with seed reports, and the similarity threshold (`MAX_MATCH_DISTANCE`, NF-P3-002) still cannot be tuned against this data. Adding an `--embed` option is possible later; it needs Gemini access and quota.
- The seed reports are not removed by any backend job; delete them by `source == "seed"` if needed.

## Checks run

`black --check`, `ruff check`, `mypy src tests` clean; `pytest` in `data-scripts/`: 137 passed. Not run against a real Firestore or emulator.
