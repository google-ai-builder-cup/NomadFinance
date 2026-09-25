#!/usr/bin/env bash
# Regenerate every raster brand asset (favicons, PWA icons, Apple splash screens) from the
# vector sources in public/brand/. Run from frontend/ whenever the logo changes.
#
# Needs `rsvg-convert` (librsvg) on PATH: `pacman -S mingw-w64-x86_64-librsvg2` (MSYS2/Git Bash
# on Windows), `brew install librsvg` (macOS), or `apt install librsvg2-bin` (Debian/Ubuntu).
set -euo pipefail
cd "$(dirname "$0")/.."

command -v rsvg-convert >/dev/null || {
  echo "rsvg-convert not found on PATH — see the comment at the top of this script." >&2
  exit 1
}

MARK=public/brand/logo-mark.svg
MASKABLE=public/brand/logo-mark-maskable.svg
BG_COLOR="#ffffff" # matches manifest.background_color in vite.config.ts

echo "== Favicons and app icons =="
rsvg-convert -w 16 -h 16 -o public/brand/.favicon-16.png "$MARK"
rsvg-convert -w 32 -h 32 -o public/brand/.favicon-32.png "$MARK"
rsvg-convert -w 48 -h 48 -o public/brand/.favicon-48.png "$MARK"
rsvg-convert -w 180 -h 180 -o public/apple-touch-icon.png "$MARK"
rsvg-convert -w 192 -h 192 -o public/icons/pwa-192x192.png "$MARK"
rsvg-convert -w 512 -h 512 -o public/icons/pwa-512x512.png "$MARK"
rsvg-convert -w 512 -h 512 -o public/icons/maskable-512x512.png "$MASKABLE"

python3 scripts/pack_ico.py \
  public/brand/.favicon-16.png public/brand/.favicon-32.png public/brand/.favicon-48.png \
  --output public/favicon.ico
rm -f public/brand/.favicon-16.png public/brand/.favicon-32.png public/brand/.favicon-48.png

echo "== Apple splash screens =="
mkdir -p public/splash
# width height (logical-point x device-pixel-ratio, portrait) -> matches the
# apple-touch-startup-image media queries in index.html
SIZES=(
  "640 1136"   # iPhone SE (1st gen)
  "750 1334"   # iPhone 6/7/8, SE (2nd/3rd gen)
  "828 1792"   # iPhone 11, XR
  "1125 2436"  # iPhone X/XS, 11 Pro, 12/13 mini
  "1170 2532"  # iPhone 12/13/14
  "1179 2556"  # iPhone 14/15 Pro
  "1242 2688"  # iPhone XS Max, 11 Pro Max
  "1284 2778"  # iPhone 12/13/14 Pro Max
  "1536 2048"  # iPad 9.7", iPad mini
  "1668 2388"  # iPad Air, iPad Pro 11"
  "2048 2732"  # iPad Pro 12.9"
)

for size in "${SIZES[@]}"; do
  read -r w h <<<"$size"
  icon=$(python3 -c "print(min($w, $h) * 0.28)")
  scale=$(python3 -c "print($icon / 64)")
  cx=$(python3 -c "print($w / 2)")
  cy=$(python3 -c "print($h / 2)")
  svg=$(cat <<EOF
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 $w $h">
  <rect width="$w" height="$h" fill="$BG_COLOR" />
  <g transform="translate($cx $cy) scale($scale) translate(-32 -32)">
    <rect width="64" height="64" rx="12" fill="#0B5D71" />
    <path d="M20 46 L20 18 L44 46 L44 18" fill="none" stroke="#FFFFFF"
          stroke-width="7" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="44" cy="18" r="5" fill="#F59E0B" />
  </g>
</svg>
EOF
)
  echo "$svg" | rsvg-convert -w "$w" -h "$h" -o "public/splash/apple-splash-${w}-${h}.png"
done

echo "Done. $(ls public/splash | wc -l) splash screens, favicon.ico, apple-touch-icon.png and PWA icons written."
