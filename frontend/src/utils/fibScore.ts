// Fixed, never themed — the dataviz skill's own status palette (good/warning/critical),
// validated distinct from the categorical chart colors in utils/fibChartColors.ts. Always
// paired with a text label wherever it's used: on the light surface "warning" alone clears
// only 1.79:1 contrast.
export const STATUS_COLOR = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" } as const;
export type Status = keyof typeof STATUS_COLOR;

// The same three states as TEXT. The fills above are for rings, bars and arcs, which need 3:1;
// words need 4.5:1, which "good" clears at 3.3:1 on white and "warning" at 1.8:1 does not. These
// follow the theme, so the words stay readable on the dark surface too.
export const STATUS_INK = {
  good: "hsl(var(--safe-ink))",
  warning: "hsl(var(--caution-ink))",
  critical: "hsl(var(--danger-ink))",
} as const;

// For the printed-sheet preview, which is paper in both themes: the light theme's three inks as
// fixed colours (each is 5:1 or better on the paper).
export const STATUS_PAPER_INK = {
  good: "#047756",
  warning: "#994a00",
  critical: "#ba1c1c",
} as const;

export function statusFor(score: number): Status {
  if (score >= 70) {
    return "good";
  }
  return score >= 40 ? "warning" : "critical";
}

/** The `savings_rate` metric's own real percentage (`detail.savings_rate`), more meaningful
 * to a worker than its normalized 0-100 score. Null when the metric carries no such detail
 * (no score, or a metric other than `savings_rate`). */
export function savingsRatePct(detail: Record<string, unknown>, language: string): string | null {
  const rate = detail.savings_rate;
  if (typeof rate !== "number") {
    return null;
  }
  return rate.toLocaleString(language, { style: "percent", maximumFractionDigits: 0 });
}
