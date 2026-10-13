import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import { CORRIDOR_IDS } from "@/types/enums";
import {
  adviceFailureKey,
  CORRIDORS,
  compareFailure,
  defaultCorridor,
  parseAmount,
  parseCompareLink,
} from "@/utils/corridors";
import { formatMoney } from "@/utils/format";

interface SurveyQuote {
  send_amount_lcu: number;
}

interface SurveyFile {
  corridors: {
    corridor_id: string;
    source_currency: string;
    destination_currency: string;
    providers: { quote_200: SurveyQuote; quote_500: SurveyQuote }[];
  }[];
}

const SURVEY = JSON.parse(
  readFileSync(
    new URL("../../../data-scripts/data/processed/rpw_corridors.json", import.meta.url),
    "utf-8"
  )
) as SurveyFile;

describe("CORRIDORS", () => {
  it("covers the six corridors of the project scope", () => {
    expect(Object.keys(CORRIDORS).sort()).toEqual([...CORRIDOR_IDS].sort());
  });

  it.each(SURVEY.corridors.map((c) => [c.corridor_id, c] as const))(
    "%s matches the survey file the backend compares with",
    (id, surveyed) => {
      const info = CORRIDORS[id as keyof typeof CORRIDORS];
      const low = Math.min(...surveyed.providers.map((p) => p.quote_200.send_amount_lcu));
      const high = Math.max(...surveyed.providers.map((p) => p.quote_500.send_amount_lcu));

      expect(info.sendCurrency).toBe(surveyed.source_currency);
      expect(info.receiveCurrency).toBe(surveyed.destination_currency);
      expect(info.surveyAmounts).toEqual([low, high]);
      // backend/app/services/remittance/engine.py: MIN_AMOUNT_FACTOR 0.25, MAX_AMOUNT_FACTOR 10
      expect(info.minAmount).toBeCloseTo(low * 0.25, 6);
      expect(info.maxAmount).toBeCloseTo(high * 10, 6);
    }
  );

  it("splits each id into host and home country", () => {
    expect(CORRIDORS["MY-ID"]).toMatchObject({ host: "MY", home: "ID" });
  });
});

describe("defaultCorridor", () => {
  it("picks the worker's own corridor", () => {
    expect(defaultCorridor("AU", "PH")).toBe("AU-PH");
  });

  it("falls back to the first corridor from the host country", () => {
    expect(defaultCorridor("SG", "NP")).toBe("SG-PH");
    expect(defaultCorridor("AU", "BD")).toBe("AU-IN");
  });

  it("falls back to the first corridor for a host with none", () => {
    expect(defaultCorridor("KR", "NP")).toBe("SG-PH");
    expect(defaultCorridor(undefined, undefined)).toBe("SG-PH");
  });
});

describe("parseAmount", () => {
  const sgd = CORRIDORS["SG-PH"];
  const jpy = CORRIDORS["JP-PH"];

  it.each([
    ["645", 645],
    [" 645 ", 645],
    ["645.5", 645.5],
    ["645,50", 645.5],
    ["6,450", 6450],
    ["6.450", 6450],
    // A dot before exactly three digits groups thousands (the Indonesian "1.530").
    ["1.530", 1530],
    ["1,530.50", 1530.5],
    ["1.530,50", 1530.5],
    ["65", 65],
  ])("reads %j as %d SGD", (text, amount) => {
    expect(parseAmount(text, sgd)).toEqual({ ok: true, amount });
  });

  it.each([
    ["42000", 42000],
    ["42,000", 42000],
    ["42.000", 42000],
    ["4 250", 4250],
    ["4\u00a0250", 4250],
  ])("reads %j as %d yen", (text, amount) => {
    expect(parseAmount(text, jpy)).toEqual({ ok: true, amount });
  });

  it.each([
    ["", "empty"],
    ["   ", "empty"],
    ["abc", "invalid"],
    ["-100", "invalid"],
    ["1e3", "invalid"],
    ["0", "invalid"],
    ["12.3.4", "invalid"],
    ["645.5555", "decimals"],
    ["64.99", "tooSmall"],
    ["6450.01", "tooLarge"],
  ])("refuses %j for SGD: %s", (text, problem) => {
    expect(parseAmount(text, sgd)).toEqual({ ok: false, problem });
  });

  it("refuses a fraction of a yen and amounts outside the yen limits", () => {
    expect(parseAmount("17000.5", jpy)).toEqual({ ok: false, problem: "decimals" });
    expect(parseAmount("4249", jpy)).toEqual({ ok: false, problem: "tooSmall" });
    expect(parseAmount("420001", jpy)).toEqual({ ok: false, problem: "tooLarge" });
  });
});

describe("formatMoney", () => {
  it("formats in the UI language with the currency", () => {
    // Intl puts a no-break space between the code and the number.
    const plain = (text: string) => text.replace(/\u00a0/g, " ");
    expect(plain(formatMoney(6450, "SGD", "en"))).toBe("SGD 6,450");
    expect(plain(formatMoney(152.5, "MYR", "en"))).toBe("MYR 152.50");
    expect(formatMoney(44615.2, "PHP", "en")).toBe("₱44,615.20");
    expect(formatMoney(3384.004, "PHP", "en")).toBe("₱3,384.00");
    expect(formatMoney(42000, "JPY", "en", 0)).toBe("¥42,000");
  });

  it("falls back to plain text for a code the browser cannot format", () => {
    expect(formatMoney(5, "NOT-A-CURRENCY", "en")).toBe("5 NOT-A-CURRENCY");
  });
});

describe("compareFailure", () => {
  it("says the corridor has no prices yet on a 404", () => {
    expect(compareFailure(new ApiError(404, "No prices"), "SG-PH", "en")).toEqual({
      key: "remittance.form.errors.notLoaded",
    });
  });

  it("names the corridor's limits on a 422, in the UI language", () => {
    const failure = compareFailure(new ApiError(422, "Enter an amount"), "JP-PH", "en");

    expect(failure.key).toBe("remittance.form.errors.outOfRange");
    expect(failure.values).toEqual({ min: "¥4,250", max: "¥420,000" });
  });

  it("uses the app-wide messages for anything else", () => {
    expect(compareFailure(new ApiError(0, "Network error"), "SG-PH", "en").key).toBe(
      "errors.offline"
    );
    expect(compareFailure(new ApiError(500, "boom"), "SG-PH", "en").key).toBe("errors.server");
  });
});

describe("the link into the comparison from a plan", () => {
  const link = (query: string) => parseCompareLink(new URLSearchParams(query));

  it("gives the corridor and the amount", () => {
    expect(link("corridor=AU-IN&amount=900")).toEqual({ corridorId: "AU-IN", amount: 900 });
    expect(link("corridor=SG-PH&amount=412.5")).toEqual({ corridorId: "SG-PH", amount: 412.5 });
  });

  it.each([
    ["no query", ""],
    ["no amount", "corridor=AU-IN"],
    ["no corridor", "amount=900"],
    ["a corridor outside the six", "corridor=NP-BD&amount=900"],
    ["an amount that is not a number", "corridor=AU-IN&amount=lots"],
    ["a negative amount", "corridor=AU-IN&amount=-5"],
    ["an amount with more decimals than the currency has", "corridor=JP-PH&amount=100.5"],
    ["an amount above the corridor's limit", "corridor=AU-IN&amount=999999999"],
  ])("is nothing for %s, so the screen opens as usual", (_label, query) => {
    expect(link(query)).toBeNull();
  });
});

describe("an amount typed on another keyboard (QA-B-01, NF-HR-005)", () => {
  const sgd = CORRIDORS["SG-IN"];

  it.each([
    ["Devanagari", "\u096b\u0966\u0966"],
    ["Bengali", "\u09eb\u09e6\u09e6"],
    ["Arabic-Indic", "\u0665\u0660\u0660"],
    ["full-width", "\uff15\uff10\uff10"],
  ])("reads %s digits", (_name, text) => {
    expect(parseAmount(text, sgd)).toEqual({ ok: true, amount: 500 });
  });

  it("reads grouped and decimal amounts in those digits", () => {
    expect(parseAmount("\u0967,\u0966\u0966\u0966", sgd)).toEqual({ ok: true, amount: 1000 });
    expect(parseAmount("\u096c\u096a\u096b.\u096b\u0966", sgd)).toEqual({
      ok: true,
      amount: 645.5,
    });
  });

  it("still refuses what is not a number", () => {
    expect(parseAmount("\u096b\u0966\u0966 SGD", sgd)).toEqual({ ok: false, problem: "invalid" });
  });
});

describe("adviceFailureKey (QA-B-02)", () => {
  it("does not speak of a contract when the model's answer was unusable", () => {
    expect(adviceFailureKey(new ApiError(502, "ai_bad_response"))).toBe("errors.server");
  });

  it("keeps the shared words for a busy or slow model", () => {
    expect(adviceFailureKey(new ApiError(503, "ai_busy"))).toBe("contract.progress.errors.aiBusy");
    expect(adviceFailureKey(new ApiError(504, "ai_timeout"))).toBe(
      "contract.progress.errors.aiSlow"
    );
  });
});
