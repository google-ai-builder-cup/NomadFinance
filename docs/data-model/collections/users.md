# users

Shape sources: `users/{uid}` and `notifications` are **[D]** (original design). The profile fields come from the NF-P1-022 task description **[T]**. The exact enums, `notification_prefs` and `fcm_tokens` are **[P]**.

## `users/{uid}`

One document per person. The id is the Firebase Auth `uid`, so the backend's `AuthenticatedUser.uid` (NF-P1-005) is the key with no lookup.

Firebase Auth already stores the name, email, phone number and photo. **Do not copy them here**: a copy goes stale and doubles the personal data held.

| Field | Type | Required | Description |
|---|---|---|---|
| `home_country` | string | after onboarding | ISO-2 country the money goes to. Onboarding offers `PH`, `IN`, `ID`, `NP`, `BD`. |
| `host_country` | string | after onboarding | One of `SG`, `KR`, `MY`, `JP`, `HK`, `AU` |
| `job_type` | string | after onboarding | `domestic_worker`, `manufacturing_worker`, `care_worker`, `plantation_worker`, `construction_worker`, `working_holiday`, `other` |
| `preferred_language` | string | after onboarding | `en`, `hi`, `tl`, `id`, `ne`, `bn`. Drives report language, notifications and SMS language. |
| `onboarding_completed_at` | timestamp | no | Absent until onboarding finishes. The app shows onboarding while it is absent. |
| `notification_prefs` | map | no | `radar_alerts` (bool), `radar_corridors` (array of corridor ids), `reminders` (bool). Missing means all on for the user's own corridor. |
| `signal_sharing` | map | no | **Future Scope (NF-HR-001).** `{ "coach": bool, "scam": bool }`: whether the worker lets the Coach plan or the scam-check activity appear as a signal in their Financial Identity report. **Off when absent: it is opt-in**, and setting it back to `false` removes the signal at the next recompute. Changed only on the profile page. **Read by the weekly recompute and by every report export (NF-HR-001)**; only a boolean `true` counts. |
| `fcm_tokens` | array of string | no | Push tokens of the user's browsers, at most 5. Remove a token when FCM reports it invalid. |
| `created_at` | timestamp | yes | Set once when the document is first written |
| `updated_at` | timestamp | yes | Updated on every write |
| `schema_version` | number | yes | Currently `1` |

The `job_type` list follows the demo contract files in `data-scripts/data/seed/contracts/` (domestic, manufacturing, care, plantation, working holiday) plus construction and `other`. NF-P1-022 confirms the final list.

**Example** — `users/uid_priya_demo`

```json
{
  "home_country": "IN",
  "host_country": "SG",
  "job_type": "domestic_worker",
  "preferred_language": "hi",
  "onboarding_completed_at": "2026-09-26T09:12:00Z",
  "notification_prefs": {
    "radar_alerts": true,
    "radar_corridors": ["SG-IN"],
    "reminders": true
  },
  "fcm_tokens": [],
  "created_at": "2026-09-26T09:10:31Z",
  "updated_at": "2026-09-26T09:12:00Z",
  "schema_version": 1
}
```

**Access:** owner reads; owner writes the profile fields only. The `uid` in the path must equal the caller's auth uid.

**Account deletion (NF-P1-023, `DELETE /api/v1/users/me`).** Firestore does not delete subcollections with their parent. The backend (`app/services/auth_service.py`) does these, in this order, and only for a caller who signed in within the last 5 minutes:
1. Recursively delete `users/{uid}` (all subcollections). The Admin SDK has `recursive_delete` for this.
2. Delete the user's files under `contracts/{uid}/`, `bills/{uid}/` and `exports/{uid}/` in Cloud Storage.
3. Delete the Firebase Auth user last.

`radar_reports` the user filed are **not** deleted. They hold only a salted hash of the reporter, never the uid, and they are part of the community record.

## `users/{uid}/notifications/{id}`

Alerts and reminders shown in the user's feed. The text is written in the user's `preferred_language` at creation time, so the feed and the push message read the same.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | yes | `radar_alert`, `reminder`, `system`, and `coach_checkin` (**Future Scope, NF-FC-016:** the day 30, 60 or 90 check-in of a Coach plan). The feed must show a type it does not know with a generic icon, not hide it. A `coach_checkin` follows the worker's `notification_prefs.reminders`. |
| `title` | string | yes | Short headline in `language` |
| `body` | string | yes | Message in `language` |
| `language` | string | yes | Language the text was written in |
| `deep_link` | string | no | In-app path opened on tap, for example `/radar` |
| `source` | map | no | Where it came from: `{ "kind": "radar_alert", "path": "radar_alerts/SG-IN/current/{alertId}" }`. For a Coach check-in: `{ "kind": "coach_checkin", "path": "users/{uid}/coach_plans/{planId}", "milestone": "d30" }` and `deep_link` `/coach/checkin/{planId}?m=30`. |
| `read` | boolean | yes | `false` when created |
| `read_at` | timestamp | no | Set when marked read |
| `created_at` | timestamp | yes | |
| `schema_version` | number | yes | `1` |

**Example** — `users/uid_priya_demo/notifications/n_01`

```json
{
  "type": "radar_alert",
  "title": "नई चेतावनी: SG-IN",
  "body": "पिछले 7 दिनों में 3 कामगारों ने एक ऑपरेटर की छिपी फीस की रिपोर्ट की।",
  "language": "hi",
  "deep_link": "/radar",
  "source": { "kind": "radar_alert", "path": "radar_alerts/SG-IN/current/a_01" },
  "read": false,
  "created_at": "2026-09-27T06:00:04Z",
  "schema_version": 1
}
```

**Access:** owner reads; owner may update only `read` and `read_at`; only the backend creates or deletes.

**Index:** `read` asc + `created_at` desc (unread feed). See the index table in `firestore-schema.md`.

**Tasks that use it:** NF-P1-022 (create the profile), NF-P1-023 (edit it, delete the account), NF-P3-004 (create notifications), NF-P3-009 (feed and read state).
