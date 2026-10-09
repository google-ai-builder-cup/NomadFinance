// @vitest-environment jsdom
import { beforeAll, describe, expect, it } from "vitest";

import i18n, { loadNamespace } from "@/lib/i18n";
import { formatDate, recapRows, recapValue } from "@/utils/coachRecap";

beforeAll(async () => {
  await loadNamespace("coach");
});

const t = (key: string, options?: Record<string, unknown>) =>
  i18n.getFixedT("en", ["coach", "translation"])(key, options) as string;

describe("formatDate", () => {
  it("writes the day in the language of the worker, with no time-zone shift", () => {
    expect(formatDate("2026-12-01", "en")).toBe("December 1, 2026");
    expect(formatDate("2026-12-01", "id")).toBe("1 Desember 2026");
  });

  it("keeps digits 0 to 9 in languages whose own digits differ", () => {
    for (const language of ["ne", "bn", "hi"]) {
      expect(formatDate("2026-12-01", language)).toMatch(/2026/);
    }
  });

  it("gives back text that is not a date as it is", () => {
    expect(formatDate("soon", "en")).toBe("soon");
  });
});

describe("recapValue", () => {
  it("puts a money answer in the sentence the helpers send", () => {
    expect(
      recapValue("monthly_salary", { amount: 4200, currency: "AUD", period: "month" }, t, "en")
    ).toBe("4,200 AUD per month");
    expect(
      recapValue("debt_outstanding", { amount: 120000, currency: "INR", period: "once" }, t, "en")
    ).toBe("120,000 INR");
  });

  it("says none for zero, which is an answer", () => {
    expect(recapValue("savings", { amount: 0, currency: "SGD", period: "once" }, t, "en")).toBe(
      "None (0)"
    );
  });

  it("names a country, a kind of work and a bank answer", () => {
    expect(recapValue("destination_country", "AU", t, "en")).toBe("Australia");
    expect(recapValue("job_type", "care_worker", t, "en")).toBe("Care worker");
    expect(recapValue("bank_or_wallet", "both", t, "en")).toBe(
      "Both a bank account and a mobile wallet"
    );
  });

  it("reads an interest rate and a count", () => {
    expect(recapValue("debt_interest", { rate_percent: 3, period: "month" }, t, "en")).toBe(
      "3% interest per month"
    );
    expect(recapValue("dependents", 3, t, "en")).toBe("3");
  });

  it("gives nothing for a value of a shape the Coach does not store", () => {
    expect(recapValue("monthly_salary", "lots", t, "en")).toBeNull();
    expect(recapValue("dependents", "three", t, "en")).toBeNull();
  });
});

describe("recapRows", () => {
  it("lists the answers in the order of the interview and leaves out what was not answered", () => {
    const rows = recapRows(
      {
        savings: { amount: 25000, currency: "INR", period: "once" },
        destination_country: "AU",
        dependents: 3,
      },
      t,
      "en"
    );

    expect(rows.map((row) => [row.slot, row.label, row.value])).toEqual([
      ["destination_country", "Country you will work in", "Australia"],
      ["dependents", "People who depend on you", "3"],
      ["savings", "Your savings", "25,000 INR"],
    ]);
  });

  it("shows a dash, not nothing, for an answer it cannot put in words", () => {
    expect(recapRows({ monthly_salary: "lots" }, t, "en")[0]?.value).toBe("—");
  });
});
