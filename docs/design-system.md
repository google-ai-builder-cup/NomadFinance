# NomadFinance design system

"Trusted fintech, quietly futuristic": calm light surfaces, one teal brand colour, a sparing gold accent, one risk scale used everywhere, and one accent hue per pillar. Motion and 3D explain things (money moving, a document being scanned, a radar sweeping); they are never decoration.

Everything lives in code, not in this file:

| What | Where |
| --- | --- |
| Colour, gradient, shadow, motion tokens | `frontend/src/styles/tokens.css` |
| Tailwind names for those tokens, keyframes | `frontend/tailwind.config.ts` |
| Base styles, `card-surface`, `glass`, `ai-border`, reduced-motion rules | `frontend/src/styles/globals.css` |
| Pillar class sets | `frontend/src/utils/pillars.ts` |
| Illustrations, globe, backgrounds, gauges | `frontend/src/components/visual/` |

## Palette ("Mist")

Colour tokens are HSL triplets (`hsl(var(--x))`). The values below are the light theme; `.dark` has its own set.

| Role | Token | Value |
| --- | --- | --- |
| Page | `--background` | `#F4F9FA` |
| Card | `--card` | `#FFFFFF` |
| Band | `--alt` | `#E7F1F4` |
| Ink | `--foreground` | `#0E2A33` |
| Secondary ink | `--muted-foreground` | `#476470` |
| Line | `--border` | `#D6E5EA` |
| Brand (Nomad Teal) | `--primary` | `#0B5D71` |
| Gold accent | `--brand-gold` | `#F59E0B` |
| Midnight, Aqua | `--navy`, `--aqua` | `#071B2E`, `#5ED6E8` |

Gold is used for the main call to action, key numbers and the logo dot only.

## Risk scale

One scale for contract health, radar risk, alerts, badges and provider flags. Each state has a fill, a text ink, a tint and the ink that sits on the tint (`safe`, `caution`, `danger`, `info`). A state is never shown by colour alone: use `RiskBadge`, which always pairs an icon and a word.

## Pillar accents

Each pillar owns one hue, chosen away from the four risk hues so a pillar tint is never mistaken for a risk level. It colours the icon tile, the page header band, the illustration and the active nav item.

| Pillar | Key | Hue |
| --- | --- | --- |
| Remittance X-Ray | `remit` | Lagoon `#0EA5C0` |
| Contract Shield | `contract` | Indigo `#6A5FE0` |
| Exploitation Radar | `radar` | Orchid `#C9409A` |
| Financial Identity | `identity` | Citrus `#8FB51A` |

Use `PILLAR_STYLES[key]` (never build a class name from the key: Tailwind cannot see it).

## Surfaces and shape

- Body cards are solid (`card-surface`), with an optional 1px gradient edge (`card-edge`). Glass (`glass`) is for overlays only: the header, floating cards, sheets and the radar side panel.
- Radius scale: 12 / 16 / 24 px (`rounded-lg`, `rounded-xl`, `rounded-2xl`).
- Elevation: `shadow-sm`, `shadow-md`, `shadow-lg`, `shadow-glow`.
- Type: Plus Jakarta Sans, with Noto Sans Devanagari and Noto Sans Bengali in the same stack (loaded from `index.html`, `font-display: swap`). Money and figures use tabular numerals (set on `body`).

## Motion rules

- Durations 150 / 280 / 600 ms (`duration-fast|base|slow`), one easing (`ease-out-soft`). Ambient motion (drifting backgrounds, floating cards) is slow, transform-only and never flashes.
- Everything has a static fallback: `globals.css` stops every animation and transition under `prefers-reduced-motion`; `useReveal` and `useCountUp` show the final state at once.
- The animated globe only runs on a capable device (motion allowed, no data saver, at least 4 GB memory and 4 cores) and pauses when off-screen or in a background tab. Everywhere else the identical static SVG poster is shown. Its code is a separate chunk.
- Tilt on hover applies to a mouse only, never to touch.

## Components

| Component | Use |
| --- | --- |
| `PageHeader` | Top band of every pillar page: pillar tile, title, one line, illustration, actions |
| `PillarIllustration` | Isometric scene per pillar, theme-aware |
| `StatusIllustration` | Not found, error and coming-soon screens |
| `StatCard` | A KPI tile with loading, error, empty and ready states |
| `RiskBadge`, `Badge` | Status pills |
| `RiskGauge`, `ScoreRing` | Contract health gauge, progress ring |
| `CountUp`, `Reveal`, `TiltCard` | Count-up numbers, fade-up on scroll, hover tilt |
| `AnimatedBackground` | `mesh`, `dotted-map`, `grid` ambient backgrounds |
| `CorridorGlobe` | Hero globe with the six corridors |
| `CountryPair` | Host to home country-code discs (no flags or brand logos) |

## Landing page figures

Every number on the landing page comes from `frontend/src/utils/landingMetrics.ts`. An industry figure carries its source; a figure that has not been measured yet is `null` and the page shows a "pending" card. Do not put a number in JSX.

## Checklist

- Reduced motion: all animation stops; content never stays hidden. Done.
- WebGL / heavy visual fallback: static SVG poster of the same scene; canvas globe is lazy and gated. Done.
- Contrast: text and surface pairs in `tokens.css` were checked against WCAG 2.2 AA (4.5:1) in the light theme; the dark values were chosen to match.
- Fonts: Devanagari and Bengali render through the font stack.
- No raw hex in components (illustration skin tones, the printed-letter paper and the SDG colours are tokens).
- Presentation only: services, hooks, API calls, types, routing, auth and Firestore rules are untouched.
