import { Timestamp } from "firebase/firestore";
import { describe, expect, it } from "vitest";

import type { BillEntry, IncomeEntry } from "@/types/fib";
import {
  billsByCategory,
  incomeByCategory,
  majorityCurrency,
  monthKey,
  monthlyTotals,
  monthWindow,
} from "@/utils/fibTimeline";

// A real value, not a stand-in: these functions never read `created_at`, but the entry types
// require it, and `Timestamp.fromDate` needs no live Firestore connection to construct one.
const SOME_TIMESTAMP = Timestamp.fromDate(new Date("2026-09-01"));

function income(over: Partial<IncomeEntry> & { id: string }): IncomeEntry {
  return {
    entry_date: "2026-09-01",
    amount: 100,
    currency: "SGD",
    category: "salary",
    category_source: "user",
    verified: false,
    source: "manual",
    created_at: SOME_TIMESTAMP,
    ...over,
  };
}

function bill(over: Partial<BillEntry> & { id: string }): BillEntry {
  return {
    entry_date: "2026-09-01",
    amount: 50,
    currency: "SGD",
    paid: true,
    source: "manual",
    created_at: SOME_TIMESTAMP,
    ...over,
  };
}

describe("monthKey", () => {
  it("takes the year-month prefix of an ISO date", () => {
    expect(monthKey("2026-09-25")).toBe("2026-09");
  });
});

describe("monthWindow", () => {
  it("returns the last N months, oldest first, ending on the given month", () => {
    expect(monthWindow(3, new Date(Date.UTC(2026, 0, 15)))).toEqual([
      "2025-11",
      "2025-12",
      "2026-01",
    ]);
  });

  it("handles a window of one month", () => {
    expect(monthWindow(1, new Date(Date.UTC(2026, 8, 1)))).toEqual(["2026-09"]);
  });
});

describe("majorityCurrency", () => {
  it("is null for no entries", () => {
    expect(majorityCurrency([])).toBeNull();
  });

  it("picks the currency with the most entries", () => {
    const entries = [{ currency: "SGD" }, { currency: "SGD" }, { currency: "USD" }];
    expect(majorityCurrency(entries)).toBe("SGD");
  });
});

describe("monthlyTotals", () => {
  const window = ["2026-08", "2026-09"];

  it("sums income and bills per month, only in the given currency", () => {
    const incomeEntries = [
      income({ id: "i1", entry_date: "2026-08-01", amount: 600 }),
      income({ id: "i2", entry_date: "2026-09-01", amount: 650 }),
      income({ id: "i3", entry_date: "2026-09-15", amount: 90, currency: "USD" }),
    ];
    const bills = [
      bill({ id: "b1", entry_date: "2026-08-20", amount: 40 }),
      bill({ id: "b2", entry_date: "2026-09-05", amount: 38.5 }),
    ];

    expect(monthlyTotals(incomeEntries, bills, window, "SGD")).toEqual([
      { month: "2026-08", income: 600, expense: 40 },
      { month: "2026-09", income: 650, expense: 38.5 },
    ]);
  });

  it("zeroes a month with no matching entries", () => {
    expect(monthlyTotals([], [], window, "SGD")).toEqual([
      { month: "2026-08", income: 0, expense: 0 },
      { month: "2026-09", income: 0, expense: 0 },
    ]);
  });
});

describe("incomeByCategory / billsByCategory", () => {
  it("sums by category in the given fixed order, skipping categories with nothing logged", () => {
    const entries = [
      income({ id: "i1", category: "salary", amount: 600 }),
      income({ id: "i2", category: "bonus", amount: 50 }),
      income({ id: "i3", category: "salary", amount: 50 }),
    ];
    expect(
      incomeByCategory(entries, ["salary", "overtime", "bonus", "other_income"], "SGD")
    ).toEqual([
      { category: "salary", amount: 650 },
      { category: "bonus", amount: 50 },
    ]);
  });

  it("leaves out entries in another currency or with no category", () => {
    const entries = [
      bill({ id: "b1", category: "rent", amount: 500 }),
      bill({ id: "b2", category: "rent", amount: 500, currency: "USD" }),
      bill({ id: "b3", amount: 10 }),
    ];
    expect(billsByCategory(entries, ["rent", "utilities"], "SGD")).toEqual([
      { category: "rent", amount: 500 },
    ]);
  });
});
