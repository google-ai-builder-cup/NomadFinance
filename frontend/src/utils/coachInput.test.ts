import { describe, expect, it } from "vitest";

import {
  answerInputFor,
  defaultCurrency,
  isAmount,
  isDependents,
  isRate,
  isWholeUnitCurrency,
  parseAmount,
} from "@/utils/coachInput";

describe("parseAmount", () => {
  it.each([
    ["4200", 4200],
    ["4,200", 4200],
    ["4 200", 4200],
    ["1,50,000", 150_000],
    ["1.700.000", 1_700_000],
    ["1.700,50", 1700.5],
    ["1,700.50", 1700.5],
    ["4200.5", 4200.5],
    ["4,20", 4.2],
    // A dot is a decimal point even before three digits; a comma there groups thousands.
    ["4.200", 4.2],
    ["0.500", 0.5],
    ["  3000  ", 3000],
    ["0", 0],
  ])("reads %s as %s", (raw, expected) => {
    expect(parseAmount(raw)).toBe(expected);
  });

  it.each(["", "abc", "12abc", "-5", "1e3", "4200 AUD", "1..2", ",5", "12.3.4", "5,1000"])(
    "does not read %j as a number",
    (raw) => {
      expect(parseAmount(raw)).toBeNull();
    }
  );

  it.each([
    ["500.000", 500_000],
    ["500,000", 500_000],
    ["1.700.000", 1_700_000],
    ["50000", 50_000],
  ])("reads %s as %d where the currency has no minor unit", (raw, expected) => {
    expect(parseAmount(raw, true)).toBe(expected);
  });

  it("knows which coach currencies have no minor unit", () => {
    expect(["JPY", "KRW", "IDR"].map(isWholeUnitCurrency)).toEqual([true, true, true]);
    expect(["SGD", "AUD", "PHP", "INR", "NPR", "BDT"].map(isWholeUnitCurrency)).toEqual(
      Array(6).fill(false)
    );
  });
});

describe("the limits", () => {
  it("accepts pay above zero and a debt of zero", () => {
    expect(isAmount(2500, { allowZero: false })).toBe(true);
    expect(isAmount(0, { allowZero: false })).toBe(false);
    expect(isAmount(0, { allowZero: true })).toBe(true);
    expect(isAmount(null, { allowZero: true })).toBe(false);
    expect(isAmount(1_000_000_001, { allowZero: true })).toBe(false);
  });

  it("holds a rate to 0 to 1000 and people to a whole number from 0 to 20", () => {
    expect([isRate(0), isRate(3), isRate(1000), isRate(1001), isRate(null)]).toEqual([
      true,
      true,
      true,
      false,
      false,
    ]);
    expect([isDependents(0), isDependents(20), isDependents(21), isDependents(2.5)]).toEqual([
      true,
      true,
      false,
      false,
    ]);
  });
});

describe("answerInputFor", () => {
  it("offers six countries and seven jobs as chips", () => {
    const country = answerInputFor("intro", "destination_country");
    const job = answerInputFor("intro", "job_type");

    expect(country).toMatchObject({ kind: "choice", set: "country" });
    expect(country.kind === "choice" && [...country.ids].sort()).toEqual(
      ["AU", "HK", "JP", "KR", "MY", "SG"].sort()
    );
    expect(job.kind === "choice" && job.ids).toHaveLength(7);
  });

  it("asks pay for a period and a total for none", () => {
    expect(answerInputFor("income", "monthly_salary")).toEqual({
      kind: "money",
      periods: ["month", "week", "year"],
      canBeNone: false,
    });
    expect(answerInputFor("debt", "debt_outstanding")).toEqual({
      kind: "money",
      periods: [],
      canBeNone: true,
    });
  });

  it("gives each other question its own helper", () => {
    expect(answerInputFor("obligations", "dependents").kind).toBe("count");
    expect(answerInputFor("debt", "debt_interest").kind).toBe("interest");
    expect(answerInputFor("intro", "departure_date").kind).toBe("date");
    expect(answerInputFor("savings", "bank_or_wallet")).toMatchObject({ set: "bank" });
  });

  it("offers yes or change at the review, whatever the slot", () => {
    expect(answerInputFor("review", null)).toMatchObject({ kind: "choice", set: "review" });
  });

  it("falls back to free text when no question is known", () => {
    expect(answerInputFor("intro", null)).toEqual({ kind: "text" });
  });
});

describe("defaultCurrency", () => {
  it("starts with the host country's money", () => {
    expect(defaultCurrency({ destination_country: "JP" })).toBe("JPY");
    expect(defaultCurrency({ destination_country: "AU" })).toBe("AUD");
  });

  it("prefers the money the worker already used", () => {
    expect(
      defaultCurrency({
        destination_country: "AU",
        monthly_salary: { amount: 4200, currency: "INR", period: "month" },
      })
    ).toBe("INR");
  });

  it("does not trust a value that is not a currency of the contract", () => {
    expect(
      defaultCurrency({
        destination_country: "SG",
        monthly_salary: { amount: 1, currency: "XXX", period: "month" },
      })
    ).toBe("SGD");
  });
});

describe("parseAmount on another keyboard (QA-B-01, NF-HR-005)", () => {
  it("reads Devanagari and Bengali digits as 0 to 9", () => {
    expect(parseAmount("\u096a\u0968\u0966\u0966")).toBe(4200);
    expect(parseAmount("\u09ea\u09e8\u09e6\u09e6")).toBe(4200);
  });
});
