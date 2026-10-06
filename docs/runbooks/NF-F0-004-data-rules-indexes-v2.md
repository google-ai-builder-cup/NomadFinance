# NF-F0-004 — Security rules and indexes for the Future Scope collections

## Summary

The nine new Future Scope paths of NF-F0-003 now have Firestore rules, the two indexes they need are in `frontend/firestore.indexes.json`, and every rule has an allow and a deny test on the emulator. Nothing was deployed: there is no staging project yet (NF-F0-011), and no workflow deploys indexes (D-68).

The model is the one NF-F0-003 fixed: a worker **reads** their own Coach and scam data, and **every write goes through the API**. Reference data (taxonomy, cost baselines) is readable by any signed-in user. The scam templates, the indicator counts and the feature flags are not reachable from a browser at all.

## Who can do what

| Path | Owner (signed in, uid matches) | Other signed-in user | Signed out |
|---|---|---|---|
| `users/{uid}/coach_sessions/{id}` | read | — | — |
| `users/{uid}/coach_plans/{id}` | read | — | — |
| `users/{uid}/coach_plans/{id}/translations/{lang}` | read | — | — |
| `users/{uid}/scam_checks/{id}` | read | — | — |
| `scam_taxonomy/{id}`, `scam_taxonomy/_meta` | read | read | — |
| `cost_baselines/{host}` | read | read | — |
| `scam_patterns/{id}` | — | — | — |
| `scam_indicators/{id}` | — | — | — |
| `config/feature_flags` | — | — | — |
| `users/{uid}`, field `signal_sharing` | write (see below) | — | — |

`—` = denied. No browser create, update or delete on any row above (the one exception is `signal_sharing`). The backend (Admin SDK) skips the rules and is unaffected.

**`signal_sharing`** is the only new client-writable thing. It joins the profile fields: a map holding only the keys `coach` and `scam`, each a boolean. A missing key means off. It follows the same rules as the other profile fields (a server `updated_at` on every write; no other field may change in the same update).

## Files

| File | Change |
|---|---|
| `frontend/firestore.rules` | Three owner-read collections added to the backend-written list; one `translations/{language}` match; `scam_taxonomy` and `cost_baselines` added to the shared-read list; `signal_sharing` in `profileFields()` and `validProfile`; the comment on denied collections now names the three new ones |
| `frontend/firestore.indexes.json` | Vector index on `scam_patterns.embedding` (768, flat); `fieldOverrides` entry for `coach_plans.departure_date` with collection and collection-group scope |
| `frontend/firebase.json` | **Shared file, approved 2026-10-06.** `"indexes": "firestore.indexes.json"` added under `firestore`, so the CLI can deploy the index file (it did not reference it before, D-68) |
| `frontend/tests/rules/firestore.rules.test.ts` | New paths in the existing lists; `signal_sharing` block; a block for browser writes, deletes and lists on the new collections |
| `frontend/tests/rules/audit.rules.test.ts` | Collection-group queries on the new groups, signed in or not |
| `docs/data-model/firestore-schema.md`, `docs/deferred-items.md` | Status of rules and indexes; D-109 and D-68 updated |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **No browser delete** of a scam check or a Coach session (D-109). | NF-F0-003 decision 8: every change goes through the API, so the state machine and the guardrails cannot be skipped. If NF-SA-012 wants a "delete my check" button it is an API route, and no rule needs to change. D-109 stays open for that choice. |
| 2 | `signal_sharing` is in this task, not NF-HR-001. | NF-F0-003 listed it under what this task builds, and a profile save from the browser fails without it. |
| 3 | Rules for `translations` are a separate match. | The generic `users/{uid}/{collection}/{docId}` rule matches one level only; the translation is two levels below `coach_plans`. |
| 4 | The check-in index keeps the collection-scope entry next to the new group-scope one. | A field override replaces Firestore's automatic indexes for that field, so leaving the first out would break a per-user `departure_date` query. |
| 5 | TTL is **not** in the index file. | A TTL policy is a setting on the field. The three `gcloud` commands from NF-F0-003 stay the way to set it (below); I could not check the JSON form without a real deploy. |

## Indexes: what a later task can rely on

Every query in the NF-F0-003 field tables is served by an automatic index, or by one of these two:

| Query | Served by |
|---|---|
| Nearest 3 scam templates (NF-SA-010) | the vector index on `scam_patterns.embedding` |
| Plans reaching day 30, 60 or 90, across all users (NF-FC-016) | `coach_plans.departure_date`, collection-group scope |
| Active session; newest plans; newest checks; a cached verdict; the taxonomy by `kind`; the most reported indicators | automatic single-field indexes |

If a later task adds a query that needs a composite index, it adds it to the same file and to `firestore-schema.md`.

## Commands

All from `frontend/` (pnpm 10; Java 11+ and the Firebase CLI installed). The same on bash and PowerShell.

### 1. Run the rule tests on the emulators

```bash
pnpm test:rules
```

Expected: 3 files, 186 tests, all passed (the count before this task was 134).

### 2. Check the files parse

```bash
python3 -c "import json; json.load(open('firestore.indexes.json')); print('ok')"
pnpm exec prettier --check tests/rules firestore.indexes.json firebase.json
```

PowerShell: use `python` for `python3`.

### 3. Deploy (someone with project access, not done in this task)

Staging does not exist yet. For a project that does (replace the project id):

```bash
pnpm dlx firebase-tools@15.31.0 deploy --only firestore:rules,firestore:indexes --project <project-id>
```

The vector index takes several minutes to build; `gcloud firestore indexes composite list --project <project-id>` shows it as `READY` when done. **Merging this to `main` deploys the rules to production on its own** (the rules workflow watches `frontend/firestore.rules`); it does not deploy the indexes.

### 4. TTL policies (once per project)

These are in NF-F0-003 and D-103, repeated here so the set is complete. Not run.

```bash
gcloud firestore fields ttls update expires_at --project <project-id> \
  --collection-group=coach_sessions --enable-ttl --async
gcloud firestore fields ttls update expires_at --project <project-id> \
  --collection-group=scam_checks --enable-ttl --async
gcloud firestore fields ttls update expires_at --project <project-id> \
  --collection-group=scam_indicators --enable-ttl --async
```

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `pnpm test:rules` | 186 passed (52 new), run three times in a row after the last change |
| Rules broken on purpose: `scam_patterns` and `config` made readable; `translations` made writable; `signal_sharing` validation removed | Caught by 4, 2 and 4 tests; rules restored and compared byte for byte |
| `tsc -b`, `eslint --max-warnings 0 tests/rules`, `prettier --check` | clean |
| `firestore.indexes.json` | parses; 3 composite indexes, 1 field override |

Not verified: the index file against a real deploy (the emulator ignores indexes), and the three TTL commands. Both need a project.

## Not done, and why

- **Deploy to staging:** no staging project (NF-F0-011), and no credentials here.
- **Index deploy in the workflow** and the `roles/datastore.indexAdmin` grant (D-33, D-68): the workflow is a shared file. `firebase.json` is now ready for it.
- **TTL policies:** project settings, see step 4 (D-103).
- **A delete route for a worker's own history:** NF-SA-012 decides (D-109).

## Commit

```bash
git commit -m "feat(data): add security rules and indexes for coach and scam collections" -m "Refs: NF-F0-004"
```

PR title: `feat(data): security rules and indexes for coach and scam collections (NF-F0-004)`
