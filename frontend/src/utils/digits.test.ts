import { describe, expect, it } from "vitest";

import { toAsciiDigits } from "@/utils/digits";

describe("toAsciiDigits", () => {
  it.each([
    ["Devanagari (Hindi, Nepali)", "\u096b\u0966\u0966", "500"],
    ["Bengali", "\u09eb\u09e6\u09e6", "500"],
    ["Arabic-Indic", "\u0665\u0660\u0660", "500"],
    ["Persian", "\u06f5\u06f0\u06f0", "500"],
    ["full-width", "\uff15\uff10\uff10", "500"],
    ["Gujarati and Tamil", "\u0aeb\u0be6", "50"],
  ])("reads %s digits as 0 to 9", (_name, text, expected) => {
    expect(toAsciiDigits(text)).toBe(expected);
  });

  it("keeps separators, letters and ASCII digits as they are", () => {
    expect(toAsciiDigits("1,234.50 SGD")).toBe("1,234.50 SGD");
    expect(toAsciiDigits("abc \u096b,\u096a\u0966\u0966")).toBe("abc 5,400");
  });

  it("reads the Arabic decimal and thousands marks", () => {
    expect(toAsciiDigits("\u0661\u066c\u0662\u0663\u0664\u066b\u0665")).toBe("1,234.5");
  });

  it("leaves a digit of a script it does not know alone, so it is still refused", () => {
    expect(toAsciiDigits("\u1d7d8")).toBe("\u1d7d8");
  });
});
