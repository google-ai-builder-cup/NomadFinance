import { describe, expect, it } from "vitest";

import type { CoachPlanBody, PlanWarning } from "@/types/coach";
import {
  humanId,
  planMoney,
  remittanceLink,
  sendWeeks,
  warningsBySeverity,
} from "@/utils/coachPlan";

function plan(overrides: Partial<CoachPlanBody["remittance"]> = {}, warnings: PlanWarning[] = []) {
  return {
    remittance: {
      corridor_id: "AU-IN",
      monthly_amount: { amount: 900, currency: "AUD" },
      provider: null,
      schedule: [
        { week: 5, amount: { amount: 900, currency: "AUD" } },
        { week: 9, amount: { amount: 900, currency: "AUD" } },
      ],
      ...overrides,
    },
    warnings,
  } as unknown as CoachPlanBody;
}

describe("a figure as the PDF writes it", () => {
  it.each([
    [{ amount: 4200, currency: "AUD" }, "4,200 AUD"],
    [{ amount: 1473.72, currency: "AUD" }, "1,473.72 AUD"],
    [{ amount: 48991.2, currency: "INR" }, "48,991.2 INR"],
    [{ amount: 0, currency: "SGD" }, "0 SGD"],
    [{ amount: -455, currency: "SGD" }, "-455 SGD"],
    [{ amount: 3390000, currency: "KRW" }, "3,390,000 KRW"],
    [{ amount: 2177.07, currency: "AUD" }, "2,177.07 AUD"],
  ])("%j is %s", (money, text) => {
    expect(planMoney(money)).toBe(text);
  });
});

describe("the link into Remittance X-Ray", () => {
  it("carries the corridor and the monthly amount", () => {
    expect(remittanceLink(plan())).toBe("/remittance?corridor=AU-IN&amount=900");
  });

  it("keeps a decimal amount as it is", () => {
    const link = remittanceLink(
      plan({ monthly_amount: { amount: 412.5, currency: "SGD" }, corridor_id: "SG-PH" })
    );

    expect(link).toBe("/remittance?corridor=SG-PH&amount=412.5");
  });

  it.each([
    ["a route outside the six corridors", { corridor_id: null }],
    ["a corridor the screen does not know", { corridor_id: "NP-BD" }],
    ["nothing to send", { monthly_amount: { amount: 0, currency: "AUD" } }],
  ])("is none for %s", (_label, change) => {
    expect(remittanceLink(plan(change as Partial<CoachPlanBody["remittance"]>))).toBeNull();
  });
});

describe("the weeks to send", () => {
  it("are the weeks of the schedule", () => {
    expect([...sendWeeks(plan())]).toEqual([5, 9]);
    expect(sendWeeks(plan({ schedule: [] })).size).toBe(0);
  });
});

describe("the warnings", () => {
  const w = (id: string, severity: PlanWarning["severity"]): PlanWarning => ({
    id,
    severity,
    text: id,
  });

  it("come most serious first and keep the plan's order among equals", () => {
    const sorted = warningsBySeverity(
      plan({}, [
        w("a", "info"),
        w("b", "warning"),
        w("c", "urgent"),
        w("d", "warning"),
        w("e", "urgent"),
      ])
    );

    expect(sorted.map((x) => x.id)).toEqual(["c", "e", "b", "d", "a"]);
  });
});

describe("an id the screen has no words for", () => {
  it("is shown as words", () => {
    expect(humanId("child_care")).toBe("Child care");
    expect(humanId("rent")).toBe("Rent");
  });
});
