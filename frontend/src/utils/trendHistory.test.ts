import { describe, expect, it } from "vitest";

import { historyStartsLate } from "@/utils/trendHistory";

const NOW = new Date("2026-10-01T12:00:00Z");
const points = (...dates: string[]) => dates.map((date) => ({ date, rate: 43 }));

describe("historyStartsLate", () => {
  it("names the first day when only a few recent days are stored", () => {
    const fewDays = points("2026-09-26", "2026-09-29", "2026-09-30", "2026-10-01");

    expect(historyStartsLate(fewDays, 30, NOW)).toBe("2026-09-26");
    expect(historyStartsLate(fewDays, 365, NOW)).toBe("2026-09-26");
  });

  it("is null when the history covers the period, a holiday at the start included", () => {
    expect(historyStartsLate(points("2026-09-04", "2026-09-30"), 30, NOW)).toBeNull();
    expect(historyStartsLate(points("2025-10-06", "2026-09-30"), 365, NOW)).toBeNull();
  });

  it("is null with no points", () => {
    expect(historyStartsLate([], 90, NOW)).toBeNull();
  });
});
