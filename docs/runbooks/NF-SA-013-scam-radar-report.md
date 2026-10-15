# NF-SA-013 — One-tap report to Exploitation Radar

## Summary

`POST /api/v2/scam/checks/{id}/report` turns one of the worker's stored scam checks into an anonymous Radar report, exactly as the confirmation sheet showed it (docs/api/v2-scam.md). The worker sends the ids of the indicators they left ticked and, optionally, the text as they edited it.

- **`201`** with `{report_id, already_reported: false, entity_slug, entity_name, created_at}` for a new report; **`200`** with `already_reported: true` and the first report for a check that was reported already.
- **`409 not_a_scam`** when the check's verdict is not a scam. **`422`** for an indicator id not in the check, a repeat, more than 10, or an empty or over-long text. **`404`** for a check that is unknown, expired or someone else's (the same answer for all three).
- The report is about **a kind of scam**, not a business: entity type `scam_type`, named with the taxonomy label, slug `scam-illegal-recruitment-fee`; violation type `scam_message`; source `scam_check`. Its `scam` map holds the type, tactics, risk, confidence, trigger phrases, what the message asks for and **only the indicators the worker confirmed**.

**Anonymous by construction.** No uid, no reporter hash, no check id, no raw message and no screenshot is stored. The text is **masked again** (the worker can type anything into the box). A test fails if the report or the log holds the uid or the check id, and two deliberate breakages (leaking the check id, skipping the re-masking) were each caught.

Not in this task: the confirmation sheet and the Radar screens (NF-SA-018, NF-SA-016), masking personal names (D-108), removing old indicator values after a year (D-110). The dependency NF-SA-012 (stored checks) is merged.

## How it works

```
POST .../checks/{id}/report
  load the check (owner only; expired = absent)  → 404
  verdict is a scam?                              → 409 not_a_scam
  already reported?                               → 200, the first report, nothing written
  ids ⊆ the check's indicators?                   → 422
  mask the text again, cut to 1,000 characters
  embed it (Gemini) and find its cluster (the same two steps every Radar report goes through)
  ┌ one Firestore transaction ──────────────────────────────────────────────────────────┐
  │ read the check (already reported by another tap? → write nothing, return its report)  │
  │ read the ticked indicators' documents                                                 │
  │ write radar_reports/{id}  +  scam_indicators/{key} for each (counters)  +  the check's│
  │ reported_report_id, reported_at                                                       │
  └───────────────────────────────────────────────────────────────────────────────────────┘
  after the commit, best effort: the report's vector, and the entity's profile (radar_entities/scam-…)
```

- **One transaction** so a check is reported once and the counters cannot drift from the reports. The Gemini call is made before it, never inside it.
- **Indicator counters** (`scam_indicators/{first 32 hex of the key}`): `report_count` goes up for every report; `incident_count` only when the report began a new similarity cluster, so one worker repeating a message does not make a number look widespread; `flagged` at 2 incidents (the rule `radar_entities` uses); a `hidden` document stays hidden and is still counted; `expires_at` is a year after the last report. The key function is the one the reader of NF-SA-012 uses, and a test writes a sender in one spelling and reads it back in another.
- **host country**: the worker's profile, else the corridor's host; a check with neither is still reported (the alert job and heatmap, which group by corridor or country, skip it).
- **The report counts in Radar** like any other: its vector is stored for later similarity, and `update_entity_risk` folds it into `radar_entities/scam-…`, which is `flagged` at 2 incidents. Radar's entity report list now returns the `scam` map (D-124, the backend half) and still leaves out `reporter_hash` and the validation internals.
- **A worker's own report form cannot produce a scam report.** The new values `scam_type`, `scam_message` and `scam_check` are only in the stored types; the form and the two models that read a free-text report keep the old, narrower types, and a test refuses the new ones.

## Two taps at once

A repeat tap that arrives after the first finished is the normal case and is answered with `200` (tested in memory and on Firestore). Two taps that start at the same instant each hold the check and wait on the other. On the Firestore emulator the client gave up on one of them (`Transaction lock timeout`) in about one run in four; the other tap's report stood, and the worker's retry got it. What must never happen does not: **no second report and no second count**, and a test of exactly that passes on the emulator (stable over three runs and a mutation check). What a simultaneous double tap cannot promise is that both taps succeed. The emulator is not real Firestore, which resolves such conflicts its own way: D-148 records it and says what to change if a tap is ever seen to fail on the live Firestore.

## Files

| File | Change |
|---|---|
| `backend/app/repositories/scam_report_repo.py` (new) | `commit_report` (the transaction) and `merge_indicator` (the counters, a pure function) |
| `backend/app/services/scam/report.py` (new) | `ScamReporter`: the checks, the masking, the embedding and cluster, the report, the after-commit steps |
| `backend/app/schemas/radar_scam.py` (new), `radar.py`, `radar_report.py` | The `scam` map; the stored Radar types widened, the form's and the models' kept narrow |
| `backend/app/services/radar/entity_reports.py` | Returns `scam` (D-124) |
| `backend/app/api/v2/scam_checks.py`, `backend/app/dependencies.py` | The route and its dependency |
| `backend/app/services/scam/indicator_seen.py`, `history.py` | The document id uses the key's normal form (a sender is lowercase); a small id helper |
| `backend/tests/unit/services/test_scam_report.py` (38), `tests/unit/repositories/test_scam_report_merge.py` (11), `tests/integration/api/test_scam_report.py` (24), `tests/integration/repositories/test_scam_report_repository.py` (11, on the emulator), `tests/unit/test_radar_user_types.py` (4), additions to `test_radar_entity_reports.py`, `test_auth_matrix.py`; fixtures `tests/fixtures/scam_report.py`, `scam_app.py` | The tests |
| `docs/api/v2-scam.md`, `docs/data-model/collections/radar.md` | State, rate limit, host-country rule, D-124, D-145 and D-104 closed on the backend side, D-148 and D-149 |

No shared files, no new dependency, no workflow change. The contract's request and response models did not change.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The check is read inside the transaction, and the Gemini call is made before it | The once-only rule needs the read in the transaction; a model call must not hold one open |
| 2 | Embedding and the entity update come after the commit and may fail without losing the report | The same treatment every Radar path gives them (`intake.py`, `aggregation.py`) |
| 3 | `validation` holds the analyzer's real values: spam score 0, the verdict's confidence, the model the check recorded | The data model says no invented numbers; there is no spam check because the analyzer already classified the message |
| 4 | The route uses the AI budget (10 a minute) | It embeds the text, which is a Gemini call; the auth matrix lists it |
| 5 | The worker's text is masked again and cut at 1,000 characters | Nothing the worker sends is trusted to be clean; names are not masked by a pattern (D-108) |
| 6 | The safety of two simultaneous taps is tested; both succeeding is not promised | Shown on the emulator; real Firestore is untested (D-148) |

## Checks run (2026-10-07)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .`, `mypy app`, `mypy --strict app/services` (backend) | clean |
| `pytest` (backend) | **1954 passed, 113 skipped** (the live and emulator tests) |
| The 11 new transaction tests on a **real Firestore emulator** | **11 passed**, three runs in a row. Also all 40 emulator repository tests: **40 passed** |
| Mutation checks | Putting the check id into the report fails 2 tests; not re-masking the text fails 2; removing the once-only guard fails 2 emulator tests. Each was restored |
| Caught on the way | The emulator showed that two taps starting together can leave one with "Failed to commit transaction in 5 attempts": the test was rewritten to what is guaranteed, a fallback was added (if the other tap has reported the check, its report is returned), and D-148 records the rest. Also: a sender's `scam_indicators` id was made from its value as written, not in lowercase as its key says; fixed in the reader so reader and writer agree |
| Not run | Anything against the real project: the Radar aggregation is shown here by the tests, which fold the report into `radar_entities/scam-…`, and the transaction by the Firestore emulator, not by a run on the live Firestore |

## Try it

With the backend running, a token, the taxonomy loaded and the `scam` flag on (commands in `docs/api/v2-scam.md`): analyze a scam message, take its `id` and the `id` of an indicator from the answer, then

```bash
curl -s -X POST http://127.0.0.1:8080/api/v2/scam/checks/<check id>/report \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"indicator_ids": ["<indicator id>"]}'
```

Expect `201` and an `entity_slug`; the same command again gives `200` and `"already_reported": true`. Then `GET /api/v1/radar/entities/<entity_slug>/reports` lists the report with its `scam` map, and `GET /api/v2/scam/checks/<check id>` shows `reported: true` and the indicator's `seen`.

## Not done, and why

- **No run on the live Firestore** (D-148 for the concurrency check): there is no staging project, and a test report written to the real project would be a real Radar report.
- **Names in the text are not masked** (D-108): the sheet is the guard.
- **Old indicator values stay in old reports** (D-110).
- **The screens, labels and layout** for scam reports in Radar (NF-SA-018, D-124).
- **Alert and notification wording for a scam type** (D-149).

## Definition of Done (backend endpoint; the tracker's own)

- [x] Creates an anonymised `radar_reports` entry (type `scam_message`) pre-filled from the verdict, which flows into Radar clustering and the entity's aggregation (shown by the tests)
- [x] Duplicate reports of the same check are idempotent (in memory, and on the emulator, including a race)
- [x] Pydantic models, token check, error envelope with the right statuses, rate limit applied, docs updated
- [x] Tests, lint, format, types
- [x] The report is folded into Radar's entity aggregation (shown by the tests and on the emulator; there is no staging to run it on)
- [ ] Two simultaneous taps checked on the live Firestore (D-148, only if it is ever seen in the logs)
