// Values live in styles/tokens.css (:root and .dark) — see the comment there for how this
// palette was chosen and validated. Referenced here by role, never raw hex, so swapping the
// brand's own chart colors later touches one file.

export const CHART_INCOME_COLOR = "var(--chart-income)";
export const CHART_EXPENSE_COLOR = "var(--chart-expense)";

/** Fixed categorical order, slots 1-8. Assign by a category's position in its own type's
 * array (`INCOME_CATEGORIES`/`BILL_CATEGORIES`), never by rank or value, so a category keeps
 * the same color everywhere it appears. */
export const CATEGORY_CHART_COLORS = [
  "var(--chart-cat-1)",
  "var(--chart-cat-2)",
  "var(--chart-cat-3)",
  "var(--chart-cat-4)",
  "var(--chart-cat-5)",
  "var(--chart-cat-6)",
  "var(--chart-cat-7)",
  "var(--chart-cat-8)",
] as const;
