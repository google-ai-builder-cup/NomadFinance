import { describe, expect, it } from "vitest";

import type { CoachScore } from "@/types/coach";
import { bandTone, factorKey, isHeldByFloor, isKnownBand, levelOf } from "@/utils/coachScore";

function score(total: number, band: string, points: number[]): CoachScore {
  const ids = [
    "debt_to_income",
    "emergency_buffer",
    "remittance_ratio",
    "recruitment_fee_vs_cap",
    "banked_status",
  ] as const;
  return {
    total,
    band,
    rubric_version: 1,
    factors: ids.map((id, index) => ({ id, value: 1, score: points[index], weight: 0.2 })),
  };
}

describe("the level of a factor", () => {
  it.each([
    [0, "weak"],
    [39, "weak"],
    [39.4, "weak"],
    [40, "fair"],
    [69, "fair"],
    [70, "strong"],
    [100, "strong"],
  ] as const)("%d points is %s", (points, level) => {
    expect(levelOf(points)).toBe(level);
  });
});

describe("bands", () => {
  it("knows the three of the rubric and treats another as neutral", () => {
    expect(["needs_work", "getting_ready", "well_prepared"].every(isKnownBand)).toBe(true);
    expect(isKnownBand("excellent")).toBe(false);
    expect(bandTone("needs_work")).toBe("danger");
    expect(bandTone("getting_ready")).toBe("caution");
    expect(bandTone("well_prepared")).toBe("safe");
    expect(bandTone("excellent")).toBe("neutral");
  });
});

describe("the floor rule's note", () => {
  it("applies when 70 points or more is held at 'getting ready' by a factor under 20", () => {
    expect(isHeldByFloor(score(74, "getting_ready", [100, 100, 100, 10, 100]))).toBe(true);
  });

  it.each([
    ["a total under 70", score(60, "getting_ready", [100, 100, 10, 50, 40])],
    ["a factor at exactly 20", score(74, "getting_ready", [100, 100, 100, 20, 100])],
    ["a band that is not held", score(91, "well_prepared", [100, 100, 100, 100, 19])],
    ["a low band", score(17, "needs_work", [5, 0, 25, 10, 0])],
  ])("does not apply to %s", (_label, value) => {
    expect(isHeldByFloor(value)).toBe(false);
  });
});

describe("the copy keys", () => {
  it("are by factor, level and part", () => {
    expect(factorKey("debt_to_income", "weak", "improve")).toBe(
      "score.factor.debt_to_income.weak.improve"
    );
  });
});
