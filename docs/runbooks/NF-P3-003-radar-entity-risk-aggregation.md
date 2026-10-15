# NF-P3-003 — Radar: Entity Risk Aggregation

## Summary

Steps 8 and 9 of the Exploitation Radar pipeline: after a report is stored, recompute that business's running profile at `radar_entities/{slug}` — report and incident counts, violation tally, corridors/countries, community rating, risk level, and the `flagged` boolean the future cross-pillar badges (NF-P3-022, NF-P3-023) will read. `radar_repo.py`'s own comment already earmarked this: "Entity aggregation (NF-P3-003) adds its own methods later" — so the new methods went on the existing `RadarRepository`, not a new file.

Wired into **both** places that write a `radar_reports` document: `services/radar/intake.py` (NF-P3-001, a worker's own report) and `services/cross_pillar/contract_to_radar.py` (NF-P2-021, a contract-shield signal). The task says "when new reports come in" — a contract-flagged employer can only ever become `flagged` if this runs on that path too; that's the whole point of cross-pillar flow #4.

No frontend, no new API endpoint. Purely backend, purely triggered from existing writes.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/radar.py` | Added `RadarRiskLevel`, `RadarEntity` (matches `radar_entities/{slug}` exactly) |
| `backend/app/repositories/radar_repo.py` | `get_entity`/`set_entity` on the existing `RadarRepository`, mirroring the `_embeddings` pattern NF-P3-002 already established |
| `backend/app/services/radar/aggregation.py` (was an empty stub) | The recompute logic: `update_entity_risk()` + the pure `_apply_report()`/`_risk_level()`/`_community_rating()` |
| `backend/app/services/radar/intake.py` | Calls `update_entity_risk()` after `create_report` |
| `backend/app/services/cross_pillar/contract_to_radar.py` | Calls `update_entity_risk()` after each `create_report` in its loop |
| `backend/tests/unit/services/test_radar_aggregation.py` (new) | 13 tests on the formula itself |
| `backend/tests/unit/services/test_radar_intake.py`, `test_contract_to_radar.py`, `backend/tests/integration/api/test_radar_report.py` | Fakes extended with `get_entity`/`set_entity`; a few new assertions confirming the wiring |
| `docs/data-model/collections/radar.md` | Replaced "the formula belongs to NF-P3-003" with the actual formula; fixed the illustrative example's numbers to match it |

## Decisions

The rating formula isn't specified anywhere in the original design or `radar.md` (which explicitly punts it to this task), so this is this task's own design work. Full reasoning was worked through with you in chat before implementing; summarized here:

1. **`incident_count` (distinct clusters), not `report_count`, drives everything.** `radar.md` itself already defines this as "unique incidents" — the metric that resists both pile-on inflation (five people repeating the same clustered story) and repeat-report dilution (one person spamming the same complaint). A report that *joins* an existing cluster (NF-P3-002's `find_cluster` returned an existing `cluster_id`) adds to `report_count` only; a report that *starts* a new cluster (`cluster_id == report_id`) adds to both.
2. **`risk_level`: `low` below 2, `medium` at 2–4, `high` at 5+.** Round numbers, not derived from anything — legible and trivially retunable. The one number that actually matters is the floor at 2 (decision 3).
3. **`flagged` at 2+ incidents, not 1.** This decides whether a real, named business gets a public "community flagged" badge. Flagging on a single unverified report is a real defamation-adjacent risk for a legitimate business (and, on demo day, a single-bad-faith-report risk for the project itself). Requiring a second, independent incident is the cheapest guard against both, and matches the original design's own framing of this pillar as "pattern detection," not "first complaint wins."
4. **`community_rating = max(0, 5 − 0.5 × incident_count)`, rounded to 1 decimal; `null` below 2 incidents.** Linear decay: simplest curve that starts at a perfect 5 and reaches 0 by 10 incidents. Stays `null` below the same 2-incident floor as `flagged`, for the same reason — a rating on one report would look like false precision.
5. **A `contract_signal` report is weighted the same as a `user` report — one incident, full stop.** A contract signal comes from Contract Shield's own checked legal finding, arguably more trustworthy than a single unverified crowd complaint, and you could argue it should flag on its own. Not built: that would make `flagged`/`risk_level` depend on *which kind* of incident occurred, real added complexity with no seed data yet (NF-P3-005, which runs after this task) to test a mixed-source case against. Uniform incident-counting is simpler to reason about now; weighting by source is a contained, easy-to-review follow-up if wanted later.
6. **Kept deliberately simple overall, matching the team's own established pattern.** No severity-by-violation-type weighting, no time-decay, no confidence-weighting from the model's own `category_confidence`/`spam_score`. Same reasoning your teammate used for NF-P3-002's `MAX_MATCH_DISTANCE` and I used for NF-P3-001's `SPAM_SCORE_THRESHOLD`: a formula that's easy to explain and easy to retune later beats one that's precisely wrong with no data to check it against.
7. **Not transactional.** The `radar_entities` read-modify-write isn't wrapped in a Firestore transaction; two reports about the same business landing at the same instant could race and one update could be lost. Acceptable for this prototype's expected concurrency (a hackathon demo, not production traffic under real load) — flagged here rather than silently accepted.
8. **Best-effort, same treatment as NF-P3-002's embedding write.** A `GoogleAPICallError` while updating `radar_entities` is caught and logged, never raised — it costs that entity's own updated badge/rating, never the report that was just successfully stored.
9. **Both `FlaggedProviderBadge.tsx` (NF-P3-022) and the Contract Shield employer badge (NF-P3-023) were explicitly kept out of this task**, per your call — both are now unblocked (this task is their last real dependency) and ready to pick up as their own normal-scope tasks.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .` | Clean |
| `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (36 files) |
| `mypy app/` (whole app, informational) | Clean (120 files) |
| `pytest` (full suite) | 687 passed (34 new), 51 skipped (pre-existing live-Gemini tests) — up from 653 before this task |
| New: `test_radar_aggregation.py` | 13 tests — new-entity creation, join-vs-new-incident counting, the full risk/flag/rating table parametrized across the thresholds, corridor/country dedup, violation tally accumulation, first/last-seen span tracking, a Firestore failure swallowed not raised |
| Extended: `test_radar_intake.py` (+3), `test_contract_to_radar.py` (+1), `test_radar_report.py` (+1 assertion) | Confirm the wiring itself: a worker report and a contract signal both actually update `radar_entities`, a joined cluster doesn't double-count as a new incident |
| Banned-word scan across every changed file | Clean, no matches |

## Manual test steps

No new endpoint or UI surface to click through — this is triggered internally by `POST /api/v1/radar/report` (NF-P3-001) and the contract analysis pipeline (NF-P2-021's signal). To see it live against the Firestore emulator:

bash / PowerShell (same commands, both platforms):
```bash
# 1. Submit two reports about the same business that will each start their own cluster
#    (different enough descriptions that NF-P3-002's clustering won't merge them).
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type":"money_transfer_operator","entity_name":"Example Remit","corridor_id":"SG-IN","description":"They showed one rate and gave me a worse one at the counter.","language":"en"}' \
  http://127.0.0.1:8080/api/v1/radar/report

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type":"money_transfer_operator","entity_name":"Example Remit","corridor_id":"SG-IN","description":"Completely different problem: they kept my ID card until I paid an extra fee.","language":"en"}' \
  http://127.0.0.1:8080/api/v1/radar/report

# 2. Check the Firestore emulator UI (or `gcloud firestore` locally) at
#    radar_entities/example-remit: expect incident_count 2, flagged true, community_rating 4.0.
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `radar_entities/{slug}` never appears after a report | Check the logs for `radar_entity_update_failed` — this is caught, not raised, so the report itself still succeeds; a missing Firestore index or permission issue on the new collection would show up only here |
| `incident_count` doesn't increase on a report that should be a new incident | Check `report.cluster_id == report_id` at the call site — if NF-P3-002's clustering incorrectly matched an unrelated report, this function trusts that signal completely and won't second-guess it |
| Two reports at once only update one increment | Known, accepted limitation — see decision 7. Not a bug to chase for this prototype |

## Definition of Done

**Firestore Schema Change** (closest-fitting checklist — this adds a real, documented shape to an existing collection's write path, not a new endpoint)
- [x] No migration needed — `radar_entities` had no prior documents to migrate
- [x] Security rules — checked: `radar_entities` was already in the signed-in-read allowlist (`frontend/firestore.rules`), provisioned ahead of this task; no change needed
- [x] `docs/data-model/collections/radar.md` updated — the formula placeholder replaced, the illustrative example's numbers fixed to match
- [ ] Firestore Emulator tests — not run live in this session (see Manual test steps); the mypy/pytest suite ran against fakes only
- [x] No version metadata to bump — `radar_entities.schema_version` stays `1`, this task doesn't change the shape, only fills in a formula the shape already anticipated

## Commit and PR

Branch: `feature/radar-entity-risk` (already checked out).

```
feat(radar): add entity risk aggregation
Refs: NF-P3-003
```

PR title: `feat: exploitation radar entity risk aggregation (NF-P3-003)`

## Noticed, not fixed

- No corridor-level split on `radar_entities` — an entity's risk is aggregated globally across every corridor/country it's been reported in, even though behavior could genuinely differ by corridor. Not a choice this task made: `radar_entities/{slug}` is one document per entity, full stop, per `radar.md`'s own shape.
- `aliases` (merging spelling variants of the same business) stays manual/unbuilt, exactly as `radar.md` already called out before this task.
