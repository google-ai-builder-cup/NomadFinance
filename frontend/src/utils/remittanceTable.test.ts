import { describe, expect, it } from "vitest";

import type { ProviderResult } from "@/types/remittance";
import { type SortState, nextSortState, sortProviders } from "@/utils/remittanceTable";

function provider(
  over: Partial<ProviderResult> & { rpw_id: number; firm: string }
): ProviderResult {
  return {
    firm_type: "Money Transfer Operator",
    payment_instrument: "Bank account transfer",
    access_point: "Internet",
    pickup_method: "Bank account",
    speed: "Same day",
    speed_order: 1,
    network_coverage: null,
    note: null,
    payout_currency: "PHP",
    comparable: true,
    rank: 1,
    estimated: false,
    fee: 3.3,
    fx_margin_pct: 0.07,
    rate_cost: 0.35,
    total_cost: 3.65,
    total_cost_pct: 0.73,
    recipient_receives: 24274.17,
    lost_to_costs: 178.83,
    less_than_best: 0,
    ...over,
  };
}

describe("sortProviders", () => {
  const best = provider({
    rpw_id: 1,
    firm: "InstaReM",
    recipient_receives: 24453,
    fee: 3,
    speed_order: 0,
    speed: "Same day",
    total_cost_pct: 0.5,
  });
  const mid = provider({
    rpw_id: 2,
    firm: "Wise",
    recipient_receives: 24000,
    fee: 5,
    speed_order: 1,
    speed: "Next day",
    total_cost_pct: 1.2,
    rank: 2,
    less_than_best: 453,
  });
  const worst = provider({
    rpw_id: 3,
    firm: "Maybank",
    recipient_receives: 23000,
    fee: 10,
    speed_order: 2,
    speed: "3-5 days",
    total_cost_pct: 2.5,
    rank: 3,
    less_than_best: 1453,
  });
  const notComparable = provider({
    rpw_id: 4,
    firm: "USD Direct",
    comparable: false,
    rank: null,
    recipient_receives: null,
    lost_to_costs: null,
    less_than_best: null,
    payout_currency: "USD",
  });
  const providers = [worst, notComparable, best, mid];

  it("defaults to the highest amount received first, comparable providers only", () => {
    const sorted = sortProviders(providers, { column: "receives", direction: "desc" });

    expect(sorted.map((p) => p.firm)).toEqual(["InstaReM", "Wise", "Maybank", "USD Direct"]);
  });

  it("keeps non-comparable providers last no matter the sort column", () => {
    const sorted = sortProviders(providers, { column: "fee", direction: "asc" });

    expect(sorted.at(-1)?.firm).toBe("USD Direct");
  });

  it("sorts by fee ascending (cheapest first)", () => {
    const sorted = sortProviders(providers, { column: "fee", direction: "asc" });

    expect(sorted.slice(0, 3).map((p) => p.firm)).toEqual(["InstaReM", "Wise", "Maybank"]);
  });

  it("sorts by speed using speed_order, not the text", () => {
    // Alphabetically "3-5 days" < "Next day" < "Same day", the opposite of speed_order.
    const sorted = sortProviders(providers, { column: "speed", direction: "asc" });

    expect(sorted.slice(0, 3).map((p) => p.speed)).toEqual(["Same day", "Next day", "3-5 days"]);
  });

  it("sorts by provider name case-insensitively", () => {
    const sorted = sortProviders(providers, { column: "provider", direction: "asc" });

    expect(sorted.slice(0, 3).map((p) => p.firm)).toEqual(["InstaReM", "Maybank", "Wise"]);
  });

  it("breaks a tie by the original rpw_id order, whichever direction is asked for", () => {
    const tied = [
      provider({ rpw_id: 20, firm: "B", fee: 5 }),
      provider({ rpw_id: 10, firm: "A", fee: 5 }),
    ];

    expect(sortProviders(tied, { column: "fee", direction: "asc" }).map((p) => p.rpw_id)).toEqual([
      10, 20,
    ]);
    expect(sortProviders(tied, { column: "fee", direction: "desc" }).map((p) => p.rpw_id)).toEqual([
      10, 20,
    ]);
  });
});

describe("nextSortState", () => {
  it("picks the column's own best-first direction the first time it is clicked", () => {
    const current: SortState = { column: "receives", direction: "desc" };

    expect(nextSortState(current, "fee")).toEqual({ column: "fee", direction: "asc" });
    expect(nextSortState(current, "provider")).toEqual({ column: "provider", direction: "asc" });
  });

  it("flips direction when the same column is clicked again", () => {
    expect(nextSortState({ column: "fee", direction: "asc" }, "fee")).toEqual({
      column: "fee",
      direction: "desc",
    });
    expect(nextSortState({ column: "fee", direction: "desc" }, "fee")).toEqual({
      column: "fee",
      direction: "asc",
    });
  });
});
