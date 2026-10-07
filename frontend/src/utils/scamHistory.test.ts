import { describe, expect, it } from "vitest";

import { formatCheckDate } from "@/utils/scamHistory";

describe("formatCheckDate", () => {
  it("writes the date in the worker's language", () => {
    expect(formatCheckDate("2026-11-05T09:20:00Z", "en")).toMatch(/Nov 5, 2026|5 Nov 2026/);
    expect(formatCheckDate("2026-11-05T09:20:00Z", "hi")).toContain("2026");
  });

  it("shows an unreadable value as it came, not as Invalid Date", () => {
    expect(formatCheckDate("not a date", "en")).toBe("not a date");
  });

  it("still gives a date when the language is one the browser does not know", () => {
    expect(formatCheckDate("2026-11-05T09:20:00Z", "!!")).toMatch(/2026/);
  });
});
