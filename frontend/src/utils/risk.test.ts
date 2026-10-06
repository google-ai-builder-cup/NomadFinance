import { describe, expect, it } from "vitest";

import { riskLevelForSeverity, SEVERITIES } from "@/utils/risk";

describe("riskLevelForSeverity", () => {
  it("maps low, medium and high onto the safe, caution and danger colours", () => {
    expect(riskLevelForSeverity("low")).toBe("safe");
    expect(riskLevelForSeverity("medium")).toBe("caution");
    expect(riskLevelForSeverity("high")).toBe("danger");
  });

  it("covers every severity", () => {
    expect(SEVERITIES.map(riskLevelForSeverity)).toEqual(["safe", "caution", "danger"]);
  });
});
