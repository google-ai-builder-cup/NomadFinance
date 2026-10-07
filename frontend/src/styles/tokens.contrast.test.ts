// The colour pairs the scam screens rely on, measured from the real tokens.css in both themes
// (NF-SA-019). The file says every pair was checked against WCAG 2.2 AA; this keeps it true when a
// token changes. A real browser measured the same screens (docs/runbooks/NF-SA-019-scam-i18n-a11y.md);
// this is the part of that which can run in CI.
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

type Rgb = [number, number, number];
type Theme = "light" | "dark";

const CSS = readFileSync(path.resolve(process.cwd(), "src/styles/tokens.css"), "utf8");

/** The custom properties in the first `selector { ... }` block of the file. */
function block(selector: string): Record<string, string> {
  const start = CSS.indexOf(`${selector} {`);
  const end = CSS.indexOf("\n}", start);
  const found: Record<string, string> = {};
  for (const match of CSS.slice(start, end).matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    found[match[1]] = match[2].trim();
  }
  return found;
}

const TOKENS: Record<Theme, Record<string, string>> = (() => {
  const light = block(":root");
  return { light, dark: { ...light, ...block(".dark") } };
})();

/** `192 82% 24%` as sRGB. */
function hsl(triplet: string): Rgb {
  const [h, s, l] = triplet.match(/[\d.]+/g)!.map(Number);
  const sat = s / 100;
  const light = l / 100;
  const a = sat * Math.min(light, 1 - light);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    return light - a * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [f(0) * 255, f(8) * 255, f(4) * 255];
}

const luminance = ([r, g, b]: Rgb) => {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
};

const contrast = (a: Rgb, b: Rgb) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

const over = (top: Rgb, alpha: number, below: Rgb): Rgb =>
  top.map((v, i) => v * alpha + below[i] * (1 - alpha)) as Rgb;

/** A token, optionally some way transparent over another token (a border, a tinted panel). */
interface Layer {
  token: string;
  alpha?: number;
  over?: string;
}

function colour(theme: Theme, layer: Layer): Rgb {
  const rgb = hsl(TOKENS[theme][layer.token]);
  return layer.alpha === undefined
    ? rgb
    : over(rgb, layer.alpha, hsl(TOKENS[theme][layer.over ?? "card"]));
}

interface Pair {
  /** Where it is used, for the failure message. */
  use: string;
  fg: Layer;
  bg: Layer;
}

// Text: 4.5:1 (WCAG 1.4.3).
const TEXT: Pair[] = [
  { use: "body text on the page", fg: { token: "foreground" }, bg: { token: "background" } },
  { use: "body text on a card", fg: { token: "card-foreground" }, bg: { token: "card" } },
  { use: "muted text on the page", fg: { token: "muted-foreground" }, bg: { token: "background" } },
  { use: "muted text on a card", fg: { token: "muted-foreground" }, bg: { token: "card" } },
  {
    use: "muted text in the tactic and explainer panels",
    fg: { token: "muted-foreground" },
    bg: { token: "muted", alpha: 0.6 },
  },
  {
    use: "muted text on the pillar band",
    fg: { token: "muted-foreground" },
    bg: { token: "radar-tint" },
  },
  {
    use: "the heading on the pillar band",
    fg: { token: "foreground" },
    bg: { token: "radar-tint" },
  },
  { use: "a button's label", fg: { token: "primary-foreground" }, bg: { token: "primary" } },
  { use: "an error message on a card", fg: { token: "danger-ink" }, bg: { token: "card" } },
  { use: "an error message on the page", fg: { token: "danger-ink" }, bg: { token: "background" } },
  {
    use: "an error in a tinted notice",
    fg: { token: "danger-ink" },
    bg: { token: "destructive", alpha: 0.05 },
  },
  { use: "the chosen mode", fg: { token: "radar-ink" }, bg: { token: "radar-tint" } },
  { use: "a safe badge", fg: { token: "safe-tint-ink" }, bg: { token: "safe-tint" } },
  { use: "a caution badge", fg: { token: "caution-tint-ink" }, bg: { token: "caution-tint" } },
  { use: "a danger badge", fg: { token: "danger-tint-ink" }, bg: { token: "danger-tint" } },
  {
    use: "an info badge and the low-confidence note",
    fg: { token: "info-tint-ink" },
    bg: { token: "info-tint" },
  },
];

// What is not text but has to be seen: the outline of an empty box, the focus ring, an icon that
// carries meaning. 3:1 (WCAG 1.4.11).
const GRAPHICS: Pair[] = [
  {
    use: "the outline of a text box, on a card",
    fg: { token: "muted-foreground", alpha: 0.8, over: "card" },
    bg: { token: "card" },
  },
  {
    use: "the outline of a text box, on the page",
    fg: { token: "muted-foreground", alpha: 0.8, over: "background" },
    bg: { token: "background" },
  },
  { use: "the focus ring on a card", fg: { token: "ring" }, bg: { token: "card" } },
  { use: "the focus ring on the page", fg: { token: "ring" }, bg: { token: "background" } },
  { use: "the shield of a scam", fg: { token: "danger" }, bg: { token: "card" } },
  {
    use: "the shield of a message that is not a scam",
    fg: { token: "safe" },
    bg: { token: "card" },
  },
  { use: "the spinner", fg: { token: "primary" }, bg: { token: "card" } },
];

const THEMES: Theme[] = ["light", "dark"];

describe.each(THEMES)("the %s theme", (theme) => {
  it.each(TEXT)("text: $use is at least 4.5:1", ({ fg, bg, use }) => {
    const below = colour(theme, bg);
    const ratio = contrast(over(colour(theme, { token: fg.token }), 1, below), below);

    expect(ratio, `${use}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
  });

  it.each(GRAPHICS)("graphics: $use is at least 3:1", ({ fg, bg, use }) => {
    const ratio = contrast(colour(theme, fg), colour(theme, bg));

    expect(ratio, `${use}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3);
  });
});

describe("the measurement itself", () => {
  it("reads both themes, the dark one over the light one", () => {
    expect(TOKENS.light.background).not.toBe(TOKENS.dark.background);
    expect(TOKENS.dark.radius).toBe(TOKENS.light.radius);
  });

  it("agrees with the known ratios of black and white and of two greys", () => {
    expect(contrast([0, 0, 0], [255, 255, 255])).toBeCloseTo(21, 5);
    expect(contrast([118, 118, 118], [255, 255, 255])).toBeCloseTo(4.54, 2);
    expect(contrast([180, 180, 180], [255, 255, 255])).toBeCloseTo(2.07, 2);
  });

  it("shows why error text is `danger-ink`: `destructive` is a button fill, 2.6:1 as text on a dark card", () => {
    const destructive = colour("dark", { token: "destructive" });
    const card = colour("dark", { token: "card" });

    expect(contrast(destructive, card)).toBeLessThan(3);
    expect(contrast(colour("dark", { token: "danger-ink" }), card)).toBeGreaterThanOrEqual(4.5);
  });

  it("is able to fail: the old field border, the 1.3:1 box that was found in the browser", () => {
    const input = hsl(TOKENS.light.input);
    const card = hsl(TOKENS.light.card);

    expect(contrast(input, card)).toBeLessThan(3);
  });
});
