# NF-F0-003 — Firestore schema v2 (new collections)

## Summary

The eight collections of the Coach and the Scam Analyzer are now specified, with field tables, sample documents, retention and access, so NF-F0-004 (rules and indexes), NF-FC-001/-008 and NF-SA-001/-012 can build on one agreed shape. This is documentation only: no code, no rules, no data was changed.

| Collection | Holds | Written by | Client access | Retention | Detail |
|---|---|---|---|---|---|
| `users/{uid}/coach_sessions/{id}` | Interview: stage, slots, redacted transcript | Backend | Owner reads | TTL, 30 days after last activity | [coach](../data-model/collections/coach.md) |
| `users/{uid}/coach_plans/{id}` | Score, 90-day plan, check-in markers | Backend | Owner reads | Until the account is deleted | [coach](../data-model/collections/coach.md) |
| `users/{uid}/coach_plans/{id}/translations/{lang}` | The plan in another language | Backend | Owner reads | Same as the plan | [coach](../data-model/collections/coach.md) |
| `users/{uid}/scam_checks/{id}` | Redacted text, verdict, indicators, explainer | Backend | Owner reads | TTL, 90 days after the last check | [scam](../data-model/collections/scam.md) |
| `scam_taxonomy/{id}`, `_meta` | Scam types, tactics, version | Data script | Signed-in read | None | [scam](../data-model/collections/scam.md) |
| `scam_patterns/{id}` | Templates with 768-number vectors | Data script | None | None | [scam](../data-model/collections/scam.md) |
| `scam_indicators/{id}` | Reports per phone number, address or account ("reported N times") | Backend, with the report | None | TTL, 365 days after the last report | [scam](../data-model/collections/scam.md) |
| `cost_baselines/{host}` | Monthly costs for `SG`, `KR`, `MY`, `JP`, `HK`, `AU` | Data script | Signed-in read | None | [cost_baselines](../data-model/collections/cost_baselines.md) |
| `config/feature_flags` | Flags `coach`, `scam`, allow-lists | Operator | None | None | [config](../data-model/collections/config.md) |

The tracker names `docs/data-model.md`; in the repo that is the folder `docs/data-model/` (collection files and `firestore-schema.md`). The tracker's "UAE" in the baselines is read as Australia: the six documents are SG, KR, MY, JP, HK and AU.

## Decisions taken (Devam, 2026-10-06)

| # | Decision | Why |
|---|---|---|
| 1 | **A scam report in Radar carries the full picture of the scam**: type, tactics, trigger phrases, the redacted message text, what it asks for, and the phone numbers, addresses and accounts the worker confirmed. It carries nothing that says who sent it in: no uid, no reporter hash, no raw message, no screenshot. The Radar profile is "this kind of scam" (`entity_type: scam_type`), listing each report with its details. | Workers recognise a scam by specifics, not by a category. Anonymity is kept by not storing a reporter, not by hiding the content. |
| 2 | Stored `indicators` hold the values (host of a URL, phone, email, handle, sender) instead of masked placeholders, **a deliberate exception to design 2.5**. Limits: owner-only, 90 days, never logged, and nothing goes to Radar until the worker confirms each one. | The report needs the values; a number in a message may be the worker's own, so the worker decides. |
| 3 | Scam cache is per user (`cache_key` on the check). | No new collection and no cross-user leak. A shared cache can be added by NF-SA-012 if the quota demands it. |
| 4 | Retention: Coach sessions 30 days after last activity (idle 14 days is "abandoned"); scam checks 90 days; plans until account deletion. | Sessions and checks hold the most sensitive text and are not needed once the plan or verdict exists. |
| 5 | Plan id is the first 20 hex of the slot hash; translations are a subcollection; PDFs go under `exports/{uid}/`. | Same slots give the same plan with no query; account deletion already removes `exports/{uid}/`, which design 2.5 had flagged as a change for NF-FC-014. |
| 6 | Two indexes and three TTL policies must be created (below). | Without the group-scope index the check-in job fails; without TTL policies the retention above is not enforced. |
| 7 | Coach transcripts are stored with phones, emails, IDs, accounts and URLs masked; sessions carry a `revision` so concurrent turns cannot overwrite each other. | Same masking rule as everything else the worker types; two open tabs are common on a phone. |
| 8 | Owner reads sessions, plans and checks; every write goes through the API. | The state machine and the guardrails cannot be skipped. |
| 9 | **"Reported N times" is stored per indicator** in `scam_indicators` (D-104): one document per phone number, address or account, keyed by a hash so a lookup is a direct read. It is updated in the same transaction as the report, counts incidents as well as reports (so one worker repeating a report does not inflate it), is flagged at 2 incidents like Radar entities, and expires a year after the last report because numbers are reissued. | Radar's strongest warning is a repeat offender. Drift is impossible because the counters and the report commit together. |
| 10 | **A hide switch**: `hidden` on `radar_reports` and on `scam_indicators`, set by an operator. | A wrongly named number must be removable at once; who decides is still a process question (D-107). |

## Files

| File | Change |
|---|---|
| `docs/data-model/collections/coach.md` (new) | Sessions, plans, translations |
| `docs/data-model/collections/scam.md` (new) | Checks, taxonomy, patterns, indicator counts |
| `docs/data-model/collections/cost_baselines.md` (new) | Baselines |
| `docs/data-model/collections/config.md` (new) | Feature flags |
| `docs/data-model/collections/radar.md` | New values on `radar_reports`, the `scam` map and `hidden`, "Scam reports" section |
| `docs/data-model/collections/fib.md` | `goals`, `coach_signal`, `scam_signal` on the profile |
| `docs/data-model/collections/users.md` | `signal_sharing`; notification type `coach_checkin` |
| `docs/data-model/firestore-schema.md` | Map, access matrix, indexes, TTL, Storage path, open questions |
| `docs/data-model/versioning.md` | Taxonomy and baseline versions; what readers must tolerate |

Fields added to existing collections are optional and new enum values only, so no `schema_version` bump is needed (`versioning.md`, rule 1); the readers that must tolerate them are listed there.

## What NF-F0-004 builds from this

- Rules: the access column above, and `users/{uid}.signal_sharing` as a client-writable field.
- Indexes (`frontend/firestore.indexes.json`): the vector index on `scam_patterns.embedding` (768, flat) and the group-scope index on `coach_plans.departure_date`. Commands are in `firestore-schema.md`; their syntax was taken from `gcloud ... --help` and has not been run.
- TTL policies on `coach_sessions.expires_at`, `scam_checks.expires_at` and `scam_indicators.expires_at`, one `gcloud` command each, by someone with project access, for production and for staging.
- Emulator rule tests for allow and deny on every row.

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| Every sample document parses as JSON | 12 blocks, all valid |
| Sample arithmetic: slot-hash length and plan id, check-in dates (+30, +60, +90 days), TTL values (+30, +90, +365 days), `cache_key` length, indicator keys (the sample check ids and the `scam_indicators` id are real SHA-256 prefixes of kind and value), counters consistent (incidents <= reports, type counts add up, flagged at 2 incidents), low <= typical <= high | all pass |
| Naming against design 4.7 and the schema conventions | 129 field names, all `snake_case`; the only dotted keys are the prompt-version maps (`coach.plan`), the same style as `contract.compare` already in `versioning.md`. Collections are plural `snake_case`; worker-owned data sits under `users/{uid}`; reference data uses natural keys; every document has `schema_version`; AI-written documents record `models` and `prompt_versions`. |
| `gcloud firestore ... --help` | Syntax of the TTL and field-index commands checked; commands not run |

Not done, and not part of this task: rules, indexes and TTL in a real project, the migration (there is nothing to migrate: new collections only), and emulator tests (NF-F0-004).
