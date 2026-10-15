import { describe, expect, it } from "vitest";

import { dottedThousands, readTypedAmount } from "@/utils/amountReading";

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

describe("readTypedAmount", () => {
  it.each([
    ["500", "500"],
    ["645.50", "645.50"],
    ["5,400", "5400"],
    ["5.400", "5400"],
    ["1,530.50", "1530.50"],
    ["0.500", "0.500"],
    ["५,४००", "5400"],
  ])("reads %j as %s", (text, normalized) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: true, normalized });
  });

  it.each(["5,10", "645,50", "1.530,50", "0,5"])("refuses %j: a comma is not a decimal", (text) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: false, problem: "decimalComma" });
  });

  it.each(["", "abc", "5,1000", "12.3.4", "-5", "1e3"])("refuses %j as not a number", (text) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: false, problem: "invalid" });
  });

  it("reads every separator as thousands for a currency with no minor unit", () => {
    expect(readTypedAmount("42,000", true)).toEqual({ ok: true, normalized: "42000" });
    expect(readTypedAmount("42.000", true)).toEqual({ ok: true, normalized: "42000" });
    expect(readTypedAmount("5,10", true)).toEqual({ ok: false, problem: "invalid" });
  });
});
