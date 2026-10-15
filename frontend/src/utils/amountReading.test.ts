import { describe, expect, it } from "vitest";

import { ambiguousReading, readTypedAmount } from "@/utils/amountReading";

describe("readTypedAmount", () => {
  it.each([
    ["500", "500"],
    ["645.50", "645.5"],
    ["645,50", "645.5"],
    ["5,10", "5.1"],
    ["0,5", "0.5"],
    ["0.500", "0.5"],
    ["0,500", "0.5"],
    ["12,345.6", "12345.6"],
    ["4 200.50", "4200.5"],
    ["५,४००", "5400"],
  ])("reads %j as %s", (text, normalized) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: true, normalized });
  });

  it.each([
    ["5.400", "5.4"],
    ["1.500", "1.5"],
    ["645.505", "645.505"],
    ["५.४००", "5.4"],
  ])("reads a dot before three digits, %j, as a decimal point: %s", (text, normalized) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: true, normalized });
  });

  it.each([
    ["5,400", "5400"],
    ["1,530,000", "1530000"],
    ["1.530.000", "1530000"],
    ["1,50,000", "150000"],
  ])("reads the grouped %j as thousands: %s", (text, normalized) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: true, normalized });
  });

  it.each([
    ["1,530.50", "1530.5"],
    ["1.530,50", "1530.5"],
    ["1.530.000,50", "1530000.5"],
    ["1,50,000.50", "150000.5"],
  ])("takes the last mark of %j as the decimal point: %s", (text, normalized) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: true, normalized });
  });

  it.each([
    "",
    "abc",
    "5,1000",
    "12.3.4",
    "1,2,3",
    "1,23,45",
    "1.5,30",
    "1,530.500.5",
    "-5",
    "1e3",
  ])("refuses %j as not a number", (text) => {
    expect(readTypedAmount(text, false)).toEqual({ ok: false, problem: "invalid" });
  });

  it("reads a mark before three digits as thousands for a currency with no minor unit", () => {
    expect(readTypedAmount("42,000", true)).toEqual({ ok: true, normalized: "42000" });
    expect(readTypedAmount("42.000", true)).toEqual({ ok: true, normalized: "42000" });
    expect(readTypedAmount("1.530.000", true)).toEqual({ ok: true, normalized: "1530000" });
    expect(readTypedAmount("17000", true)).toEqual({ ok: true, normalized: "17000" });
  });

  it("leaves a fraction of a whole-unit currency for the caller to refuse", () => {
    expect(readTypedAmount("5,10", true)).toEqual({ ok: true, normalized: "5.1" });
    expect(readTypedAmount("17000.5", true)).toEqual({ ok: true, normalized: "17000.5" });
    expect(readTypedAmount("0.500", true)).toEqual({ ok: true, normalized: "0.5" });
  });
});

describe("ambiguousReading", () => {
  it.each([
    ["5.400", 5.4],
    ["5,400", 5400],
    ["645.505", 645.505],
    [" 12,000 ", 12000],
    ["१.५००", 1.5],
  ])("reads %j as %d and says it could be read another way", (text, value) => {
    expect(ambiguousReading(text, 2)).toBe(value);
  });

  it.each(["5.4", "5.40", "5,40", "1.500.000", "1,500,000", "5400", "0.500", "0,500", "abc", ""])(
    "has one reading for %j",
    (text) => {
      expect(ambiguousReading(text, 2)).toBeNull();
    }
  );

  it("has no second reading where a currency has no minor unit", () => {
    expect(ambiguousReading("42.000", 0)).toBeNull();
    expect(ambiguousReading("42,000", 0)).toBeNull();
  });
});
