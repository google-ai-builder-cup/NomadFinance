import { describe, expect, it } from "vitest";

import { weekdayName } from "@/utils/format";

describe("weekdayName", () => {
  it("names all five weekdays in English, in order", () => {
    expect(
      (["monday", "tuesday", "wednesday", "thursday", "friday"] as const).map((day) =>
        weekdayName(day, "en")
      )
    ).toEqual(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]);
  });

  it("names a weekday in another UI language", () => {
    expect(weekdayName("wednesday", "hi")).toBe("बुधवार");
  });

  it("falls back to the weekday's own code if the browser can't name it", () => {
    expect(weekdayName("wednesday", "!!!not-a-locale!!!")).toBe("wednesday");
  });
});
