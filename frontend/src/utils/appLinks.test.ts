import { describe, expect, it } from "vitest";

import { isCoachCheckinPath, safeAppPath } from "@/utils/appLinks";

describe("a link that came in a push", () => {
  it.each(["/coach/checkin/5a202702c922fc9b4fcf?m=30", "/radar/alerts", "/dashboard"])(
    "follows %s",
    (link) => {
      expect(safeAppPath(link)).toBe(link);
    }
  );

  it.each([
    undefined,
    null,
    42,
    "",
    "dashboard",
    "//evil.example/coach/checkin/x",
    "/\\evil.example",
    "https://evil.example/coach/checkin/x",
    "javascript:alert(1)",
    "/coach/checkin/x\n",
    "/" + "a".repeat(300),
  ])("does not follow %j", (link) => {
    expect(safeAppPath(link)).toBeNull();
  });

  it("knows a Coach check-in link from any other", () => {
    expect(isCoachCheckinPath("/coach/checkin/5a202702c922fc9b4fcf?m=60")).toBe(true);
    expect(isCoachCheckinPath("/coach/checkin/")).toBe(false);
    expect(isCoachCheckinPath("/coach/plan/5a202702c922fc9b4fcf")).toBe(false);
    expect(isCoachCheckinPath("/radar/alerts")).toBe(false);
  });
});
