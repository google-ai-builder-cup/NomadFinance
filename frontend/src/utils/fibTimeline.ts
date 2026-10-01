import type { BillCategory, BillEntry, IncomeCategory, IncomeEntry } from "@/types/fib";

/** `"2026-09-25"` -> `"2026-09"`. */
export function monthKey(isoDate: string): string {
  return isoDate.slice(0, 7);
}

/** The last `months` month keys, oldest first, ending with the current month. */
export function monthWindow(months: number, today: Date): string[] {
  const keys: string[] = [];
  for (let back = months - 1; back >= 0; back -= 1) {
    const date = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth() - back, 1));
    keys.push(`${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`);
  }
  return keys;
}

/**
 * The currency most of `entries` are logged in. Nothing on this dashboard converts between
 * currencies (no general FX lookup exists client-side, only the remittance compare flow's own
 * corridor rates), so the chart and breakdowns total one currency and leave the rest out —
 * the same exclusion the backend's own `profile_metrics.py` applies, just chosen by majority
 * here instead of the worker's home-country rate.
 */
export function majorityCurrency(entries: readonly { currency: string }[]): string | null {
  if (entries.length === 0) {
    return null;
  }
  const counts = new Map<string, number>();
  for (const entry of entries) {
    counts.set(entry.currency, (counts.get(entry.currency) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [currency, count] of counts) {
    if (count > bestCount) {
      best = currency;
      bestCount = count;
    }
  }
  return best;
}

export interface MonthlyTotal {
  month: string;
  income: number;
  expense: number;
}

/** One row per month in `window`, summing only entries logged in `currency`. */
export function monthlyTotals(
  income: readonly IncomeEntry[],
  bills: readonly BillEntry[],
  window: readonly string[],
  currency: string
): MonthlyTotal[] {
  const byMonth = new Map<string, MonthlyTotal>(
    window.map((month) => [month, { month, income: 0, expense: 0 }])
  );
  for (const entry of income) {
    if (entry.currency !== currency) {
      continue;
    }
    const row = byMonth.get(monthKey(entry.entry_date));
    if (row) {
      row.income += entry.amount;
    }
  }
  for (const entry of bills) {
    if (entry.currency !== currency) {
      continue;
    }
    const row = byMonth.get(monthKey(entry.entry_date));
    if (row) {
      row.expense += entry.amount;
    }
  }
  return window.map((month) => byMonth.get(month) as MonthlyTotal);
}

export interface CategoryTotal<C extends string> {
  category: C;
  amount: number;
}

/**
 * One row per category in `order` that has at least one matching entry, summing only entries
 * logged in `currency`, in `order`'s fixed sequence (never re-sorted by amount: color identity
 * in `CategoryBreakdown` is assigned by this same fixed order).
 */
function categoryTotals<C extends string>(
  entries: readonly { category?: C; amount: number; currency: string }[],
  order: readonly C[],
  currency: string
): CategoryTotal<C>[] {
  const totals = new Map<C, number>();
  for (const entry of entries) {
    if (entry.currency !== currency || entry.category === undefined) {
      continue;
    }
    totals.set(entry.category, (totals.get(entry.category) ?? 0) + entry.amount);
  }
  return order
    .filter((category) => totals.has(category))
    .map((category) => ({ category, amount: totals.get(category) as number }));
}

export function incomeByCategory(
  income: readonly IncomeEntry[],
  order: readonly IncomeCategory[],
  currency: string
): CategoryTotal<IncomeCategory>[] {
  return categoryTotals(income, order, currency);
}

export function billsByCategory(
  bills: readonly BillEntry[],
  order: readonly BillCategory[],
  currency: string
): CategoryTotal<BillCategory>[] {
  return categoryTotals(bills, order, currency);
}
