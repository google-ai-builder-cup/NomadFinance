# API v2: feature flags

Which Future Scope modules are switched on for the caller (NF-F0-005). Follows `docs/api/v2-conventions.md`. The first route under `/api/v2`. Flag document: `docs/data-model/collections/config.md`.

## `GET /api/v2/flags`

The frontend asks here instead of reading `config/feature_flags`, so the allow-lists of other people's uids never reach a browser.

- **Auth:** Firebase ID token (`get_current_user`). The answer is for the token's own uid.
- **Request:** no body, no parameters. No `Idempotency-Key` (a read).
- **Response `200`:**

```json
{ "coach": false, "scam": true }
```

One boolean per module, always both keys. A module is `true` when its flag has `enabled: true` or the caller's uid is in its `allow_uids`. A missing document, a missing flag or a malformed value is `false`.

- **Freshness:** the backend reads the document at most once every 60 seconds per instance, so a change in Firestore is visible here within a minute and needs no deploy. If Firestore cannot be read, the last good answer is kept; with none, everything is `false`.

| Status | `code` | When |
|---|---|---|
| `200` | | Always for a valid token |
| `401` | `unauthenticated` | Missing, invalid, expired or revoked token |
| `429` | `rate_limited` | Over 60 API calls a minute |

Errors use the standard envelope `{code, message, request_id}` (conventions, section 2).

```bash
# local, with the emulators running and a token for the signed-in user
curl -s http://127.0.0.1:8080/api/v2/flags -H "Authorization: Bearer $ID_TOKEN"
```

## Guarding a route behind a flag

A coach or scam route adds `dependencies=[Depends(require_flag("coach"))]` (`app/dependencies.py`). When the flag is off for the caller the answer is the same `404 Not Found` an unknown path gets, so a disabled module cannot be told from a missing one: the standard envelope with code `not_found`, message `Not Found`. A request with no valid token is a `401` before the flag is checked.
