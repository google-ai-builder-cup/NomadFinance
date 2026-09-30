# NF-P3-004 — Radar: Alert Cron Job

Originally assigned to Devam; picked up because he wasn't available.

## Summary

`POST /api/v1/internal/aggregate-radar`, called by Cloud Scheduler every 6 hours: the AGG subgraph of the Exploitation Radar pipeline. For each of the 6 corridors, detects a *surge* — a business reported noticeably more in the last 7 days than in the 7 days before that — writes `radar_alerts/{corridor}/current/{alertId}`, expires alerts past their `expires_at`, and for each freshly created alert writes a `users/{uid}/notifications/{id}` in every subscribed worker's own language plus an FCM push.

Also covers two items pulled forward into this task at your explicit request: NF-P3-001's per-report `summary` now persists on `radar_reports` (previously response-only), and evidence-photo upload (`radar_reports.evidence_paths`, unowned by any task until now) got its backend half — a new endpoint to attach a photo or screenshot to an already-filed report. Frontend upload UI (NF-P3-006) is explicitly out of that scope; see Decisions.

Depends on NF-P3-003 (done) loosely, not by code reuse: surge detection reads raw `radar_reports` directly for their timestamps, since `radar_entities`'s running totals have no time window.

## Files

| File | Change |
|---|---|
| `backend/app/schemas/radar_alert.py` (new) | `RadarAlert`, `RadarAlertHeader` (`radar_alerts` documents), `AlertNotificationText` (Gemini's answer), `AggregateRadarResponse` (the endpoint's own response) |
| `backend/app/prompts/radar/alert_notification.v1.yaml` (new) | Classification-tier prompt: alert facts + language in, title/body out |
| `backend/app/repositories/radar_repo.py` | `reports_since`, and the `radar_alerts` header/alert CRUD (`get_alert_header`/`set_alert_header`/`get_active_alert`/`new_alert_id`/`create_alert`/`list_active_alerts`/`expire_alert`/`set_alert_notified`) |
| `backend/app/repositories/user_repo.py` | `by_host_and_home`, `subscribed_to_corridor`, `create_notification`, and `remove_fcm_token` — the one narrow write on a repo documented as otherwise read-only (see Decisions) |
| `backend/app/utils/corridors.py` (new) | `host_and_home(corridor_id)`: the 6 surveyed (host, home) pairs |
| `backend/app/integrations/firebase_messaging.py` (was an empty stub) | `send_push`: FCM multicast, returns tokens FCM reports gone for good |
| `backend/app/services/radar/alerts.py` (was an empty stub) | Surge detection (pure `_detect_surges`), alert dedup/expiry, the corridor loop |
| `backend/app/services/radar/notify.py` (new) | Subscriber matching, per-language text generation, notification write + FCM fan-out |
| `backend/app/api/v1/internal.py` | `POST /internal/aggregate-radar` |
| `infra/cloud-scheduler/radar-aggregation.yaml` (was an empty stub) | The Cloud Scheduler job config, mirroring `refresh-rates.yaml` |
| `docs/api/endpoints.md` | New endpoints' rows and sections |
| `backend/app/schemas/radar.py` | `RadarReport.summary` (new, optional) |
| `backend/app/services/radar/intake.py` | Persists `classification.summary` onto the stored report (was response-only) |
| `backend/app/schemas/radar_report.py` | `RadarEvidenceResponse`; updated the now-stale "not stored" note on `RadarReportResponse.summary` |
| `backend/app/integrations/cloud_storage.py` | `RadarEvidenceStore` — uploads to `radar-evidence/{report_id}/`, alongside the existing uid-scoped `UserFileStore` |
| `backend/app/repositories/radar_repo.py` | `add_evidence_path` |
| `backend/app/services/radar/evidence.py` (new) | Ownership check (via `reporter_hash`, never a stored uid), the 5-file cap, upload orchestration |
| `backend/app/api/v1/radar.py` | `POST /radar/report/{report_id}/evidence` |
| `docs/data-model/collections/radar.md` | `summary` and `evidence_paths` fields documented, formula placeholder resolved, example updated |
| `.github/workflows/scheduler-deploy.yml`, `infra/cloud-scheduler/{refresh-rates,radar-aggregation}.yaml` | Fixed a real, unrelated CI failure this task's push surfaced — see "The CI fix" below |
| 6 new test files | Surge detection, alert lifecycle, notification fan-out, evidence upload (unit + integration), one endpoint integration test |

`docs/data-model/firestore-schema.md`'s access matrix and required-index table already anticipated the alert-cron half of this task exactly (`radar_alerts`/`radar_entities` client-read-only, and the `radar_reports` `corridor_id`+`created_at` composite index credited to "NF-P3-004"). `storage.rules` already denied all browser access to `radar-evidence/` — confirmed, no change needed there for the evidence endpoint either.

## Decisions

This task's one-line description hides a lot of unspecified surface — same situation as NF-P3-003's rating formula. Confirmed with you before building:

1. **Surge window: 7 days, baseline: the 7 days before that.** Both numbers are already the illustrative values in `radar_alerts`'s own doc example, treated as intentional. A surge needs `report_count >= 2` in the window **and** more than the baseline — one report is an account, not a pattern (same floor as NF-P3-003's `flagged`).
2. **Severity: `info` at 2, `warning` at 3–4, `critical` at 5+** — the same cadence as NF-P3-003's risk levels, for consistency, not derived from anything.
3. **No duplicate alerts.** An entity with an already-`active` alert on a corridor is skipped, not re-alerted every 6 hours. `expires_at = created_at + 7 days`; each run also sweeps and expires anything past that, recomputing the corridor's `active_count` header.
4. **Notification text is Gemini-generated** (new prompt, classification tier), one call per `(alert, language actually needed among its subscribers)` — matching how every other user-facing text in this app is written, and your explicit choice over static templates. **You asked that this stay swappable if the always-on background cost becomes a problem**: `_text_for_language()` in `notify.py` is the one isolated function that would need replacing with a template lookup — nothing else in the call chain would change. No config flag was built for this now (nothing to toggle yet); the isolation is the actual insurance.
5. **Subscriber matching has two cohorts** (`users.md`: "missing means all on for the user's own corridor"): explicit (`notification_prefs.radar_corridors` names the corridor) and default (no `notification_prefs` at all, or prefs that never narrowed to specific corridors, and the worker's own `host_country`+`home_country` happen to form this corridor). Two of onboarding's five home-country options (Nepal, Bangladesh) aren't in any of the 6 corridors, so those workers simply have no default corridor. `utils/corridors.py` is a plain 6-entry lookup table, not string-parsing `corridor_id`, so it doesn't depend on the id's own format staying "HOST-HOME".
6. **`user_repo.py` was documented as read-only from the backend.** Removing an FCM token Firebase reports invalid is a narrow, real exception: a fact about delivery, not an edit to the worker's own choices. The docstring now says so explicitly rather than quietly breaking its own stated contract.
7. **The endpoint always answers 200.** Unlike `/refresh-rates` (which answers 503 so Cloud Scheduler retries a partial failure), a bad corridor or a bad recipient here is caught and logged inside `run_aggregation` itself — retrying the *whole* run would re-detect the same surges (harmless, dedup catches it) but also re-attempt notifying everyone who already succeeded (not harmless: duplicate pushes). Failure isolation happens per-corridor and per-recipient instead.
8. **Employer-type entities get no alerts.** `radar_alerts` is keyed by corridor only (`radar_alerts/{corridor}`), matching the design doc's own remittance-corridor framing ("3 workers in your corridor reported..."); an employer only ever has a `host_country`, not a `corridor_id`.
9. **The per-report `summary` (pulled forward from NF-P3-001) is a plain, additive schema field, not a cache of anything the alert cron reads.** It exists for a future consumer (a report list, NF-P3-008's entity profile page) to show one line instead of the full `description`. The alert cron's own notification text is generated fresh, from facts aggregated across *multiple* reports — a single report's summary was never going to fit that job, which is exactly why the original NF-P3-001 "noticed, not fixed" note was based on a wrong assumption about what NF-P3-004 would need.
10. **Evidence upload is a separate endpoint, not a field on `POST /radar/report`, and not a change to it at all.** `radar-evidence/{report_id}/` needs a real report id before anything can be filed under it, and switching the existing JSON endpoint to `multipart/form-data` to carry a file inline would have been a breaking change to an already-shipped, already-tested contract for no real benefit — a worker can just as easily attach evidence in a second call right after filing, or later.
11. **Evidence ownership is checked by re-hashing the caller's uid and comparing it to the report's stored `reporter_hash`** — never a stored uid-to-report mapping, which radar's whole anonymity model is built to avoid. A `contract_signal`/`seed` report (no `reporter_hash`) always answers `404`, not `403`: there is no worker to check ownership against, and `404` doesn't confirm to a prober whether a given id exists versus simply isn't theirs.
12. **Evidence upload is explicitly backend-only in this task**, per your direct choice: no frontend photo picker. NF-P3-006 (the multi-step submission form) remains its own separate, unowned task.
13. **The original file's own filename is never trusted or kept** — same reasoning as contract uploads: the real MIME type is sniffed from the bytes, and the stored filename is a fresh random id plus the extension that type implies, never anything the client sent.

## The CI fix

Filling in `radar-aggregation.yaml` triggered `scheduler-deploy.yml` (an existing, pre-existing-to-this-task workflow) on push to `main`, which loops over every `infra/cloud-scheduler/*.yaml` and creates a job that doesn't exist yet or updates one that does. Creating `radar-aggregation` succeeded; updating the *pre-existing* `refresh-rates` job (NF-P1-019) in the same run failed: `gcloud scheduler jobs update http` doesn't accept `--headers`, only `--update-headers` — a flag-name asymmetry with `create` that `refresh-rates.yaml` had carried, latent, since NF-P1-019, and that copying its pattern gave `radar-aggregation.yaml` too. Fixed by moving the (identical, for every job) `Content-Type` header out of the per-job yaml files entirely and into `scheduler-deploy.yml`, which now passes the correct flag name per subcommand. Confirmed with the real `gcloud ... --help` output for both subcommands before writing the fix, not guessed from the error message alone.

## Verified results (2026-10-01)

| Check | Result |
|---|---|
| `ruff check .`, `black --check .` | Clean |
| `mypy --strict app/services/` | Clean (38 files) |
| `mypy app/` (whole app, informational) | Clean (124 files) |
| `pytest` (full suite) | 745 passed (55 new), 51 skipped (pre-existing live-Gemini tests) — up from 690 before this task |
| New: `test_radar_alerts.py` (15) | `_detect_surges` (threshold, baseline comparison, most-reported violation type, independence across entities), severity bands, dedup, expiry + header recompute, one corridor's index failure not stopping the other five |
| New: `test_radar_notify.py` (14) | Both subscriber cohorts (default vs explicit, never double-counted, an opt-out honored, a narrower explicit choice overriding the default), one Gemini call per language not per subscriber, a failed language not retried per subscriber, FCM token kept vs removed, `notified_at` only set after an actual send, tag-injection escaping |
| New: `test_internal_aggregate_radar.py` (2) | A quiet run's response shape, hidden from `/openapi.json` (auth itself already covered by the existing `refresh-rates` test file, reused via the same override-the-dependency pattern it established) |
| New: `test_radar_evidence.py` (12, unit) | Upload + record, extension mapping for all 6 accepted types, the cap enforced before uploading, ownership (missing report, no-`reporter_hash` report, wrong uid), a second attachment from the real reporter |
| New: `test_radar_evidence.py` (12, integration) | The full endpoint: 201 happy path, 401/403/404/413/415/422, path-shape validation, hidden-field wiring, OpenAPI documented |
| Extended: `test_radar_intake.py` (+1) | `summary` is now persisted on the stored report, not just returned |
| Banned-word scan across every changed file | Clean, no matches |

**No live Gemini or FCM call was made** — same reasoning as NF-P3-001: didn't want to spend real quota, or send a real push to a real device, without asking first. The evidence endpoint makes no Gemini call at all, so this only applies to the alert-cron half.

## Manual test steps

**The composite index must exist before this runs against real Firestore** (staging/prod, or a non-empty local emulator), or `reports_since` fails with `FailedPrecondition` on every corridor (caught and logged, not fatal, but nothing will ever alert). Same situation as NF-P3-002's vector index:

```bash
gcloud firestore indexes composite create --project nomadfinance-prod \
  --collection-group=radar_reports --query-scope=COLLECTION \
  --field-config=field-path=corridor_id,order=ascending \
  --field-config=field-path=created_at,order=descending
```

Then, with the emulators running and `backend/.env.local` set up (same as every other task this session):

bash / PowerShell (same commands):
```bash
# 1. File two reports about the same business on the same corridor (NF-P3-001), far enough
#    apart in wording that clustering (NF-P3-002) starts two separate incidents.
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type":"money_transfer_operator","entity_name":"Example Remit","corridor_id":"SG-IN","description":"They showed one rate and gave me a worse one at the counter.","language":"en"}' \
  http://127.0.0.1:8080/api/v1/radar/report

curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"entity_type":"money_transfer_operator","entity_name":"Example Remit","corridor_id":"SG-IN","description":"Completely different problem: they kept my ID card until I paid an extra fee.","language":"en"}' \
  http://127.0.0.1:8080/api/v1/radar/report

# 2. Get a Cloud-Scheduler-shaped OIDC token for CRON_SERVICE_ACCOUNT/CRON_AUDIENCE (or run
#    against the emulator with require_cloud_scheduler overridden, as the tests do), then:
curl -s -X POST -H "Authorization: Bearer $CRON_TOKEN" http://127.0.0.1:8080/api/v1/internal/aggregate-radar

# 3. Check radar_alerts/SG-IN in the Firestore emulator UI: expect active_count 1, and
#    radar_alerts/SG-IN/current/{id} with report_count 2, severity "info", status "active".
# 4. If a test user has notification_prefs.radar_corridors including "SG-IN" (or matching
#    host/home with no prefs at all) and an fcm_token, check users/{uid}/notifications for
#    a new radar_alert document in their preferred_language.

# 5. Evidence: attach a photo to the first report above, using the same worker's token.
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg;type=image/jpeg" \
  "http://127.0.0.1:8080/api/v1/radar/report/<report_id from step 1>/evidence"
# Expect 201 with evidence_paths: ["radar-evidence/<report_id>/<random>.jpg"]. Retrying with
# a DIFFERENT worker's token against the same report_id should come back 403.
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `aggregate_radar` always returns everything at 0 | Almost certainly the missing composite index — check the logs for `radar_surge_detection_failed corridor=...`, caught silently by design (decision 7-adjacent: per-corridor isolation) |
| A worker never gets notified despite matching their corridor | Check `notification_prefs.radar_alerts` isn't explicitly `false`, and that `radar_corridors` (if set at all) actually includes the corridor — an explicit, narrower choice always wins over the host/home default |
| The same surge alerts every 6 hours instead of once | Check `get_active_alert` — an `active` alert for that `(corridor, entity_slug)` should short-circuit; if `status` was ever set to something other than `"active"`/`"expired"` by hand, dedup silently stops working |
| FCM push never arrives but the notification doc was written | Check `fcm_tokens` isn't empty, and check for `fcm_send_failed` in the logs — a non-`UnregisteredError` failure (quota, transient) is logged but the token is deliberately kept, not removed |
| Evidence upload always 404s even for a real report | Check the report's `source` — `contract_signal` and `seed` reports have no `reporter_hash`, so there is nothing to check ownership against, by design |
| Evidence upload 403s for the worker who actually filed the report | Check `RADAR_REPORTER_HASH_SECRET` hasn't changed since the report was filed — a changed secret makes every existing `reporter_hash` unverifiable, the same failure mode as NF-P3-001's own hash |

## Definition of Done

**Backend Endpoint — `/internal/aggregate-radar`**
- [x] Endpoint defined in FastAPI with a Pydantic response model (no request body, matching `/refresh-rates`)
- [x] Auth: Cloud Scheduler OIDC only, reusing the existing shared dependency; marked clearly as internal, hidden from `/docs`
- [x] Structured logging (`radar_aggregation` summary line; per-failure `radar_surge_detection_failed`/`radar_alert_text_failed`/`fcm_send_failed`)
- [x] Error handling — deliberately always 200 at the endpoint level; see decision 7 for why
- [ ] Manual test via Swagger — not run live (hidden from `/docs` by design; no Gemini/FCM spend without asking first; exact `curl` steps above)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting — exempt by design, same as every `/internal/*` endpoint (Cloud Scheduler only, never a browser)

**Backend Endpoint — `/radar/report/{report_id}/evidence`**
- [x] Endpoint defined in FastAPI with Pydantic request/response models
- [x] Firebase Auth token verification, plus an ownership check beyond just "signed in" (decision 11)
- [x] Structured logging — nothing extra needed; the base request-logging middleware already covers it, no Gemini call to log usage for
- [x] Error handling with specific HTTP status codes (400/401/403/404/413/415/422/429)
- [ ] Manual test via Swagger — not run live (needs a real report id from a prior live call; exact `curl` steps above)
- [x] `docs/api/endpoints.md` updated
- [x] Rate limiting applied (API-wide only, no Gemini call)

**Gemini Pipeline Step**
- [x] Correct tier (classification, for short notification text)
- [x] Structured output via Pydantic `response_schema`
- [x] Retry logic via tenacity (built into `GeminiClient`, reused as-is)
- [x] Timeout — default 30 s, no override needed (short output)
- [x] Token usage logged (existing `GeminiClient` logging)
- [x] Prompt stored in code, versioned (`radar/alert_notification.v1`)
- [ ] Tested with 3+ diverse inputs against the **real** model — tested against a fake Gemini client instead (29 automated cases across the two new service test files); a live pass needs your OK to spend quota

## Commit and PR

Branch: `feature/radar-alert-cron` (already checked out).

```
feat(radar): add alert cron job
Refs: NF-P3-004
```

PR title: `feat: exploitation radar alert cron job (NF-P3-004)`

## Noticed, not fixed

- Employer-type entities (host-country only, no corridor) never generate alerts — not a gap this task introduced; `radar_alerts` is corridor-keyed by its own documented shape.
- No corridor-level rate limit on how many alerts one corridor can generate per run — six corridors, a handful of surges expected at prototype scale, not worth building a cap for yet.
- No frontend for evidence upload — NF-P3-006 (the multi-step submission form) remains its own unowned task; the backend endpoint is ready for it whenever it's built.
- No frontend surface shows a report's `summary` yet either — same situation, waiting on whichever task first builds a report list or detail view (NF-P3-008 is the likely candidate).
