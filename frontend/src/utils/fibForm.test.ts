import { describe, expect, it } from "vitest";

import { MAX_AMOUNT, MAX_AMOUNT_WHOLE_UNIT, parseAmount } from "@/utils/fibForm";

describe("parseAmount", () => {
  it.each([
    ["650", 650],
    ["650.50", 650.5],
    ["650,50", 650.5],
    ["6,5", 6.5],
    ["1,000.50", 1000.5],
    ["1.000,50", 1000.5],
    // A dot is a decimal point even before three digits; a comma there groups thousands.
    ["6.500", 6.5],
    ["6,500", 6500],
  ])("reads %s as %d", (text, amount) => {
    expect(parseAmount(text, "SGD")).toEqual({ ok: true, amount });
  });

  it.each([
    ["", "empty"],
    ["abc", "invalid"],
    ["-5", "invalid"],
    ["0", "invalid"],
    ["1e3", "invalid"],
    ["1,2,3", "invalid"],
    ["10.555", "decimals"],
  ])("refuses '%s' as %s", (text, problem) => {
    expect(parseAmount(text, "SGD")).toEqual({ ok: false, problem });
  });

  it("refuses more decimals than the currency has", () => {
    expect(parseAmount("10.5", "JPY")).toEqual({ ok: false, problem: "decimals" });
    expect(parseAmount("10,5", "KRW")).toEqual({ ok: false, problem: "decimals" });
    expect(parseAmount("10.5555", "AUD")).toEqual({ ok: false, problem: "decimals" });
  });

  it("reads a mark before three digits as thousands where there is no minor unit", () => {
    expect(parseAmount("42.000", "JPY")).toEqual({ ok: true, amount: 42000 });
    expect(parseAmount("42,000", "KRW")).toEqual({ ok: true, amount: 42000 });
  });

  it("refuses an amount beyond the most one entry can be, as the server does", () => {
    expect(parseAmount(String(MAX_AMOUNT), "SGD")).toEqual({ ok: true, amount: MAX_AMOUNT });
    expect(parseAmount(String(MAX_AMOUNT + 1), "SGD")).toEqual({ ok: false, problem: "tooLarge" });
    expect(parseAmount("99999999999999", "MYR")).toEqual({ ok: false, problem: "tooLarge" });
  });

  it("lets the yen and the won run a hundred times higher", () => {
    expect(parseAmount(String(MAX_AMOUNT_WHOLE_UNIT), "KRW")).toEqual({
      ok: true,
      amount: MAX_AMOUNT_WHOLE_UNIT,
    });
    expect(parseAmount(String(MAX_AMOUNT_WHOLE_UNIT + 1), "JPY")).toEqual({
      ok: false,
      problem: "tooLarge",
    });
  });
});

describe("parseAmount on another keyboard (QA-B-01, NF-HR-005)", () => {
  it("reads Hindi, Bengali and Arabic-Indic digits as 0 to 9", () => {
    expect(parseAmount("\u096b\u0966\u0966", "SGD")).toEqual({ ok: true, amount: 500 });
    expect(parseAmount("\u09eb\u09e6\u09e6", "SGD")).toEqual({ ok: true, amount: 500 });
    expect(parseAmount("\u0665\u0660\u0660", "SGD")).toEqual({ ok: true, amount: 500 });
  });
});
