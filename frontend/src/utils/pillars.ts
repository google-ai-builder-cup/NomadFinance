// Tailwind only generates classes it can read as whole strings, so each pillar's accent classes
// are spelled out here once instead of being built from the pillar name.
export const PILLAR_KEYS = ["remit", "contract", "radar", "identity"] as const;
export type PillarKey = (typeof PILLAR_KEYS)[number];

export interface PillarStyle {
  /** Solid icon tile: accent fill, white icon. */
  tile: string;
  /** Accent text that clears 4.5:1 on a card and on the tint. */
  text: string;
  /** Soft background wash for header bands and active nav. */
  tint: string;
  /** Left bar and outline accent. */
  bar: string;
  border: string;
  /** Page header: tint fading into the card colour. */
  band: string;
  /** Primary button in the pillar's own colour. */
  button: string;
  /** Raw CSS custom-property names for SVG fills and inline styles. */
  base: string;
  soft: string;
  deep: string;
}

export const PILLAR_STYLES: Readonly<Record<PillarKey, PillarStyle>> = {
  remit: {
    tile: "bg-remit text-white",
    text: "text-remit-ink",
    tint: "bg-remit-tint",
    bar: "bg-remit",
    border: "border-remit",
    band: "bg-gradient-to-br from-remit-tint via-card to-card",
    button: "bg-remit-deep text-white hover:bg-remit-deep/90",
    base: "--remit",
    soft: "--remit-soft",
    deep: "--remit-deep",
  },
  contract: {
    tile: "bg-contract text-white",
    text: "text-contract-ink",
    tint: "bg-contract-tint",
    bar: "bg-contract",
    border: "border-contract",
    band: "bg-gradient-to-br from-contract-tint via-card to-card",
    button: "bg-contract-deep text-white hover:bg-contract-deep/90",
    base: "--contract",
    soft: "--contract-soft",
    deep: "--contract-deep",
  },
  radar: {
    tile: "bg-radar text-white",
    text: "text-radar-ink",
    tint: "bg-radar-tint",
    bar: "bg-radar",
    border: "border-radar",
    band: "bg-gradient-to-br from-radar-tint via-card to-card",
    button: "bg-radar-deep text-white hover:bg-radar-deep/90",
    base: "--radar",
    soft: "--radar-soft",
    deep: "--radar-deep",
  },
  identity: {
    tile: "bg-identity text-white",
    text: "text-identity-ink",
    tint: "bg-identity-tint",
    bar: "bg-identity",
    border: "border-identity",
    band: "bg-gradient-to-br from-identity-tint via-card to-card",
    button: "bg-identity-deep text-white hover:bg-identity-deep/90",
    base: "--identity",
    soft: "--identity-soft",
    deep: "--identity-deep",
  },
};

/** A pillar's colour as a CSS value, for SVG paint and inline styles. */
export function pillarVar(name: string, alpha?: number): string {
  return alpha === undefined ? `hsl(var(${name}))` : `hsl(var(${name}) / ${alpha})`;
}
