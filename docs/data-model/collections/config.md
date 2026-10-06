# config

Operator settings that the backend reads at run time. For now the only document is the feature flags of the Future Scope modules (NF-F0-003, used by NF-F0-005 and NF-F0-006). Shape sources: the path and the idea of a global value plus an allow-list are **[T]** (tracker NF-F0-005); field names are **[P]**.

```
config/feature_flags
```

## `config/feature_flags`

One document. Both Future Scope modules ship dark and are turned on one at a time (design 2.1).

| Field | Type | Required | Description |
|---|---|---|---|
| `flags` | map | yes | Flag name to `{ "enabled": bool, "allow_uids": [string] }`. Known names: `coach`, `scam`. A new module adds a key; no schema change. |
| `updated_at` | timestamp | yes | |
| `updated_by` | string | yes | Initials of the person who changed it |
| `schema_version` | number | yes | `1` |

**A flag is on for a user when `enabled` is `true`, or the user's uid is in `allow_uids`.** So `enabled: false` with a list turns a module on for named testers only. The rules that follow:

- A missing document, a missing flag, or a malformed value means **off**. Reading never fails open.
- `allow_uids` holds at most 200 uids (the document limit is far larger; this keeps it readable by a person). The backend reads the first 200 and ignores the rest, so a longer list never turns a module off for everyone.
- Only the boolean `true` turns `enabled` on. `"true"`, `1` or a missing key mean off.
- If Firestore cannot be read, the backend keeps the last good copy it had, or treats every flag as off if it never had one.
- The backend reads the document at most once every 60 seconds (cached in memory), so a change takes effect within a minute with no deploy (NF-F0-005). A flag that is off makes the module's `/api/v2` routes answer `404` in the error envelope.
- The frontend does not read this document. It asks the API (`GET /api/v2/flags`, built in NF-F0-005 (`docs/api/v2-flags.md`), used by `useFeatureFlag()` in NF-F0-006), which answers for the signed-in user, so an allow-list of other people's uids never reaches a browser.
- Staging and production each have their own copy, because they are separate databases or prefixes (NF-F0-011). The repository layer applies the prefix; the path in code stays `config/feature_flags`.

**Example** — `config/feature_flags`

```json
{
  "flags": {
    "coach": { "enabled": false, "allow_uids": ["uid_priya_demo", "uid_rajesh_demo"] },
    "scam": { "enabled": true, "allow_uids": [] }
  },
  "updated_at": "2026-11-12T08:00:00Z",
  "updated_by": "DD",
  "schema_version": 1
}
```

**Written by:** an operator, in the Firebase console or with a short script. There is no API to change a flag.

**Access:** no client access; backend only.

## Rollback

Turning a flag off is the first step of any rollback (tracker, release rules): set `enabled` to `false` and clear `allow_uids`. Data the module already wrote stays where it is and is not shown.
