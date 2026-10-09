import { describe, expect, it } from "vitest";

import { relativeTime } from "@/utils/relativeTime";

const NOW = Date.parse("2026-10-20T12:00:00Z");
const ago = (seconds: number) => new Date(NOW - seconds * 1000).toISOString();

describe("relativeTime", () => {
  it("counts whole minutes, hours and days", () => {
    expect(relativeTime(ago(5 * 60), "en", NOW)).toBe("5 minutes ago");
    expect(relativeTime(ago(2 * 3_600), "en", NOW)).toBe("2 hours ago");
    expect(relativeTime(ago(3 * 86_400), "en", NOW)).toBe("3 days ago");
  });

  it("says yesterday for one day", () => {
    expect(relativeTime(ago(86_400), "en", NOW)).toBe("yesterday");
  });

  it("says nothing for under a minute, a future time or an unreadable one", () => {
    expect(relativeTime(ago(30), "en", NOW)).toBeNull();
    expect(relativeTime(ago(-600), "en", NOW)).toBeNull();
    expect(relativeTime("not a date", "en", NOW)).toBeNull();
  });

  it("writes it in the worker's language", () => {
    expect(relativeTime(ago(2 * 3_600), "hi", NOW)).toMatch(/घंटे/);
    expect(relativeTime(ago(2 * 3_600), "id", NOW)).toMatch(/jam/);
  });

  it("falls back to English for a language it does not know", () => {
    expect(relativeTime(ago(2 * 3_600), "xx-unknown", NOW)).toBe("2 hours ago");
  });
});
