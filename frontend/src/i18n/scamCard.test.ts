// Every kind of scam, trick, flag and kind of contact the backend can name has a label in all six
// languages (NF-SA-016). The ids are read from the curated taxonomy and the contract, so a new id
// added there without strings here fails this test instead of showing a worker a raw key.
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const LANGUAGES = ["en", "hi", "tl", "id", "ne", "bn"] as const;
const TAXONOMY = path.resolve(process.cwd(), "../data-scripts/data/source/scam-taxonomy");

const ids = (file: string): string[] =>
  Object.keys(JSON.parse(readFileSync(path.join(TAXONOMY, file), "utf8")).entries);

type Tree = { [key: string]: Tree | string };
const strings = (language: string): Tree =>
  JSON.parse(readFileSync(path.resolve(process.cwd(), `src/i18n/scam/${language}.json`), "utf8"));

/** The string at a path in a language file, or undefined when any step is missing. */
function at(tree: Tree, ...steps: string[]): string | undefined {
  let node: Tree | string | undefined = tree;
  for (const step of steps) {
    node = typeof node === "object" ? node[step] : undefined;
  }
  return typeof node === "string" ? node : undefined;
}

describe.each(LANGUAGES)("scam card strings in %s", (language) => {
  const file = strings(language);
  const result = (...steps: string[]) => at(file, "result", ...steps);

  it("has a label for every kind of scam in the taxonomy", () => {
    for (const id of ids("types.json")) {
      expect(result("type", id), id).toBeTruthy();
    }
  });

  it("has a name and a general explanation for every trick in the taxonomy", () => {
    for (const id of ids("tactics.json")) {
      expect(result("tactic", id, "label"), id).toBeTruthy();
      expect(result("tactic", id, "what"), id).toBeTruthy();
    }
  });

  it("has a line for every flag, kind of contact and hidden value", () => {
    for (const flag of [
      "shortener",
      "punycode",
      "lookalike",
      "premium_rate",
      "unexpected_country",
    ]) {
      expect(result("indicators", "flag", flag), flag).toBeTruthy();
    }
    for (const kind of ["url", "phone", "email", "handle", "sender"]) {
      expect(result("indicators", "kind", kind), kind).toBeTruthy();
    }
    for (const token of ["PHONE", "EMAIL", "ID", "ACCOUNT", "URL"]) {
      expect(result("token", token), token).toBeTruthy();
    }
  });

  it("has the counts with the plural forms the language uses", () => {
    const forms = new Intl.PluralRules(language).resolvedOptions().pluralCategories;
    for (const form of forms) {
      expect(result("indicators", `seen_${form}`), `seen_${form}`).toBeTruthy();
      expect(result(`corridor_${form}`), `corridor_${form}`).toBeTruthy();
    }
  });

  it("keeps the placeholders the code fills in", () => {
    expect(result("indicators", "flag", "lookalike")).toContain("{{domain}}");
    expect(result("corridor_other")).toContain("{{count}}");
    expect(result("indicators", "seen_other")).toContain("{{count}}");
  });
});
