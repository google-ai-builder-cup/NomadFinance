import { describe, expect, it } from "vitest";

import type { BillEntry } from "@/types/fib";
import { pendingBillCount } from "@/utils/pendingCategories";

const bill = (fields: Partial<BillEntry>) => fields as BillEntry;

describe("pendingBillCount", () => {
  it("counts bills without a category and photo guesses without a confidence", () => {
    const bills = [
      bill({}),
      bill({ category: "utilities", category_source: "model" }),
      bill({ category: "utilities", category_source: "model", category_confidence: null }),
      bill({ category: "rent", category_source: "model", category_confidence: 0.9 }),
      bill({ category: "phone_internet", category_source: "user" }),
    ];

    expect(pendingBillCount(bills)).toBe(3);
  });

  it("is zero with nothing to sort", () => {
    expect(pendingBillCount([])).toBe(0);
  });
});
