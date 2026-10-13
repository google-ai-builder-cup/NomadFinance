import { describe, expect, it } from "vitest";

import { dottedThousands } from "@/utils/amountReading";

describe("dottedThousands", () => {
  it.each([
    ["1.500", 1500],
    ["645.505", 645505],
    [" 12.000 ", 12000],
    ["१.५००", 1500],
  ])("reads %s as %d and says it could be read another way", (text, value) => {
    expect(dottedThousands(text)).toBe(value);
  });

  it.each(["1.5", "1.50", "1,500", "1.500.000", "1500", "0.500", "abc", "", "1.5000"])(
    "has one reading for %j",
    (text) => {
      // 0.500 is a half, not five hundred: a first group of zero is not thousands.
      expect(dottedThousands(text)).toBeNull();
    }
  );
});
