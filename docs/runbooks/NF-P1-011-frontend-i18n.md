# NF-P1-011 — i18n Setup (6 languages)

## Summary

The app now runs on real `react-i18next` instead of the temporary `translate()` stand-in NF-P1-010 left in place. All 6 language JSON files (`en`, `hi`, `tl`, `id`, `ne`, `bn`) carry the same keys, and a language selector in the header switches the whole UI instantly, persisting the choice in `localStorage`.

`useI18n()` was deliberately shaped like `useTranslation()` back in NF-P1-010, so every existing `t("some.key")` call site (10 files) needed zero changes — only the hook's internals changed.

## Files

| File                                                                    | Purpose                                                                                                                                                                         |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `frontend/src/lib/i18n.ts`                                              | Real `i18next` init: `use(LanguageDetector).use(initReactI18next)`, 6 language resources, `fallbackLng: "en"`, detector reads/writes `localStorage` key `nomadfinance.language` |
| `frontend/src/lib/languages.ts`                                         | `SUPPORTED_LANGUAGES` list (code + native-script name) driving the selector's options                                                                                           |
| `frontend/src/hooks/useI18n.ts`                                         | Now a thin wrapper over real `useTranslation()`                                                                                                                                 |
| `frontend/src/i18n/hi.json`, `tl.json`, `id.json`, `ne.json`, `bn.json` | Translated to match every key already in `en.json` (best-effort machine-quality — flagged for a native-speaker pass before the demo)                                            |
| `frontend/src/components/layout/LanguageSelector.tsx`                   | Native `<select>` styled to match the existing `Button`, no new UI dependency. Icon from `lucide-react`.                                                                        |
| `frontend/src/components/layout/Header.tsx`                             | Mounts `<LanguageSelector />` next to the sign-out button                                                                                                                       |
| `frontend/src/main.tsx`                                                 | Imports `@/lib/i18n` once at the entry point                                                                                                                                    |
| `frontend/package.json`, `pnpm-lock.yaml`                               | Added `react-i18next@17.0.15`, `i18next@26.4.2`, `i18next-browser-languagedetector@8.2.1`                                                                                       |

Not touched: `frontend/README.md` has no "i18n" section — noticed as a gap while writing this runbook, left for whoever picks it up next since it's outside this task's original scope.

## Flow

```
main.tsx
  └─ import "@/lib/i18n"   (side-effect: i18next.init() runs once)

useI18n() (10 call sites: Header, Sidebar, Footer, BottomNav, AppShell,
           SignIn, Dashboard, ComingSoon, NotFound, ProtectedRoute)
  └─ useTranslation() → { t }   (re-renders automatically on language change)

Header
  └─ <LanguageSelector />
       ├─ reads i18n.resolvedLanguage for the current <select> value
       └─ onChange → i18n.changeLanguage(code) → LanguageDetector caches it to
          localStorage["nomadfinance.language"] → every t() call re-renders
```

## Design choices worth knowing

- **Native `<select>`, not a shadcn/Radix dropdown.** No dropdown/select primitive existed in `components/ui/` yet, and adding `@radix-ui/react-select` would have been an extra shared-file dependency for a control this simple. A native select is fully keyboard-accessible for free.
- **`useI18n()` kept its exact shape.** NF-P1-010 wrote it as `{ t }` on purpose so this task could swap the implementation without touching any consumer — confirmed by grepping all 10 call sites before and after; none changed.
- **Language choice persists via the detector's own `localStorage` cache**, not a new Zustand store — `i18next-browser-languagedetector` already does this, so no state-management addition was needed.
- **Translations are best-effort, not reviewed by a native speaker.** None of the team are native speakers of Hindi, Tagalog, Indonesian, Nepali or Bengali beyond a conversational level; worth a review pass before the demo.

## How later tasks plug in

| Task                     | What to do                                                                                                                                                                                                                                                         |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| NF-P1-021 (landing page) | Reuse `<LanguageSelector />` on the public landing page, or read `i18n.language` directly if the landing page renders outside any layout that already has it.                                                                                                      |
| NF-P1-022 (onboarding)   | When capturing `preferred_language`, seed it from `i18n.language` as the default so the form doesn't ask something the user already answered by picking a language.                                                                                                |
| Any new UI string        | Add the key to `en.json` first, then the same key to all 5 other files. `t()` silently falls back to the raw key string if a translation is missing in a non-English language (via `fallbackLng: "en"`), so a missed key degrades to English rather than breaking. |

## All commands, in order

Run from `frontend/`.

### 1. Install

```bash
pnpm install
```

Adds `react-i18next`, `i18next`, `i18next-browser-languagedetector`.

### 2. Checks

```bash
pnpm lint
pnpm build
```

Expected: both clean.

### 3. Manual test

```bash
pnpm dev
```

Open `http://localhost:5173`, sign in, land on `/dashboard`. Use the language dropdown in the header (next to sign-out):

1. Switch through all 6 languages — dashboard, sidebar/bottom-nav labels, and footer text should update instantly, no reload.
2. Reload the page — the language you left it on should still be selected (stored in `localStorage["nomadfinance.language"]`).
3. Without signing in, you can still check a translation directly from `/sign-in` via the DevTools console: `localStorage.setItem('nomadfinance.language', 'bn'); location.reload();`

## Verified results (2026-09-25, browser pane)

| Check                                                                | Result                                                                                                                                |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm lint` / `pnpm build`                                           | Clean / clean                                                                                                                         |
| `/sign-in` in English (default)                                      | Renders correctly                                                                                                                     |
| `localStorage` set to `hi`, reload                                   | Full sign-in page in Hindi                                                                                                            |
| `localStorage` set to `bn`, reload                                   | Full sign-in page in Bengali                                                                                                          |
| Signed-in dashboard, language selector switched live (en → ne → id)  | Header, sidebar/bottom-nav, dashboard cards, footer all update instantly, no reload                                                   |
| Selector at 375px width, longest label ("Bahasa Indonesia") selected | No overflow or wrap, sign-out icon stays clear                                                                                        |
| `pnpm format:check`                                                  | Fails on 36 files repo-wide (pre-existing CRLF/line-ending issue) — confirmed none of the files touched by this task are in that list |

Not tested: a native-speaker accuracy review of the 5 non-English translations.

## Definition of Done (Frontend Feature)

- [x] Component built with Tailwind (no new UI library needed for the selector)
- [x] Fully mobile responsive (checked at 375px)
- [ ] Works on slow network (throttled 3G): not tested — nothing here is network-dependent, translations are bundled client-side
- [x] Loading states: n/a, i18next init is synchronous with bundled resources
- [x] Error states: n/a, no async/network path
- [x] i18n keys added for all user-facing strings, all 6 languages
- [ ] Screenshots added to the PR
- [x] Accessibility: `<select>` has a visible focus ring, `aria-label`/`sr-only` label, keyboard-operable natively

## Commit

Branch: `feature/frontend-i18n` (already merged to `main` via PR #17).

```bash
git add frontend/package.json frontend/pnpm-lock.yaml frontend/src/lib/i18n.ts \
  frontend/src/lib/languages.ts frontend/src/hooks/useI18n.ts frontend/src/i18n/*.json \
  frontend/src/components/layout/Header.tsx frontend/src/components/layout/LanguageSelector.tsx \
  frontend/src/main.tsx docs/runbooks/NF-P1-011-frontend-i18n.md
git commit -m "docs(frontend): add i18n setup runbook" -m "Refs: NF-P1-011"
```

This runbook was written after the fact, directly against `main` — the code itself already shipped in commit `4a7f8ee` / PR #17.

## Troubleshooting

| Symptom                                                        | Fix                                                                                                                                                                                           |
| -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A string shows as its raw key (e.g. `pillars.remittance.name`) | The key is missing from that language's JSON file. Add it there — `fallbackLng: "en"` only saves you if it's missing from `en.json` too, otherwise you get the raw key.                       |
| Language selector shows the wrong current value                | `i18n.resolvedLanguage` reflects the actual applied language, not necessarily `i18n.language` (which can be a region variant like `en-US`); the selector reads `resolvedLanguage` on purpose. |
| Chosen language doesn't persist across reload                  | Check `localStorage["nomadfinance.language"]` isn't being cleared by browser privacy settings or a private window.                                                                            |
| New language file doesn't load                                 | Confirm it's imported and added to the `resources` object in `lib/i18n.ts` — dropping a new JSON file into `src/i18n/` alone isn't enough.                                                    |

## Not covered here

- Native-speaker accuracy review of hi/tl/id/ne/bn translations
- Landing page language selector: NF-P1-021
- `preferred_language` persisted to the Firestore user profile: NF-P1-022
- A `frontend/README.md` "i18n" section: not written by this task, noticed as a gap above
