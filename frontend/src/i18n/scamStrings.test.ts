// The scam module's strings, as a worker in each language would meet them (NF-SA-019). The parity
// script (scripts/check-i18n.mjs) already fails when a language lacks a key or a {{placeholder}};
// this adds what it cannot see: a string left in English, and a string written in the wrong script.
// It cannot tell a good translation from a stiff one: that needs a native speaker (D-154, D-157,
// D-159).
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const LANGUAGES = ["hi", "tl", "id", "ne", "bn"] as const;
type Language = (typeof LANGUAGES)[number];

type Tree = { [key: string]: Tree | string };

function leaves(node: Tree | string, prefix = ""): Record<string, string> {
  if (typeof node === "string") {
    return { [prefix]: node };
  }
  return Object.entries(node).reduce<Record<string, string>>(
    (all, [key, value]) => ({ ...all, ...leaves(value, prefix ? `${prefix}.${key}` : key) }),
    {}
  );
}

const read = (...parts: string[]): Record<string, string> =>
  leaves(JSON.parse(readFileSync(path.resolve(process.cwd(), "src/i18n", ...parts), "utf8")));

const scam = (language: string) => read("scam", `${language}.json`);
const shared = (language: string) => read(`${language}.json`);

const english = scam("en");

// Words that are the same in a language and in English: a loan-word, a file type, a number
// format. A new key that is identical to English must be added here on purpose, so it is a
// decision and not an omission.
const SAME_AS_ENGLISH: Readonly<Record<Language, readonly string[]>> = {
  hi: ["input.counter"],
  ne: ["input.counter"],
  bn: ["input.counter"],
  id: ["input.counter"],
  tl: [
    "input.counter",
    "home.title", // "Scam check": scam is the word Tagalog speakers use
    "input.modeScreenshot",
    "history.screenshot",
    "result.indicators.kind.url",
    "result.indicators.kind.email",
    "result.indicators.kind.handle",
  ],
};

const SCRIPT: Readonly<Record<Language, RegExp | null>> = {
  hi: /[ऀ-ॿ]/,
  ne: /[ऀ-ॿ]/,
  bn: /[ঀ-৿]/,
  tl: null,
  id: null,
};
const ANY_INDIC = /[ऀ-৿]/;

// A string that is only a format ("{{count}} / {{max}}") has no letters to be in any script.
const hasLetters = (text: string) => /\p{L}/u.test(text.replace(/{{[^}]+}}/g, ""));

describe.each(LANGUAGES)("scam strings in %s", (language) => {
  const strings = scam(language);

  it("is translated: nothing is left in English unless it is meant to be", () => {
    const left = Object.keys(strings).filter(
      (key) => strings[key] === english[key] && !SAME_AS_ENGLISH[language].includes(key)
    );

    expect(left).toEqual([]);
  });

  it("does not list a word as the same as English when it is not", () => {
    const stale = SAME_AS_ENGLISH[language].filter((key) => strings[key] !== english[key]);

    expect(stale).toEqual([]);
  });

  it("is written in the language's own script", () => {
    const script = SCRIPT[language];
    const wrong =
      script === null
        ? Object.keys(strings).filter((key) => ANY_INDIC.test(strings[key]))
        : Object.keys(strings).filter(
            (key) => hasLetters(strings[key]) && !script.test(strings[key])
          );

    expect(wrong).toEqual([]);
  });
});

describe("the three Radar labels that scam reports need in the shared strings", () => {
  const KEYS = [
    "radar.report.who.types.scam_type",
    "radar.violation.scam_message",
    "radar.entity.reportSource.scam_check",
  ] as const;

  it.each(LANGUAGES)("%s has them, translated", (language) => {
    const strings = shared(language);
    const base = shared("en");

    for (const key of KEYS) {
      expect(strings[key], key).toBeTruthy();
      expect(strings[key], key).not.toBe(base[key]);
    }
  });
});

describe("what every language has in common", () => {
  it("keeps the counts' plural forms: Indonesian has one, the others two", () => {
    for (const language of LANGUAGES) {
      const strings = scam(language);
      const forms = new Intl.PluralRules(language).resolvedOptions().pluralCategories;

      for (const form of forms) {
        expect(strings[`result.corridor_${form}`], `${language} corridor_${form}`).toBeTruthy();
      }
    }
  });

  it("has a title for the module in every language", () => {
    for (const language of LANGUAGES) {
      expect(scam(language)["home.title"]).toBeTruthy();
    }
  });
});
