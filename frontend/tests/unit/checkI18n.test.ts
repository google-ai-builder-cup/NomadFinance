import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";

// @ts-expect-error: a plain ES module script with no type declarations
import { checkI18n, readLanguages } from "../../scripts/check-i18n.mjs";

const LANGUAGES = ["en", "hi", "id"];
const dirs: string[] = [];

type Strings = Record<string, unknown>;

// A throwaway src/i18n folder: `shared` is the default namespace, `modules` maps a namespace to
// its per-language files.
function makeDir(
  shared: Record<string, Strings>,
  modules: Record<string, Record<string, Strings>> = {}
) {
  const dir = mkdtempSync(path.join(tmpdir(), "i18n-check-"));
  dirs.push(dir);
  for (const [language, content] of Object.entries(shared)) {
    writeFileSync(path.join(dir, `${language}.json`), JSON.stringify(content));
  }
  for (const [namespace, files] of Object.entries(modules)) {
    mkdirSync(path.join(dir, namespace));
    for (const [language, content] of Object.entries(files)) {
      writeFileSync(path.join(dir, namespace, `${language}.json`), JSON.stringify(content));
    }
  }
  return dir;
}

const messages = (result: { problems: { message: string }[] }) =>
  result.problems.map((problem) => problem.message);

afterEach(() => {
  for (const dir of dirs.splice(0)) rmSync(dir, { recursive: true, force: true });
});

describe("checkI18n", () => {
  const ok = { a: "A", nested: { b: "B {{name}}" } };

  it("passes when every language has every key", () => {
    const dir = makeDir({ en: ok, hi: ok, id: ok }, { coach: { en: ok, hi: ok, id: ok } });

    const result = checkI18n(dir, LANGUAGES);

    expect(result.problems).toEqual([]);
    expect(result.namespaces).toEqual(["translation", "coach"]);
  });

  it("names the namespace, language and key that is missing", () => {
    const dir = makeDir({ en: ok, hi: ok, id: ok }, { scam: { en: ok, hi: { a: "A" }, id: ok } });

    const result = checkI18n(dir, LANGUAGES);

    expect(result.problems).toEqual([
      { namespace: "scam", language: "hi", message: "missing key nested.b" },
    ]);
  });

  it("fails on a key English does not have", () => {
    const dir = makeDir({ en: ok, hi: { ...ok, extra: "x" }, id: ok });

    expect(messages(checkI18n(dir, LANGUAGES))).toEqual([
      "key extra is not in English (the source of truth)",
    ]);
  });

  it("fails on empty text and on changed {{placeholders}}", () => {
    const dir = makeDir({
      en: ok,
      hi: { a: " ", nested: { b: "B {{nom}}" } },
      id: ok,
    });

    expect(messages(checkI18n(dir, LANGUAGES))).toEqual([
      "a: empty or not a string",
      "nested.b: {{placeholders}} differ from English",
    ]);
  });

  it("fails on a missing file and on invalid JSON", () => {
    const dir = makeDir({ en: ok, hi: ok }, { coach: { en: ok, hi: ok, id: ok } });
    writeFileSync(path.join(dir, "coach", "hi.json"), "{ not json");

    const found = messages(checkI18n(dir, LANGUAGES));

    expect(found).toContain("file is missing");
    expect(found.some((message) => message.startsWith("not valid JSON"))).toBe(true);
  });

  it("fails a module namespace whose English file is missing", () => {
    const dir = makeDir({ en: ok, hi: ok, id: ok }, { coach: { hi: ok, id: ok } });

    expect(checkI18n(dir, LANGUAGES).problems).toEqual([
      { namespace: "coach", language: "en", message: "file is missing" },
    ]);
  });

  it("compares plural keys by base name: Indonesian has only one form", () => {
    const dir = makeDir({
      en: { item_one: "{{count}} item", item_other: "{{count}} items" },
      hi: { item_one: "{{count}} x", item_other: "{{count}} xs" },
      id: { item_other: "{{count}} barang" },
    });

    expect(checkI18n(dir, LANGUAGES).problems).toEqual([]);
  });
});

describe("the shipped locale files", () => {
  it("read the six supported languages", () => {
    expect(readLanguages()).toEqual(["en", "hi", "tl", "id", "ne", "bn"]);
  });

  it("have every key in every language, for every namespace", () => {
    const result = checkI18n();

    expect(result.problems).toEqual([]);
    expect(result.namespaces).toEqual(["translation", "coach", "scam"]);
  });
});
