# NF-F0-013 — i18n namespaces for the Coach and Scam modules

## Summary

The app had one i18n namespace (`translation`, `src/i18n/<lang>.json`). The two Future Scope modules now each have their own, loaded only when the module is opened, in all six languages (`en`, `hi`, `tl`, `id`, `ne`, `bn`). A script fails CI when any language lacks a key that English has.

| Namespace | Files | Loaded |
|---|---|---|
| `translation` (shared: nav, auth, errors ...) | `src/i18n/<lang>.json` | English in the first download; each other language when first chosen (unchanged from NF-P1-011) |
| `coach` | `src/i18n/coach/<lang>.json` | With the `/coach` page, once the `coach` flag is on for the user |
| `scam` | `src/i18n/scam/<lang>.json` | With the `/scam-check` page, once the `scam` flag is on |

English is the source of truth. A module's namespace holds only that module's strings; anything shared stays in `translation`, and a module's `t()` still finds it (`fallbackNS`), so `t("common.retry")` works inside the coach.

## How loading works

`src/lib/i18n.ts`:

- `loadNamespace("coach")` fetches the module's English file (the fallback) and its file in the current language, once each, and records the namespace as **in use**. The lazy route calls it next to the page import, so the strings arrive with the page and the existing module skeleton shows until both are there:

  ```ts
  const CoachHome = lazy(async () => {
    const [page] = await Promise.all([import("@/pages/coach/CoachHome"), loadNamespace("coach")]);
    return page;
  });
  ```

- `setLanguage(code)` fetches the shared file for `code` and the file of **each namespace in use**, nothing else, then switches. A worker who never opened the coach never downloads its strings in any language.
- Failure handling: the shared file failing keeps the UI in its current language (as before). A module file failing (no signal, never cached) leaves only that module in English, not showing keys; the next switch tries again. Only the module's English file failing rejects `loadNamespace`.
- `useI18n("coach")` returns `t` for that namespace; `useI18n()` is unchanged.
- The namespace is registered before its fetch starts, so a language switch that begins while the page is loading still fetches it.
- Every file is its own tiny chunk (0.2 to 0.4 kB for the seed), precached by the service worker like the language files, so the modules work offline once visited.

## The check

`frontend/scripts/check-i18n.mjs`, no dependencies, run with `node scripts/check-i18n.mjs` (from `frontend/`):

- Finds the namespaces by folder (`src/i18n/*/` plus the shared files) and the languages from `SUPPORTED_LANGUAGES` in `src/lib/languages.ts`, so there is one list.
- Compares every namespace with its English file. Fails on: a missing file, invalid JSON, a missing key, a key English does not have, empty or non-string text, and `{{placeholders}}` that differ from English.
- Plural keys (`_one`, `_other` ...) are compared by base name, because languages differ in how many forms they have (Indonesian has only `_other`).
- Output names the namespace, language and key; exit code 1 on any problem.

```text
i18n check failed: 2 problem(s). English is the source of truth.

  coach / ne: key home.extra is not in English (the source of truth)
  scam / hi: not valid JSON (...)
```

It is also a vitest test (`tests/unit/checkI18n.test.ts`), so `vitest run` catches it. The older `src/lib/i18nKeys.test.ts` still guards the shared file.

## Adding strings to a module

1. Add the key to `src/i18n/<namespace>/en.json`.
2. Add the same key, translated, to the other five files. Keep every `{{placeholder}}`.
3. `node scripts/check-i18n.mjs`.
4. Use it with `const { t } = useI18n("coach")`.

A component under the module's page uses the same hook; the namespace is already loaded by the route. A component used outside the module's route must call `loadNamespace` itself.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Folder per namespace (`src/i18n/coach/`), not `coach.hi.json` files beside the shared ones. | The shared files keep their names, so nothing existing moves; the check finds namespaces by folder. |
| 2 | Hand-written loaders, not an i18next backend plugin. | The existing `setLanguage` and its tests (stay in the current language on a failed fetch) keep working unchanged; a backend would also load every namespace on a switch unless configured against it. |
| 3 | Load in the lazy route, not in a hook. | The route already shows the module skeleton while its code loads, so no new loading state, and a user the flag is off for fetches nothing. |
| 4 | The seed is the stub pages' own strings: `home.title`, `home.comingSoonTitle`, `home.comingSoonDescription`, `home.backToDashboard`. | Gives each namespace a real consumer to test against. NF-FC-017 to NF-FC-023 and NF-SA-015 to NF-SA-019 add the real keys, and the check forces all six languages. |
| 5 | `fallbackNS: "translation"`. | A module should not repeat `common.*` and `errors.*`. |
| 6 | The check script reads the language list from `languages.ts` by pattern. | One list; it fails loudly if the list cannot be read. |

## Files

| File | Change |
|---|---|
| `frontend/src/lib/i18n.ts` | Namespaces, `loadNamespace`, `setLanguage` loads the namespaces in use, `fallbackNS` |
| `frontend/src/hooks/useI18n.ts` | Optional namespace argument |
| `frontend/src/pages/coach/CoachRoute.tsx`, `pages/scam/ScamCheckRoute.tsx` | Load the namespace with the page |
| `frontend/src/pages/coach/CoachHome.tsx`, `pages/scam/ScamCheckHome.tsx` | Use their own namespace |
| `frontend/src/i18n/coach/*.json`, `frontend/src/i18n/scam/*.json` (new, 12 files) | Seed strings in six languages |
| `frontend/scripts/check-i18n.mjs` (new) | The check |
| `frontend/src/lib/i18nNamespaces.test.ts`, `frontend/tests/unit/checkI18n.test.ts` (new) | 17 tests |

**Shared files for the CI step** (need the team's OK, not yet edited): `frontend/package.json` (one script) and `.github/workflows/frontend-ci.yml` (one step). Diffs below.

```diff
--- a/frontend/package.json
+++ b/frontend/package.json
@@ "format:check": "prettier --check .",
+    "i18n:check": "node scripts/check-i18n.mjs",
     "test:rules": ...
```

```diff
--- a/.github/workflows/frontend-ci.yml
+++ b/.github/workflows/frontend-ci.yml
@@ jobs.checks.steps
       - run: pnpm lint
       - run: pnpm format:check
+
+      # English is the source of truth: fails when a language lacks a key (NF-F0-013).
+      - run: pnpm i18n:check
```

## Checks run (2026-10-06)

| Check | Result |
|---|---|
| `tsc -b`, `pnpm lint` | clean |
| `vitest run src tests/unit` | 37 files, **312 passed** (17 new) |
| `prettier --check` on the files touched | clean (with `--end-of-line auto`; see Open points) |
| `node scripts/check-i18n.mjs` | OK: 3 namespaces x 6 languages, 813 English keys |
| The check against planted faults | A key English lacks and invalid JSON are both reported by name, exit 1; the files were restored afterwards |
| Mutations | Making a language switch load every namespace, and not registering a namespace, each fail 2 to 3 of the new tests; both reverted |
| `pnpm build` | Builds; each namespace file is its own chunk (12 new, 0.2 to 0.4 kB), and neither module's strings are in the main bundle |
| Real browser (dev server) | `setLanguage("hi")` requested `hi.json` only; `loadNamespace("coach")` added `coach/en.json` and `coach/hi.json`; `setLanguage("bn")` added `bn.json` and `coach/bn.json`. **No `scam/*` file was requested at any point.** The coach title came back in Bengali and a shared string resolved from the coach's `t()`. |

Not tested: the two pages end to end behind a real sign-in (the browser pane cannot sign in); the seed translations by a native speaker.

## Open points

- **Seed translations are machine quality**, as the other languages are (NF-P1-011 note). The new ones are only `home.title`: "Financial Coach" in Hindi, Indonesian, Nepali and Bengali (Tagalog keeps the English term). The rest copy the existing `comingSoon.*` and `nav.scamCheck` text.
- **Prettier on a CRLF checkout**: `pnpm format:check` flags CRLF files on Windows (pre-existing, NF-P1-011). New files were checked with `--end-of-line auto`.
- **Plural keys are not used yet.** The check is ready for them; i18next must also be given the count.

## Definition of Done (Frontend Feature)

- [x] i18n keys added for all user-facing strings, all 6 languages (and a check that keeps it so)
- [x] Loading state: the existing module skeleton covers the strings fetch
- [x] Error state: a failed non-English fetch falls back to English
- [ ] Missing-key check runs in CI: script written; the CI step waits for the OK on two shared files
- [ ] Component / mobile / accessibility / screenshots: not applicable, no new UI
- [ ] Reviewed by Pranjal
