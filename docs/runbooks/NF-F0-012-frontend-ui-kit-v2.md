# NF-F0-012 — Shared UI kit additions

## Summary

Seven reusable components now exist for the Coach and Scam Analyzer screens, each with tests and a usage example in [`docs/ui-kit.md`](../ui-kit.md). They live in `frontend/src/components/common/`, take all their text as props (no language files touched), use only colour tokens, and mirror correctly in right-to-left.

| Component | State | What it is |
|---|---|---|
| `ChatBubble` | **new** | One chat message: assistant or user, streaming caret or typing dots, failed state with retry |
| `QuickReplyChips` | **new** | Suggested answers as a named group of 44 px buttons |
| `RiskMeter` | **new** | Three-segment low / medium / high meter with an icon and words beside it |
| `StepProgress` | **new** | Numbered steps for a multi-step flow, with spoken status |
| `TimelineItem` | **new** | One entry of a vertical timeline (`li`), with a connecting line |
| `RiskBadge` | existing, unchanged | Tests added; `utils/risk.ts` maps a severity to its level |
| `EmptyState` | existing, one prop added | `headingLevel` (2, 3 or 4) so a screen keeps its heading order |

No screen uses the new components yet. Merging this changes nothing a user sees.

## Files

| File | Change |
|---|---|
| `frontend/src/components/common/{ChatBubble,QuickReplyChips,RiskMeter,StepProgress,TimelineItem}.tsx` | New components |
| `frontend/src/components/common/EmptyState.tsx` | `headingLevel` prop (default 2, so nothing changes for current callers) |
| `frontend/src/components/common/*.test.tsx` (7 files) | 51 tests with `utils/risk.test.ts` |
| `frontend/src/utils/risk.ts`, `risk.test.ts` | `riskLevelForSeverity`: low, medium, high to safe, caution, danger |
| `docs/ui-kit.md` (new) | Props, rules and a usage example per component |
| `docs/design-system.md` | One row in the Components table pointing at `ui-kit.md` |
| `frontend/package.json`, `frontend/pnpm-lock.yaml` | **Shared files, diff approved 2026-10-06.** Four dev dependencies, see below |

## Test tooling added

The tracker asks for "vitest + RTL" tests, and the repo had neither React Testing Library nor a DOM. The four existing component tests use `renderToStaticMarkup`, which cannot test a click or a keypress.

| Package | Version | Why |
|---|---|---|
| `@testing-library/react` | 16.3.3 | Renders a component and finds it by role and accessible name, as a screen reader does |
| `@testing-library/dom` | 10.4.2 | A peer of the one above (`pnpm` is strict about peers) |
| `@testing-library/user-event` | 14.6.7 | Real click, Tab, Enter and Space |
| `jsdom` | 29.1.1 | The DOM for those tests |

**`jsdom` is 29.1.1, not the newest.** The latest (30.x) needs Node 22 or newer, but CI and `engines` use Node 20; 29.1.1 supports Node 20.19 and later. Do not bump it past 29 without moving CI to Node 22.

A test file opts in to the DOM with `// @vitest-environment jsdom` as its first line, and calls `afterEach(cleanup)`. Existing tests and `vite.config.ts` are unchanged. NF-F0-014 (the test harness) needs the same packages and can reuse them.

The lockfile change is the four packages and their dependencies (about 420 lines, nearly all `jsdom`'s), plus vitest's resolved key gaining `jsdom` as a peer.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | All new components go in `components/common/`, next to `EmptyState` and `RiskBadge`. | `components/ui/` holds the shadcn primitives (`button`, `badge`, `card`). These are composites. |
| 2 | Components have no `t()` call; every word and every accessible name is a prop. | The screens own the `coach.*` and `scam.*` keys (NF-F0-013), so this task needed no language file change. `RiskGauge` already works this way. |
| 3 | `RiskMeter` is new and does not replace `RiskGauge`. | `RiskGauge` is the 0 to 100 contract-health semicircle. `RiskMeter` is the three-level scam verdict. |
| 4 | `RiskBadge` is unchanged; the severity mapping is a small function in `utils/risk.ts`. | A badge and a meter for the same verdict can never disagree, and the badge's four levels stay as they are. |
| 5 | `ChatBubble` has no live-region role. | The list holding the bubbles is the `role="log"`. A role on each bubble would announce a streamed reply many times (NF-FC-023 asks for once). |
| 6 | Right-to-left safety uses logical classes (`ms-`, `ps-`, `start-`, `justify-start`, `rounded-es-`), checked by a test that fails on `ml-`, `mr-`, `pl-`, `pr-`, `text-left`, `text-right`. | None of the six app languages is right-to-left today, so this costs nothing and avoids a rewrite later. |

## What was verified

| Check | Result |
|---|---|
| New tests | 51 passed, in 8 files |
| Full frontend suite (`pnpm test`) | 354 passed |
| `tsc -b`, `pnpm lint` (zero warnings), `pnpm format:check`, `pnpm build` | clean |
| Coverage gates (`pnpm test:coverage`) | pass; lines 17.3% against a 15% floor |
| 360 px wide, light theme | No horizontal scroll; chips 44 px tall; every section reads correctly |
| Dark theme | Looked at every component; one contrast problem found and fixed (below) |
| Right-to-left (`dir="rtl"`) | Chat sides swap, chips and badges reverse, steps run right to left, timeline marker and line move to the start edge |
| Tablet width | `StepProgress` names appear under each marker, evenly spaced |
| Keyboard, in a real browser | Tab order was Try again, Singapore, Australia, South Korea, Japan, then the page's last button; focus ring a visible 2 px outline; Tab then Enter chose "South Korea" and `aria-pressed` followed |

The browser checks used a temporary page served by the Vite dev server. It rendered every component with switches for dark mode and `dir="rtl"`. **It was deleted afterwards** and is not in the change.

**Two defects found by that look, both fixed in this change** (the unit tests could not see either):

1. `StepProgress`: the current step's name made its column wider and squeezed the line after it, so the steps were unevenly spaced. The names also used `display: none` on a narrow screen, which removes them from a screen reader, leaving only "completed". Names are now drawn out of the flow and visually hidden (`sr-only`) on a narrow screen, so they are still read.
2. `ChatBubble`: the "not sent" text used the destructive fill colour, about 2.7:1 against the dark background. It now uses `text-danger-ink`, the design system's text colour for danger.

**Not verified:** a real screen reader (VoiceOver, TalkBack). The queries in the tests use roles and accessible names, which is how a screen reader finds them, but nobody listened. `axe` on finished screens belongs to NF-SA-019 and NF-FC-023.

## Manual test

From `frontend/`. The same on bash and PowerShell.

```bash
pnpm test
```

Expected: `Test Files 44 passed`, `Tests 354 passed`.

```bash
pnpm exec vitest run src/components/common src/utils/risk.test.ts
```

To look at the components, add a throwaway page (a root `.html` file and a `.tsx` that renders each component with some sample props), start `pnpm dev`, open it at 360 px wide, then add `?dark=1`-style switches for the dark class and `dir="rtl"` on `<html>`. Delete it again. The first usage examples to copy are in `docs/ui-kit.md`.

## Definition of Done (Frontend Feature)

- [x] Components built with Tailwind and the existing shadcn `Button` and `Badge`
- [x] Mobile responsive, checked at 360 px and at tablet width
- [x] Slow network, loading and error states: not applicable, these are presentational components with no requests
- [x] i18n keys for 6 languages: not applicable, the components have no text of their own (see decision 2); the screens add the keys
- [x] Accessibility: real buttons and list elements, roles and names tested, keyboard path tried in a browser; a screen reader was not run
- [x] Dark theme and right-to-left checked
- [ ] Screenshots added to the pull request: not done; the preview screenshots are not saved in the repository
- [ ] Reviewed by a teammate

## Commit

Branch: `feature/NF-F0-012-frontend-ui-kit-v2`.

```bash
git commit -m "feat(ui): add shared chat, risk, step and timeline components" -m "Refs: NF-F0-012"
```

PR title: `feat(ui): shared UI kit for the coach and scam screens (NF-F0-012)`

## Noticed, not fixed

- The retry icon in `ChatBubble` (a rotating arrow) is not mirrored in right-to-left. Whether a rotation arrow should flip is a judgement call; it looked fine in the preview.
- The `TimelineItem` title is an `h3`, which assumes an `h2` section heading above it. The screens that use it have to keep that order.
