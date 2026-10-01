import type { BillEntry } from "@/types/fib";

/**
 * Bills `/fib/categorize` would still sort: no category, or a bill photo's guess that has no
 * confidence yet. The backend's own rule (`categorizer._is_pending`); income always carries
 * the category the worker picked, so only bills are ever pending here.
 */
export function pendingBillCount(bills: readonly BillEntry[]): number {
  return bills.filter(
    (bill) =>
      !bill.category || (bill.category_source === "model" && bill.category_confidence == null)
  ).length;
}
