# NF-F0-005 — Feature flag service

## Summary

The Coach and the Scam Analyzer can now be switched on and off from Firestore, without a deploy. `config/feature_flags` holds one flag per module; the backend reads it at most once a minute and answers two questions: **is this module on for this user** (`require_flag`, for a route to ask) and **which modules are on for me** (`GET /api/v2/flags`, for the frontend to ask). A flag that is off for the caller makes a guarded route answer `404 Not Found`, the same as a path that does not exist.

A flag is on for a user when its `enabled` is `true` **or** the user's uid is in its `allow_uids`. So `enabled: false` with a list turns a module on for named testers only. Nothing guards a real route yet: the coach and scam routes do not exist (NF-FC-008, NF-SA-007). This task gives them the guard.

The route is the first under `/api/v2`, so it creates `backend/app/api/v2/` and mounts it, as `docs/api/v2-conventions.md` says. It also closes D-98 (the CORS names for v2). No v1 file changed.

## What is read, and what happens when it is wrong

| Situation | Result |
|---|---|
| Document missing, `flags` missing or not a map | Everything off |
| One flag missing, not a map, or `enabled` not the boolean `true` (`"true"`, `1`) | That flag is off |
| `allow_uids` not a list, or entries that are not strings | The list is empty; `enabled` still counts |
| `allow_uids` longer than 200 | The first 200 are used, a warning is logged; the flag is not turned off |
| A flag name other than `coach` and `scam` | Ignored |
| Firestore cannot be read | The last good copy is kept (everything off if there never was one) and the next request tries again |

Reading never fails open: nothing here can turn a module on that the document does not turn on.

## Files

| File | Purpose |
|---|---|
| `backend/app/repositories/config_repo.py` (new) | Reads `config/feature_flags`; read-only |
| `backend/app/services/feature_flag_service.py` (new) | Parses the document, keeps the 60-second copy, answers `is_enabled(flag, uid)` and `enabled_for(uid)` |
| `backend/app/dependencies.py` | `require_flag(flag)` and `get_feature_flag_service` |
| `backend/app/schemas/feature_flags.py` (new) | `FeatureFlagsResponse` |
| `backend/app/api/v2/` (new: `__init__.py`, `router.py`, `flags.py`), `backend/app/main.py` | `GET /api/v2/flags`; the v2 router is mounted at `/api/v2`; CORS allows `Idempotency-Key` and exposes `Idempotency-Replayed`, `Deprecation` and `Sunset` (D-98) |
| `backend/tests/unit/services/test_feature_flag_service.py` (new) | 23 service tests |
| `backend/tests/integration/api/test_feature_flags.py` (new) | 9 route and guard tests |
| `backend/tests/integration/api/test_cors_rate_limit.py` | 1 test for the v2 CORS headers |
| `docs/api/v2-flags.md` (new), `docs/data-model/collections/config.md` | Contract, read rules, D-98 closed |

No new package, environment variable or shared file.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The flag-off answer is exactly the unknown-path answer: `404`, message `Not Found`. | A disabled module cannot be told from a missing one. Under `/api/v2` the error handler wraps it in the standard envelope (code `not_found`) by itself; `test_feature_flags.py` checks this with a throwaway route. |
| 2 | The guard needs the caller's uid, so a request without a valid token is `401` first. | The allow-list is per uid. Every route behind sign-in answers `401` the same way, so this reveals nothing about a flag. |
| 3 | The one-minute copy is per Cloud Run instance, in memory. | Matches the "within 60 s, no redeploy" goal. With several instances a change can show up on each at a different second inside the minute. |
| 4 | A failed read keeps the last good copy. | An outage should neither hide a module that was on nor switch one on. |
| 5 | The cache is in the service, not in the empty `core/cache.py` stub. | One cached value does not need a general cache class. |
| 6 | `GET /api/v2/flags` returns booleans only, never `allow_uids`. | Other people's uids must not reach a browser. |

## Turning a flag on or off (operator)

The document does not exist until someone creates it, and **with no document everything is off**, which is the state production should ship in. No API changes a flag.

In the Firebase console → Firestore Database → `nomadfinance-prod`: start the collection `config` with the document id `feature_flags` and these fields:

| Field | Type | Value |
|---|---|---|
| `flags` | map | with two keys below |
| `flags.coach` | map | `enabled` (boolean) `false`, `allow_uids` (array of string) empty |
| `flags.scam` | map | `enabled` (boolean) `false`, `allow_uids` (array of string) empty |
| `updated_at` | timestamp | now |
| `updated_by` | string | your initials |
| `schema_version` | number | `1` |

The same as JSON, for reference:

```json
{
  "flags": {
    "coach": { "enabled": false, "allow_uids": [] },
    "scam": { "enabled": false, "allow_uids": [] }
  },
  "updated_at": "2026-10-24T08:00:00Z",
  "updated_by": "XX",
  "schema_version": 1
}
```

- **Test with named people first:** put their uids in `allow_uids`, keep `enabled` `false`.
- **Switch on for everyone:** `enabled` `true`.
- **Rollback (first step of any rollback):** `enabled` `false` and clear `allow_uids`.
- **Takes effect** within 60 seconds on each instance. Staging and production each have their own document (NF-F0-011 decides how).
- **Firestore rules:** a browser cannot read `config` (rules from NF-F0-004), so a console edit is the only way in.

## Manual test

Start the emulators and the API (`.claude/launch.json`: `backend-emulators`, `backend-api-emulator`), or from `backend/` with the venv active.

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
$env:APP_ENV="local"; $env:FIREBASE_PROJECT_ID="demo-nomadfinance"
$env:FIRESTORE_EMULATOR_HOST="127.0.0.1:8085"; $env:FIREBASE_AUTH_EMULATOR_HOST="127.0.0.1:9099"
$env:GEMINI_API_KEY="not-used-here"
uvicorn app.main:app --port 8080
```

bash:

```bash
source .venv/bin/activate   # .venv/Scripts/activate on Windows Git Bash
APP_ENV=local FIREBASE_PROJECT_ID=demo-nomadfinance FIRESTORE_EMULATOR_HOST=127.0.0.1:8085 \
FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099 GEMINI_API_KEY=not-used-here \
uvicorn app.main:app --port 8080
```

Then, with a token for a signed-in test user (`$ID_TOKEN`):

```bash
curl -s http://127.0.0.1:8080/api/v2/flags -H "Authorization: Bearer $ID_TOKEN"
```

1. No document yet: `{"coach":false,"scam":false}`. No token: `401`.
2. Create `config/feature_flags` in the emulator UI (http://127.0.0.1:4000, Firestore) as in the table above with `scam.enabled` `true`. Call again at once: still all `false` (the one-minute copy). After 60 seconds: `{"coach":false,"scam":true}`.
3. Put the test user's uid in `flags.coach.allow_uids`: after a minute `coach` is `true` for that user and `false` for any other.
4. Set `scam.enabled` back to `false`: after a minute it is `false` again.

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `black --check app tests`, `ruff check app tests` | clean |
| `mypy --strict app/services/`, `mypy app` | clean (45 and 137 files) |
| `pytest tests` | 1,075 passed, 60 skipped (live Gemini); 33 are new |
| Live, Auth and Firestore emulators, real signed-in test users | no document → all off; after writing the document the old answer for the full minute, then the new one; allow-listed user on while the other is off; switch-off applied after the next minute; no token → 401 |

Not verified: a real production document, and several Cloud Run instances reading at different moments.

## Not done, and why

- **A route that is actually guarded:** no coach or scam route exists yet. Each one adds `Depends(require_flag(...))` when it is written.
- **Frontend hook, `<FlagGate>`, lazy routes:** NF-F0-006. It reads `GET /api/v2/flags`.
- **The Firestore document itself:** an operator creates it, steps above.
- **Staging and production copies:** NF-F0-011.

## Commit

```bash
git commit -m "feat(flags): add feature flag service and require_flag dependency" -m "Refs: NF-F0-005"
```

PR title: `feat(flags): feature flag service, require_flag guard and GET /api/v2/flags (NF-F0-005)`
