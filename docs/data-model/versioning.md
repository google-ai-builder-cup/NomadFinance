# Versioning

Status: NF-P1-013 **[P]**, built on the DoD line "Version metadata bumped if cached data depends on this" and on NF-P2-007 ("cache by contract-hash + language + law-version"). There are four kinds of version, each answering a different question.

| Kind | Question it answers | Where it lives |
|---|---|---|
| Data version | "Has the reference data changed since I made this result?" | `labor_laws/{country}/_meta/current.version` |
| Prompt version | "Was this AI result made with the prompt the code uses now?" | `prompt_versions` on contract reports and the financial profile |
| Schema version | "Which shape is this document in?" | `schema_version` on user-owned and AI-written documents |
| Survey period | "Which quarter is this price data from?" | `period` on `corridors/{id}` |

## Data version

Only `labor_laws` has one, because it is the only reference data that stored results depend on.

- `labor_laws/{country}/_meta/current.version` is a whole number that starts at 1.
- The loader (NF-P1-018) hashes the country's validated `rules` in canonical form (not the file bytes, so formatting and reviewer names do not count). If the hash differs from `_meta/current.content_hash`, it writes the rules and sets `version` to the old value plus 1. If the hash is the same, the version and `_meta` are left alone, so re-running the loader is safe.
- A contract report records the `law_version` it was made with. When the current version is higher, the stored report is out of date and is remade on the next request (see the cache rule in [contracts](collections/contracts.md)).
- The version is per country. Changing the Singapore rules does not invalidate Japanese reports.

Corridor prices and FX rates do not need a data version: they are read live, never copied into stored results, and `period` and `fetched_at` already say how old they are.

## Prompt version

Prompts live in `backend/app/prompts/<pillar>/<step>.v<N>.yaml`. The step's name and `N` are recorded as `{ "contract.compare": 1 }`.

- Saving the map on every report and profile lets the cache tell that a prompt changed.
- Changing a prompt's wording in a way that changes results means a **new file** (`.v2.yaml`) and a code change to load it. Editing `.v1.yaml` in place would leave old results looking current.
- Also store the `models` (or `model`) used per result. ADR-002 lets the team switch the model with an environment variable, and the record shows which model made a result.

## Schema version

Every user-owned document and every AI-written document has `schema_version`, a whole number starting at 1. Reference data loaded from files (corridors, labor laws) is replaced wholesale on each load, so the `schema_version` on those documents matters less; they carry it anyway so every document can be recognised.

### Rules for changing a schema

1. **Adding an optional field needs no version bump.** Readers must treat an absent field as unknown. This is the normal, safe change.
2. **Never rename or remove a field in place.** Add the new field, write both for a release, move the readers, then stop writing the old one. Old documents keep the old field until migrated.
3. **A change that would break a reader** (type change, meaning change, a field becoming required) needs a bump: write `schema_version: 2` on new documents, and make readers accept versions 1 and 2 until the migration has run.
4. **Migrations are idempotent scripts** in `data-scripts/`, safe to run twice: they skip documents already at the new version, validate before writing, and log how many they changed and skipped. Run them on the emulator first.
5. **Update the docs and the security rules** in the same change: the field tables in `docs/data-model/`, the rules in `firestore.rules`, and the index list if a query changed. This is the "Firestore Schema Change" checklist at the bottom of the tracker's Definition of Done.
6. **Say so in the pull request.** Devam, Aditya and Pranjal share these documents; a silent field change breaks someone else's task.

### What each pillar's reader must tolerate

| Reader | Must handle |
|---|---|
| Comparison engine | `payout_currency` other than the destination currency; `total_cost_pct` below zero |
| Contract report UI | `complaint: null`; `law_reference: null`; a rule with no variant for the worker's job type (use the `all` variant); `coverage` of `not_regulated` or `unclear` (show "no rule found", not "safe") |
| Radar UI | `community_rating: null` |
| Financial Identity | Entries without `category`; a profile that does not exist yet |

## Survey period (corridors)

`corridors/{id}.period` (for example `2025_1Q`) is the quarter of the World Bank survey. Loading a newer quarter replaces the documents. The UI should show `surveyed_on` so users can see how old a price is; the data was already 18 months old when this task was written, because RPW had published nothing newer.

## Checklist for a schema change

- [ ] Field tables in the matching `collections/*.md` updated, with an example
- [ ] `schema_version` bumped if a reader would break, and readers accept both versions
- [ ] Migration script written, idempotent, run on the emulator (or "not needed" stated in the pull request)
- [ ] Security rules updated for the new fields or collections
- [ ] New queries have their index in `firestore.indexes.json`
- [ ] `_meta.version` bumped by the loader if cached results depend on this data
- [ ] Prompt file version bumped if the prompt changed
