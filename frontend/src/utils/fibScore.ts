// Fixed, never themed — the dataviz skill's own status palette (good/warning/critical),
// validated distinct from the categorical chart colors in utils/fibChartColors.ts. Always
// paired with a text label wherever it's used: on the light surface "warning" alone clears
// only 1.79:1 contrast.
export const STATUS_COLOR = { good: "#0ca30c", warning: "#fab219", critical: "#d03b3b" } as const;
export type Status = keyof typeof STATUS_COLOR;

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
