# NF-P1-024 — Design Assets: Logo, Colors, Favicons

## Summary

Replaces every placeholder brand asset NF-P1-012 left behind (a plain "N" monogram on shadcn's
default slate theme, explicitly flagged with a `TODO(Aditya)` in `vite.config.ts`) with real
branding: a color palette, two logo variants, and the full favicon/PWA-icon/Apple-splash-screen
suite generated from them. Every existing component re-themes automatically — nothing in
`src/components/` or `src/pages/` changed, because they already style off the semantic
`bg-primary` / `text-muted-foreground` / etc. Tailwind classes wired to the CSS variables in
`tokens.css`.

## Palette (for the pitch deck)

**Nomad Teal** — primary brand color. Protection and trust; dark enough to read clearly outdoors
on a phone screen, which matters since many users are on the move for work.

| Token | Hex | HSL |
|---|---|---|
| Primary | `#0B5D71` | `hsl(192, 82%, 24%)` |
| Primary (dark mode) | `#29B6D8`-ish | `hsl(193, 70%, 55%)` |

**Nomad Gold** — sparing marketing accent (the dot in the logo mark). Not part of the
shadcn functional palette (`--primary`/`--secondary`/etc.) and not wired into any component by
this task; use it deliberately via the `gold` Tailwind color (`text-gold`, `bg-gold`, ...).

| Token | Hex | HSL |
|---|---|---|
| Gold accent | `#F59E0B` | `hsl(38, 92%, 50%)` |

Everything else (backgrounds, borders, muted text) is a low-saturation tint of the same teal
hue, not pure gray, so the whole UI reads as one family of colors. Full variable list:
`frontend/src/styles/tokens.css`.

## Logo

| File | Use |
|---|---|
| `frontend/public/brand/logo-full.svg` | Icon + "NomadFinance" wordmark, horizontal lockup, dark text on transparent background. For docs, the pitch deck, letterhead — anywhere shown on a light background. |
| `frontend/public/brand/logo-mark.svg` | Icon only, 64×64, teal rounded square with a white "N" and a gold accent dot. Source for every favicon and app icon below. |
| `frontend/public/brand/logo-mark-maskable.svg` | Same mark, glyph shrunk to ~78% and centered, full-bleed background (no rounded corners). Android crops maskable icons to a circle/squircle, so this is the only variant that survives that crop without clipping the glyph. Not a "brand variant" — a platform-required technical derivative of `logo-mark.svg`. |

The mark reads as an "N" but is drawn as three straight strokes (not a filled glyph or a font),
so it stays crisp and legible all the way down to a 16×16 browser tab favicon. The gold dot is
the one deliberate departure from a plain monogram — a small, memorable signature detail that
also nods at "a destination reached."

## Generated files

`frontend/scripts/generate-brand-assets.sh` rasterizes both SVG sources with `rsvg-convert` and
writes every one of these; **never hand-edit them, edit the SVGs and re-run the script**:

| File | Size | Purpose |
|---|---|---|
| `public/favicon.svg` | vector | Browser tab icon (modern browsers) — identical content to `logo-mark.svg` |
| `public/favicon.ico` | 16/32/48 px, one file | Legacy fallback favicon |
| `public/apple-touch-icon.png` | 180×180 | iOS home-screen icon |
| `public/icons/pwa-192x192.png`, `pwa-512x512.png` | 192, 512 | PWA manifest icons, `purpose: "any"` |
| `public/icons/maskable-512x512.png` | 512 | PWA manifest icon, `purpose: "maskable"`, from `logo-mark-maskable.svg` |
| `public/splash/apple-splash-*.png` | 11 sizes, 640×1136 to 2048×2732 | iOS launch splash screens, referenced from `index.html` by exact device media query |

`favicon.ico` is packed by `frontend/scripts/pack_ico.py`, a ~40-line pure-stdlib script (only
`struct`) rather than a Pillow/ImageMagick dependency — the Vista+ ICO format allows embedding a
plain PNG's bytes directly per entry, so no image library is needed at all, and there's nothing
here that can hit a native-DLL block like the one documented in NF-P1-016's runbook.

## Flow

```
public/brand/logo-mark.svg ────┬─→ favicon.svg (copy)
                                ├─→ pack_ico.py → favicon.ico (16/32/48)
                                ├─→ apple-touch-icon.png (180)
                                ├─→ icons/pwa-192x192.png, pwa-512x512.png
                                └─→ 11× splash/apple-splash-*.png (icon centered on white)
public/brand/logo-mark-maskable.svg ─→ icons/maskable-512x512.png
public/brand/logo-full.svg ─→ (not rasterized; used as-is in docs/deck)
```

## Files

| File | Purpose |
|---|---|
| `frontend/src/styles/tokens.css` | New palette (light + dark), replacing the shadcn slate default |
| `frontend/tailwind.config.ts` | Added `gold` color mapped to `--brand-gold` |
| `frontend/public/brand/*.svg` | The three logo/mark sources (new) |
| `frontend/scripts/generate-brand-assets.sh`, `pack_ico.py` | The generation pipeline (new) |
| `frontend/public/favicon.svg`, `favicon.ico`, `apple-touch-icon.png`, `icons/*.png` | Regenerated in place, same filenames NF-P1-012 used |
| `frontend/public/splash/*.png` | New — NF-P1-012 explicitly left these for this task |
| `frontend/index.html` | `theme-color` updated to the new primary; 11 `apple-touch-startup-image` links added |
| `frontend/vite.config.ts` | Manifest `theme_color` updated; `TODO(Aditya)` removed |
| `frontend/README.md` | New "Brand assets" section; PWA section's "placeholder" note updated |

## All commands, in order

Run from `frontend/`.

### 0. Prerequisites (only if you need to regenerate the rasters)

`rsvg-convert` (librsvg) on PATH — this machine already has it via MSYS2:
`pacman -S mingw-w64-x86_64-librsvg2`. macOS: `brew install librsvg`. Debian/Ubuntu:
`apt install librsvg2-bin`. Plus a `python3` on PATH (any version — `pack_ico.py` is pure
standard library).

### 1. Regenerate the raster assets (only after editing an SVG in `public/brand/`)

```bash
bash scripts/generate-brand-assets.sh
```

Expected: `Done. 11 splash screens, favicon.ico, apple-touch-icon.png and PWA icons written.`

### 2. Checks

```bash
pnpm lint
pnpm build
```

### 3. Manual test

```bash
pnpm dev
```

Open `http://localhost:5173/`:

1. Browser tab shows the new teal "N" favicon, not the old plain slate one.
2. Every button, focus ring, and card border across the app (dashboard, sign-in, landing) now
   reads in Nomad Teal instead of shadcn slate — no component code changed to make this happen.
3. DevTools → Application → Manifest: icons resolve, `theme_color` is `#0B5D71`.
4. `pnpm build` then `pnpm preview`, install the PWA (Chrome: address-bar install icon) — the
   installed app icon and splash (Android) use the new mark.

## Verified results (2026-09-25, browser pane)

| Check | Result |
|---|---|
| `pnpm lint` | Clean |
| `pnpm build` | Clean (`tsc -b && vite build`) |
| `generate-brand-assets.sh` | All 11 splash screens + favicon.ico + apple-touch-icon + PWA icons written, no errors |
| `logo-mark.svg` rendered | Clean, legible teal/white/gold mark |
| `logo-full.svg` rendered | Lockup fits its viewBox with margin to spare |
| `maskable-512x512.png` | Glyph stays well inside the safe zone after the Android crop |
| Landing page, dashboard, sign-in re-themed | All re-color from the new tokens with zero component changes |
| `dist/manifest.webmanifest` after `pnpm build` | `theme_color: "#0B5D71"`, all 3 icon entries point at the regenerated PNGs |

## Definition of Done (Documentation-adjacent Frontend task)

- [x] Logo: 2 variants (`logo-full.svg`, `logo-mark.svg`), plus the maskable technical derivative
- [x] Color palette defined and documented with hex values (for the pitch deck)
- [x] Favicon suite 16–512 px (`favicon.ico` 16/32/48, `favicon.svg`, up to `pwa-512x512.png`)
- [x] PWA icons (`any` 192/512, `maskable` 512)
- [x] Splash screens (11 standard iOS portrait sizes)
- [x] Reproducible generation pipeline, not hand-exported one-off files

## Commit

Branch: `feature/frontend-brand-assets`.

```bash
git add frontend/src/styles/tokens.css frontend/tailwind.config.ts frontend/index.html \
  frontend/vite.config.ts frontend/README.md frontend/scripts/generate-brand-assets.sh \
  frontend/scripts/pack_ico.py frontend/public/brand frontend/public/favicon.svg \
  frontend/public/favicon.ico frontend/public/apple-touch-icon.png frontend/public/icons \
  frontend/public/splash docs/runbooks/NF-P1-024-brand-assets.md
git commit -m "feat(frontend): add brand palette, logo and generated icon suite" -m "Refs: NF-P1-024"
```

## Not covered here

- A dark-mode toggle in the UI: `tokens.css` has a real `.dark` palette, but nothing currently
  applies the `.dark` class (`src/store/uiStore.ts` is still an empty stub) — that's a separate,
  unassigned task.
- Landscape Apple splash screens: only the 11 standard portrait sizes were generated; landscape
  launch on iPad falls back to a plain white screen for a moment, which is a soft, cosmetic gap.
- A native-speaker or professional designer review of the mark — this is a prototype-quality
  logo, not a reviewed final brand identity.
